# patchwise

kept watching claude wrap its diffs in ```diff fences. agent fed the wrapped
text to apply_patch, apply_patch choked on the fence, agent retried with the
same broken output. fix one: a tolerant `apply_patch` that surfaces what's
actually wrong (fences, line drift, truncated hunks) so the agent can react.
fix two: a small harness to check whether the better applier actually moves
solve rate.

scratch repo. not a library.

## what's in here

- `apply_patch/` — the parser + applier. structured errors (`FencedDiffError`,
  `LineDriftError`, `PartialHunkError`, `MalformedDiffError`) with enough info
  for a caller to retry, unwrap, or bail.
- `harness/` — sandboxed runner. clones the upstream repo at the task's base
  SHA, applies fixture test files, hands a tool catalog to the scaffold, runs
  the actual test command, scores success.
- `harness/scaffolds/` — `react.py` (plain ReAct loop) and `planner_executor.py`
  (planner produces a plan, executor follows it; rough — see TODOs).
- `harness/tasks/` — 12 task fixtures pulled from real merged PRs across
  fastapi / httpx / requests / rich / click / poetry / urllib3. each has a
  manifest + the new test files; the agent works against the cloned upstream
  repo at `base_sha`.
- `scripts/run_eval.py` + `scripts/analyze_results.py` — orchestration + report.
- `results/` — eval-run summaries and notes. trace `.sqlite` files are
  gitignored.

## failure modes the applier handles

real model output i collected by hand. each one breaks a naive applier.

### fenced markdown wrap (claude, gpt, gemini)

```
Here's the diff:

​```diff
--- a/click/core.py
+++ b/click/core.py
@@ -1,4 +1,9 @@
...
​```
```

`apply_diff(text)` raises `FencedDiffError(fence_marker="```diff", unwrapped=...)`.
the caller can either retry with the unwrapped content or kick it back to the
model with "drop the fences."

### line-number drift

model generated a diff against a slightly older copy of a file. the `@@ -X,Y`
header points at line 1 but the function actually moved to line 6 because
someone added imports. tolerant applier searches `±20` lines around the stated
position for the unique context window. one match → apply with a recorded
warning. zero or multiple matches → `LineDriftError`, don't guess.

### partial hunk (response truncated mid-stream)

```
@@ -17,18 +17,28 @@ def get_request_handler(...):
+    logger.debug("building handler: ...")
     async def app(request: Request) -> Response:
...
+                logger.exception("unexpected body parse e
```

declared 28 new lines in the header, only 27 actually arrived (the last `+`
line is mid-string). naive appliers happily write the half-hunk and corrupt
the file. tolerant raises `PartialHunkError`.

### bare empty lines in hunk body

LLMs and editors strip trailing whitespace, so blank context lines often arrive
as `""` instead of `" "`. parser normalizes empty body lines to a single space
so the count check, drift verify, and apply all see them as context. (this one
took me a while to find — see `notes.md`.)

## results so far

ran the 4-task / 4-variant / 2-model / 2-trial sweep on 2026-01-24. 64
trajectories, **8 pass**.

| variant | pass / total | pct |
|---|---|---|
| naive_react | 2 / 16 | 12.5% |
| naive_planner | 1 / 16 | 6.2% |
| tolerant_react | 2 / 16 | 12.5% |
| tolerant_planner | 3 / 16 | 18.8% |

averaging over scaffolds, **tolerant variants pass 5/32 (15.6%) vs naive 3/32
(9.4%)** — a ~6pp gap in the right direction. averaging over tool layers,
**react and planner are tied at 12.5%**. so on this fixture set the tool layer
moved solve rate where the scaffold change didn't.

caveats:

- n is small. 6pp at 32 trajectories per side isn't statistically clean — the
  95% CI on each proportion is ~±10pp. directional support, not a strong claim.
- 4 tasks, all single-file. the scaffold-on-multi-file question is genuinely
  unanswered — the two multi-file fixtures (`poetry_rstrip_eats_alpha_versions`,
  `httpx_iter_text_emits_empty_chunks`) aren't in this run yet.
- model effect dominates: claude solves 6/32, gpt-4o-mini solves 2/32. wasn't
  expecting that gap.

full breakdown in `results/run2_summary.txt`. interpretation in
`results/run2_notes.md`.

## what's broken / TODO

- task set is small (n=4 in the eval; 12 fixtures total but 8 not yet run).
  expanding when batch 2/3 fixtures are merged in.
- planner-executor scaffold doesn't actually constrain the executor to the
  plan — it just puts the plan in the system prompt. on this fixture set it
  reduces to "react with a plan-shaped intro" and adds zero solve rate.
  redesign so the executor walks plan steps explicitly.
- `httpx_send_ignores_client_timeout` is 0/16 across all variants. suspect
  the test asserts both sync + async timeout paths and the agent only fixes
  one. need to look before drawing conclusions about that task.
- harness leaks docker containers when interrupted with Ctrl+C — cleanup is
  lazy. (also: docker mode is documented but the eval defaults to subprocess
  mode for speed; the docker path needs more love.)
- haven't tried this with reasoning models (o1/o3 family) yet. hypothesis:
  reasoning models make way fewer of these mundane diff mistakes, so the
  tolerant applier matters less. would be a real result either way.
- max_steps=20 is saturated — mean tool calls per trajectory ≈ 17. bumping
  to 30 might help on close-but-not-quite trajectories. cheap experiment.

## running the eval

needs python 3.10+ and [uv](https://github.com/astral-sh/uv) (`brew install uv`
or `curl -LsSf https://astral.sh/uv/install.sh | sh`). from a clean clone:

```bash
uv venv --python 3.12 .venv
.venv/bin/python -m ensurepip --upgrade
uv pip install --python .venv/bin/python -e ".[dev,eval]"
```

then set both API keys (the eval uses gpt-4o-mini and claude-haiku-4-5):

```bash
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...
.venv/bin/python scripts/run_eval.py --trace-db trace.sqlite
.venv/bin/python scripts/analyze_results.py --trace-db trace.sqlite
```

cost on the full 12-task sweep: ~$10-15 with mini-tier models. runtime: 2-4
hours sequential.

## license

MIT. see [LICENSE](LICENSE).
