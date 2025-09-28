import re
from pathlib import Path

from .errors import FencedDiffError, MalformedDiffError
from .parser import parse_diff

FENCE = re.compile(r'^\s*```(?:diff|patch)?\s*$', re.MULTILINE)


def _extract_fenced(text: str):
    """if text looks fenced around a diff, return (inner, marker). else None.

    we look for at least two ``` fence lines AND a --- header inside the
    fenced region. plain text containing the literal string ``` somewhere
    (e.g. in a docstring being patched) shouldn't false-positive.
    """
    fences = list(FENCE.finditer(text))
    if len(fences) < 2:
        return None
    inner = text[fences[0].end(): fences[1].start()].strip('\n')
    if not ('\n--- ' in inner or inner.lstrip().startswith('--- ')):
        return None
    marker = text[fences[0].start(): fences[0].end()].strip()
    return inner, marker


def apply_hunk(file_lines, hunk):
    out = list(file_lines[:hunk['old_start'] - 1])
    cur = hunk['old_start'] - 1
    for hl in hunk['lines']:
        if hl.startswith(' '):
            out.append(file_lines[cur])
            cur += 1
        elif hl.startswith('-'):
            cur += 1
        elif hl.startswith('+'):
            out.append(hl[1:])
    out.extend(file_lines[cur:])
    return out


def apply_diff(text, root='.'):
    """apply a unified diff to a working tree.

    raises one of the apply_patch.errors classes on bad input.
    """
    fenced = _extract_fenced(text)
    if fenced is not None:
        inner, marker = fenced
        raise FencedDiffError(fence_marker=marker, unwrapped=inner)
    files = parse_diff(text)
    if not files:
        raise MalformedDiffError("no files found in diff (empty or unrecognized format)")
    for f in files:
        p = Path(root) / f['path']
        lines = p.read_text().splitlines()
        for h in reversed(f['hunks']):
            lines = apply_hunk(lines, h)
        p.write_text('\n'.join(lines) + '\n')
