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


def test_chatgpt_fenced_diff_with_prose_preamble(tmp_path):
    """gpt wrapped its diff in ```diff fences AND added a paragraph of
    explanation before the fence. detection should still fire and the
    unwrapped content should not include the preamble."""
    text = (FIXTURES / "fenced_markdown_chatgpt.txt").read_text()
    with pytest.raises(FencedDiffError) as excinfo:
        apply_diff(text, root=tmp_path)
    err = excinfo.value
    assert err.unwrapped.startswith("--- a/requests/sessions.py")
    # explicit: preamble prose ("Sure — here's a unified diff...") must NOT
    # leak into the unwrapped diff
    assert "Sure" not in err.unwrapped
    assert "documentation-only" not in err.unwrapped


def test_gemini_fenced_diff(tmp_path):
    """gemini's preamble + ```diff fence variant. same shape as gpt's,
    different vendor — keeping a per-vendor case so a regression in one
    parser branch doesn't go unnoticed."""
    text = (FIXTURES / "fenced_markdown_gemini.txt").read_text()
    with pytest.raises(FencedDiffError) as excinfo:
        apply_diff(text, root=tmp_path)
    assert excinfo.value.unwrapped.startswith("--- a/client.py")


def test_bare_fence_no_language_tag(tmp_path):
    """some models emit ``` instead of ```diff. detection must fire on the
    bare fence too, not just the language-tagged variant."""
    text = (
        "```\n"
        "--- a/x.py\n"
        "+++ b/x.py\n"
        "@@ -1,1 +1,1 @@\n"
        "-old\n"
        "+new\n"
        "```\n"
    )
    with pytest.raises(FencedDiffError) as excinfo:
        apply_diff(text, root=tmp_path)
    assert excinfo.value.fence_marker == "```"
    assert excinfo.value.unwrapped.startswith("--- a/x.py")
