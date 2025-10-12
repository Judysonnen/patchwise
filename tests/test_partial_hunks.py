from pathlib import Path

import pytest

from apply_patch import apply_diff
from apply_patch.errors import PartialHunkError

FIXTURES = Path(__file__).parent / "fixtures"


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


def test_claude_truncated_response(tmp_path):
    """real fixture: claude's response was cut off mid-hunk while adding
    log statements to fastapi's get_request_handler. the @@ header declares
    28 new lines but only 27 actually arrived."""
    text = (FIXTURES / "partial_hunk_anthropic.txt").read_text()
    with pytest.raises(PartialHunkError) as exc:
        apply_diff(text, root=tmp_path)
    assert exc.value.path == "fastapi/routing.py"
    # specific count matters: if we say "got 26" we silently dropped the
    # last (truncated) line, which would be a parser bug.
    assert "declared 28 new lines, got 27" in str(exc.value)
