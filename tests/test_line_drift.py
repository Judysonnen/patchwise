import pytest

from apply_patch import apply_diff
from apply_patch.errors import LineDriftError


def test_drifted_hunk_raises_line_drift_error(tmp_path):
    """diff was generated against an older version of the file. context lines
    point at line 1 but the actual content at line 1 is different now."""
    f = tmp_path / "x.py"
    f.write_text("# new comment added at top\n"
                 "# another new comment\n"
                 "def foo():\n"
                 "    return 1\n")
    diff = (
        "--- a/x.py\n"
        "+++ b/x.py\n"
        "@@ -1,2 +1,2 @@\n"
        " def foo():\n"
        "-    return 1\n"
        "+    return 2\n"
    )
    with pytest.raises(LineDriftError) as exc:
        apply_diff(diff, root=tmp_path)
    assert exc.value.path == "x.py"
    assert exc.value.hunk_old_start == 1


def test_clean_diff_still_applies(tmp_path):
    """sanity check: when context matches, apply still works."""
    f = tmp_path / "x.py"
    f.write_text("def foo():\n    return 1\n")
    diff = (
        "--- a/x.py\n"
        "+++ b/x.py\n"
        "@@ -1,2 +1,2 @@\n"
        " def foo():\n"
        "-    return 1\n"
        "+    return 2\n"
    )
    apply_diff(diff, root=tmp_path)
    assert f.read_text() == "def foo():\n    return 2\n"
