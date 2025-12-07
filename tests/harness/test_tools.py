"""tool implementations against a fake workspace."""
from __future__ import annotations

from pathlib import Path

from harness.model_client import ToolCall
from harness.tools import (
    _apply_patch_naive,
    _apply_patch_tolerant,
    _list_files,
    _read_file,
    _search_repo,
    make_dispatch,
)


def test_read_file_returns_contents(tmp_path):
    (tmp_path / "x.py").write_text("hello\n")
    assert _read_file(tmp_path, "x.py") == "hello\n"


def test_read_file_reports_missing(tmp_path):
    assert "does not exist" in _read_file(tmp_path, "nope.py")


def test_list_files_recursive_skips_hidden(tmp_path):
    (tmp_path / "a.py").write_text("")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.py").write_text("")
    (tmp_path / ".hidden").mkdir()
    (tmp_path / ".hidden" / "c.py").write_text("")
    out = _list_files(tmp_path)
    assert "a.py" in out
    assert "sub/b.py" in out
    assert "c.py" not in out  # hidden dirs filtered


def test_search_repo_finds_lines(tmp_path):
    (tmp_path / "x.py").write_text("import sys\nimport os\n")
    out = _search_repo(tmp_path, "import os")
    assert "x.py:2: import os" in out


def test_search_repo_no_match(tmp_path):
    (tmp_path / "x.py").write_text("nothing\n")
    out = _search_repo(tmp_path, "needle")
    assert "no matches" in out


def test_apply_patch_tolerant_succeeds_on_clean_diff(tmp_path):
    (tmp_path / "x.py").write_text("def f():\n    return 1\n")
    diff = (
        "--- a/x.py\n+++ b/x.py\n@@ -1,2 +1,2 @@\n def f():\n-    return 1\n+    return 2\n"
    )
    assert _apply_patch_tolerant(tmp_path, diff) == "ok"
    assert (tmp_path / "x.py").read_text() == "def f():\n    return 2\n"


def test_apply_patch_tolerant_surfaces_fenced_error(tmp_path):
    (tmp_path / "x.py").write_text("def f():\n    return 1\n")
    diff = (
        "```diff\n--- a/x.py\n+++ b/x.py\n@@ -1,2 +1,2 @@\n"
        " def f():\n-    return 1\n+    return 2\n```\n"
    )
    out = _apply_patch_tolerant(tmp_path, diff)
    assert out.startswith("error (FencedDiffError)")


def test_naive_vs_tolerant_on_truncated_hunk(tmp_path):
    """the actual differentiator between variants: tolerant raises a structured
    PartialHunkError so the agent can retry; naive applies a half-hunk and
    silently corrupts the file. (fences turn out to be a non-issue — naive
    happens to silently strip them.)"""
    (tmp_path / "x.py").write_text("a\nb\nc\nd\ne\n")
    truncated = (
        "--- a/x.py\n+++ b/x.py\n@@ -1,3 +1,4 @@\n"
        " a\n+inserted\n b\n"  # declares 3 old, only has 2; classic mid-stream cutoff
    )
    tolerant_out = _apply_patch_tolerant(tmp_path, truncated)
    assert tolerant_out.startswith("error (PartialHunkError)")
    # file untouched after tolerant rejection
    assert (tmp_path / "x.py").read_text() == "a\nb\nc\nd\ne\n"

    # naive applies the partial hunk, silently producing wrong content
    naive_out = _apply_patch_naive(tmp_path, truncated)
    assert naive_out == "ok"
    after_naive = (tmp_path / "x.py").read_text()
    assert after_naive != "a\nb\nc\nd\ne\n", "naive should have written something"
    # specifically: c/d/e are gone, replaced or shifted
    assert "inserted" in after_naive


def test_dispatch_routes_apply_patch_to_chosen_variant(tmp_path):
    (tmp_path / "x.py").write_text("def f():\n    return 1\n")
    diff = (
        "--- a/x.py\n+++ b/x.py\n@@ -1,2 +1,2 @@\n def f():\n-    return 1\n+    return 2\n"
    )
    dispatch = make_dispatch(tmp_path, "true", "tolerant")
    out = dispatch(ToolCall(name="apply_patch", arguments={"diff": diff}, call_id="c1"))
    assert out == "ok"


def test_dispatch_unknown_tool_returns_error():
    dispatch = make_dispatch(Path("/tmp"), "true", "tolerant")
    out = dispatch(ToolCall(name="nonsense", arguments={}, call_id="c1"))
    assert out.startswith("error: unknown tool")
