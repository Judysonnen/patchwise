import pytest

from apply_patch import apply_diff
from apply_patch.errors import LineDriftError


def test_drift_beyond_window_raises(tmp_path):
    """drift is larger than WINDOW so fuzzy match can't recover. bail
    rather than apply at the wrong place."""
    f = tmp_path / "x.py"
    # 30 lines of preamble, well beyond WINDOW=20
    prefix = "\n".join(f"# line {i}" for i in range(30))
    f.write_text(prefix + "\ndef foo():\n    return 1\n")
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


def test_modest_drift_is_recovered_with_warning(tmp_path):
    """diff was generated against a slightly older file: 5 lines were inserted
    above the hunk's region. fuzzy match should find the unique context window
    and apply, with a warning recorded."""
    f = tmp_path / "x.py"
    f.write_text(
        "# license header\n"
        "# license header line 2\n"
        "# license header line 3\n"
        "# license header line 4\n"
        "# license header line 5\n"
        "def foo():\n"
        "    return 1\n"
    )
    diff = (
        "--- a/x.py\n"
        "+++ b/x.py\n"
        "@@ -1,2 +1,2 @@\n"
        " def foo():\n"
        "-    return 1\n"
        "+    return 2\n"
    )
    warnings = []
    apply_diff(diff, root=tmp_path, warnings=warnings)
    assert f.read_text().endswith("def foo():\n    return 2\n")
    assert len(warnings) == 1
    assert "shifted to 6" in warnings[0]


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
