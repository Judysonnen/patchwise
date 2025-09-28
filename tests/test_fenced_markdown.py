from pathlib import Path

import pytest

from apply_patch import apply_diff
from apply_patch.errors import FencedDiffError

FIXTURES = Path(__file__).parent / "fixtures"


def test_anthropic_fenced_diff_raises_fenced_error(tmp_path):
    text = (FIXTURES / "fenced_markdown_anthropic.txt").read_text()
    with pytest.raises(FencedDiffError):
        apply_diff(text, root=tmp_path)
