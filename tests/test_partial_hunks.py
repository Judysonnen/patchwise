import pytest

from apply_patch import apply_diff
from apply_patch.errors import PartialHunkError


def test_truncated_hunk_synthesized(tmp_path):
    """small synthesized case: @@ header says 3 old / 4 new, body only has
    2 old + 1 new. classic mid-response truncation shape."""
    f = tmp_path / "x.py"
    f.write_text("a\nb\nc\nd\ne\n")
    diff = (
        "--- a/x.py\n"
        "+++ b/x.py\n"
        "@@ -1,3 +1,4 @@\n"
        " a\n"
        "+inserted\n"
        " b\n"
    )
    with pytest.raises(PartialHunkError) as exc:
        apply_diff(diff, root=tmp_path)
    assert exc.value.path == "x.py"
