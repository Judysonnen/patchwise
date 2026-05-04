# notes

scratch journal. dated entries, mostly things i thought about while staring
at trace logs. unedited.

## sept 14

started this because i was getting annoyed at apply_patch failures from claude
code. wrote a 60-line unified-diff applier on a saturday night. handles the
textbook case, nothing else. felt smug for about 6 days.

## sept 28

damn it, fenced markdown again. claude does it ~40% of the time, codex CLI
maybe 15%, gpt somewhere in between. so consistent across providers it
should just be normalized at the system-prompt layer. but here we are.

## oct 5

wrote a fuzzy line-drift recovery (search ±20 lines for the unique context
window). off-by-one in the upper bound of the search range, found it the
same day by manually testing. one-line fix. feel lucky i didn't ship it.

## oct 14

realized one of the line-drift "fixes" was actually masking a real bug in my
prompt — i was telling the model to assume line numbers from the OLD version
of the file. fixed prompt, line drift went down a lot. so maybe the applier
doesn't need to be that smart? idk. left the fuzzy match in because the model
will sometimes get drift even with a perfect prompt.

## nov 3

questions for future me: why does claude wrap diffs in ```diff fences when
gpt mostly doesn't? system-prompt artifact? training distribution? if i told
the model "plain text only, no code fences" would it stop? worth a small
experiment when i have a quiet hour.

also at some point i should try this with reasoning models. hypothesis:
o1/o3 makes way fewer of these mundane mistakes so the applier matters less.
would be a real result either way — either the applier is doing work that
matters across model classes, or it's papering over a mini-model failure
mode that the next generation kills.

## dec 13

wrote run_eval.py. 4 variants × 2 models × 3 trials × N tasks. didn't run it
on real APIs yet, dry-run looked fine. tomorrow.

## dec 14

ran the eval. 0/96. all failed.

took an embarrassing amount of time to figure out why: harness clones the
upstream repo at base_sha but never installs the package. so pytest can't
`import requests` before even getting to the agent's fix. for every
trajectory. ate $5 to learn what one local dry-run would have caught.

## dec 16

added pip install of the upstream package + test extras after the clone, with
a per-(repo, sha) install registry so we don't reinstall every trajectory.
broke the e2e tests because i forgot to mock the new function. immediate
follow-up commit. this is what tests are for.

## dec 21

added retry-with-backoff for both API clients on rate limits + transient 5xx.
also surface scaffold errors into the trace as a typed event. the previous
run had ~12 trajectories die at steps=0 in 2 seconds — those would now be
recoverable rate-limit retries.

## jan 4

wrote a sanity test that takes a real PR's fix diff and applies it through
both variants. tolerant rejected the requests/6629 fix with PartialHunkError.
test caught the bug i'd been worried about. except it wasn't the bug i thought.

## jan 5

the bug: blank context lines in a hunk body don't have a leading space (LLMs
and editors strip trailing whitespace, and apparently so does whatever
saved my snapshot). my parser was treating those as "neither space nor
add/delete" and silently dropping them from the count, the verify, and the
apply. parser now normalizes empty body lines to ' '. one of those bugs you'd
never find without a real-shaped fixture.

a chunk of the LineDriftError + PartialHunkError counts in the dec 14 run
were probably caused by THIS, not by actual model errors. so the previous
"all failed" wasn't fully diagnostic of agent quality — partly the harness
was misjudging the diffs.

## jan 6

second harness bug: pytest not on PATH because the test_command runs in a
shell that doesn't have the venv. fixed by prepending the python's bin dir.
took longer than it should have because Path(sys.executable).resolve()
follows the venv-symlink to the system python and gives you the wrong dir.
NEVER resolve venv pythons.

## jan 24

real eval finally. see results/run2_notes.md for the actual numbers and what
i made of them. tldr: tool layer matters, scaffold doesn't (in this batch),
but n is small enough that another run could flip the scaffold result. multi-
file scaffold question is unanswered until i have more multi-file fixtures.

## next thing

run on the full 12-task set once batch 2 fixtures (4 fastapi PRs) are merged
into the harness. that bumps n from 32-per-side to 64-per-side and adds
multi-file tasks. i'd want the multi-file scaffold gap to be more than ±3pp
before claiming planner helps there.

## may 4

still haven't run the second eval pass — life. batch 2 fastapi fixtures are
in the repo but haven't been folded into a fresh trace_run3 yet. budget for
it next weekend if i can.

also: reading back through the dec/jan notes, the bug-then-fix density in
this repo is high. not a brag — those bugs ate >$5 of api budget combined
to surface. the lesson is "smoke-test the harness against a known-good fix
before spending real money on a model loop." which i already believed but
apparently still had to learn the hard way.
