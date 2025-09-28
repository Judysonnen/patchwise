from pathlib import Path

import pytest

from apply_patch import apply_diff
from apply_patch.errors import FencedDiffError

FIXTURES = Path(__file__).parent / "fixtures"


def test_anthropic_fenced_diff_raises_fenced_error(tmp_path):
    text = (FIXTURES / "fenced_markdown_anthropic.txt").read_text()
    with pytest.raises(FencedDiffError):
        apply_diff(text, root=tmp_path)


def test_anthropic_fenced_diff_carries_unwrapped_content(tmp_path):
    text = (FIXTURES / "fenced_markdown_anthropic.txt").read_text()
    with pytest.raises(FencedDiffError) as excinfo:
        apply_diff(text, root=tmp_path)
    err = excinfo.value
    assert err.fence_marker.startswith("```")
    # the unwrapped content should start with the actual diff header,
    # not the prose preamble
    assert err.unwrapped.startswith("--- a/click/core.py")
    assert "+++ b/click/core.py" in err.unwrapped
