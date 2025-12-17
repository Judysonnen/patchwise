"""end-to-end smoke test for the runner using a mocked model client.

verifies the wiring (task loading -> repo clone -> test apply -> scaffold
loop -> tool dispatch -> trace events -> outcome) without spending API budget.
the actual eval (with real models) gets exercised by scripts/run_eval.py.

skipped when network is restricted (CI without external git access) by
checking for the patchwise cache flag.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from harness.model_client import Completion, Message, ToolCall, ToolDef
from harness.runner import Runner
from harness.scaffolds.react import run_react
from harness.task import load_task
from harness.trace_store import TraceStore


REQUIRES_NETWORK = pytest.mark.skipif(
    os.environ.get("PATCHWISE_E2E_NETWORK") != "1",
    reason="requires network for git clone of upstream repo (set PATCHWISE_E2E_NETWORK=1)",
)


class FakeApplyPatchModel:
    """fake client that just emits one apply_patch tool call then stops.
    enough to exercise the orchestrator without an API key."""

    name = "fake"

    def __init__(self, diff_to_emit: str):
        self.diff = diff_to_emit
        self._calls = 0

    def complete(self, messages, tools=None):
        self._calls += 1
        if self._calls == 1:
            tc = ToolCall(name="apply_patch", arguments={"diff": self.diff}, call_id="c1")
            return Completion(text="trying this patch", tool_calls=[tc], raw={})
        # second call: no more tool calls — react loop exits
        return Completion(text="done", tool_calls=[], raw={})


def test_runner_records_trace_events_and_invokes_tools(tmp_path):
    """fixture-free smoke test: build a tiny synthetic Task, run the react
    scaffold with a fake model that calls apply_patch once, verify trace
    events landed."""
    from harness.task import Task

    # synthetic 'workspace' (we'll point repo_path at it via monkey, see below)
    workspace = tmp_path / "fake_repo"
    workspace.mkdir()
    (workspace / "x.py").write_text("def f():\n    return 1\n")

    # build an in-memory fake task that bypasses repo_cache by pointing
    # source_files at a tmp file. we patch ensure_clone+checkout below.
    task = Task(
        slug="fake_task",
        repo="fake/fake",
        base_sha="HEAD",
        source_files=["x.py"],
        test_files=[],
        test_command="true",  # always passes — exercises the success path
        prompt="change return value to 2",
        difficulty="easy",
        multi_file=False,
        fixture_dir=tmp_path,
    )
    (tmp_path / "tests").mkdir()  # empty since test_files=[]

    db = tmp_path / "trace.sqlite"
    trace = TraceStore(db)

    # patch the runner's repo provisioning to point at our synthetic dir
    import harness.runner as runner_mod
    orig_clone = runner_mod.ensure_clone
    orig_checkout = runner_mod.checkout
    orig_install = runner_mod.ensure_installed
    runner_mod.ensure_clone = lambda repo: workspace
    runner_mod.checkout = lambda path, sha: None
    runner_mod.ensure_installed = lambda repo, sha, path: ""
    try:
        diff = (
            "--- a/x.py\n"
            "+++ b/x.py\n"
            "@@ -1,2 +1,2 @@\n"
            " def f():\n"
            "-    return 1\n"
            "+    return 2\n"
        )
        runner = Runner(
            task=task,
            scaffold=run_react,
            model=FakeApplyPatchModel(diff),
            trace=trace,
            apply_patch_variant="tolerant",
            max_steps=5,
        )
        result = runner.run("traj-1")
    finally:
        runner_mod.ensure_clone = orig_clone
        runner_mod.checkout = orig_checkout
        runner_mod.ensure_installed = orig_install
        trace.close()

    # patch was applied, the fake test_command 'true' returned 0, so success
    assert result.success is True
    assert (workspace / "x.py").read_text() == "def f():\n    return 2\n"

    # trace should contain start, completion, tool_result, completion, stop, outcome
    trace2 = TraceStore(db)
    events = list(trace2.replay_prefix("traj-1", up_to_step=10_000))
    types = [e["event_type"] for e in events]
    assert "start" in types
    assert "completion" in types
    assert "tool_result" in types
    assert "outcome" in types
    outcome_event = next(e for e in events if e["event_type"] == "outcome")
    assert outcome_event["payload"]["success"] is True
    trace2.close()


def test_runner_records_failure_when_tests_fail(tmp_path):
    """if the test command exits non-zero, the runner records success=False."""
    from harness.task import Task

    workspace = tmp_path / "fake_repo"
    workspace.mkdir()
    (workspace / "x.py").write_text("def f():\n    return 1\n")

    task = Task(
        slug="fake_task_fail",
        repo="fake/fake",
        base_sha="HEAD",
        source_files=["x.py"],
        test_files=[],
        test_command="false",  # always fails
        prompt="not actually solvable",
        difficulty="easy",
        multi_file=False,
        fixture_dir=tmp_path,
    )
    (tmp_path / "tests").mkdir()

    db = tmp_path / "trace.sqlite"
    trace = TraceStore(db)

    import harness.runner as runner_mod
    orig_clone = runner_mod.ensure_clone
    orig_checkout = runner_mod.checkout
    orig_install = runner_mod.ensure_installed
    runner_mod.ensure_clone = lambda repo: workspace
    runner_mod.checkout = lambda path, sha: None
    runner_mod.ensure_installed = lambda repo, sha, path: ""
    try:
        runner = Runner(
            task=task,
            scaffold=run_react,
            model=FakeApplyPatchModel(
                "--- a/x.py\n+++ b/x.py\n@@ -1,2 +1,2 @@\n def f():\n-    return 1\n+    return 1\n"
            ),
            trace=trace,
            apply_patch_variant="tolerant",
            max_steps=3,
        )
        result = runner.run("traj-fail")
    finally:
        runner_mod.ensure_clone = orig_clone
        runner_mod.checkout = orig_checkout
        runner_mod.ensure_installed = orig_install
        trace.close()

    assert result.success is False
