"""sanity check: real PR fix diffs apply cleanly via BOTH apply_patch variants.

if either variant rejects a known-good diff, that's a harness bug — agents
can't be expected to do better than the official fix. catching this saves
hours of debugging "why did all my eval trajectories fail" later.

if/when this fails, look at:
  - did the parser learn to dislike a header style it previously accepted?
  - did _check_complete tighten its count semantics in a backward-incompatible
    way?
  - did fence detection start firing on text that contains backticks?
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from harness.tools import _apply_patch_naive, _apply_patch_tolerant

SANITY = Path(__file__).parent / "sanity_diffs"


def _set_up_workspace(tmp_path: Path, before_path: Path, target_rel: str) -> Path:
    """copy `before_path` into a workspace at `target_rel`. returns the
    workspace root."""
    ws = tmp_path / "ws"
    ws.mkdir(parents=True, exist_ok=True)
    target = ws / target_rel
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(before_path, target)
    return ws


def test_requests_pr_6629_fix_applies_via_tolerant(tmp_path):
    ws = _set_up_workspace(
        tmp_path,
        SANITY / "requests_exceptions_before.py",
        "src/requests/exceptions.py",
    )
    diff = (SANITY / "requests_exceptions_fix.diff").read_text()
    out = _apply_patch_tolerant(ws, diff)
    assert out == "ok", f"tolerant rejected a known-good diff: {out}"
    after = (ws / "src/requests/exceptions.py").read_text()
    assert "def __reduce__" in after, "fix not actually applied"
    assert "CompatJSONDecodeError.__reduce__(self)" in after


def test_requests_pr_6629_fix_applies_via_naive(tmp_path):
    """sanity floor: naive should also accept this clean unified diff. if
    naive rejects a textbook diff, the eval baseline is meaningless."""
    ws = _set_up_workspace(
        tmp_path,
        SANITY / "requests_exceptions_before.py",
        "src/requests/exceptions.py",
    )
    diff = (SANITY / "requests_exceptions_fix.diff").read_text()
    out = _apply_patch_naive(ws, diff)
    assert out == "ok", f"naive rejected a known-good diff: {out}"
    after = (ws / "src/requests/exceptions.py").read_text()
    assert "def __reduce__" in after


def test_tolerant_applier_matches_pr_after_state_byte_for_byte(tmp_path):
    """tolerant should produce exactly the file content the merged PR landed.
    naive can't be trusted to do this on diffs with blank lines (drops them)
    so we don't compare naive here — a separate test confirms naive at least
    accepts the diff structurally."""
    ws = _set_up_workspace(
        tmp_path,
        SANITY / "requests_exceptions_before.py",
        "src/requests/exceptions.py",
    )
    diff = (SANITY / "requests_exceptions_fix.diff").read_text()
    assert _apply_patch_tolerant(ws, diff) == "ok"
    expected = (SANITY / "requests_exceptions_after.py").read_text()
    actual = (ws / "src/requests/exceptions.py").read_text()
    assert actual == expected
