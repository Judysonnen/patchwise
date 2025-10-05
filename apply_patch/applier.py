import re
from pathlib import Path

from .errors import FencedDiffError, LineDriftError, MalformedDiffError
from .parser import parse_diff

FENCE = re.compile(r'^\s*```(?:diff|patch)?\s*$', re.MULTILINE)

# how far we look around the stated old_start when context doesn't match.
# 20 felt about right based on cases i had — "i edited a file then asked
# the model to diff the OLD version" usually drifts < 10 lines.
WINDOW = 20


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


def _verify_hunk(file_lines, hunk, path):
    """check that context and minus lines match the file at the hunk's stated position.

    raises LineDriftError if the @@ -X header points at a region whose content
    doesn't line up with what the diff expects.
    """
    cur = hunk['old_start'] - 1
    for hl in hunk['lines']:
        if hl.startswith(' ') or hl.startswith('-'):
            expected = hl[1:]
            if cur >= len(file_lines) or file_lines[cur] != expected:
                raise LineDriftError(path, hunk['old_start'])
            cur += 1


def _try_fuzzy_match(file_lines, hunk):
    """search for the hunk's context within +/- WINDOW of its stated old_start.

    returns the corrected (1-indexed) old_start if exactly one match found,
    else None. zero matches and multiple matches both return None — better
    to bail than to apply at the wrong place.
    """
    expected = []
    for hl in hunk['lines']:
        if hl.startswith(' ') or hl.startswith('-'):
            expected.append(hl[1:])
    if not expected:
        return None

    base = hunk['old_start'] - 1
    lo = max(0, base - WINDOW)
    hi = min(len(file_lines) - len(expected) + 1, base + WINDOW)
    matches = []
    for cand in range(lo, hi):
        if file_lines[cand:cand + len(expected)] == expected:
            matches.append(cand + 1)  # back to 1-indexed
    if len(matches) == 1:
        return matches[0]
    return None


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


def apply_diff(text, root='.', warnings=None):
    """apply a unified diff to a working tree.

    raises one of the apply_patch.errors classes on bad input. if `warnings`
    is a list, drift-corrected hunks append a string note to it (so callers
    can decide whether the apply was clean or limped through).
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
            try:
                _verify_hunk(lines, h, f['path'])
            except LineDriftError:
                new_start = _try_fuzzy_match(lines, h)
                if new_start is None:
                    raise
                if warnings is not None:
                    warnings.append(
                        f"line drift in {f['path']} at @@ -{h['old_start']}: "
                        f"shifted to {new_start}"
                    )
                h = dict(h, old_start=new_start)
            lines = apply_hunk(lines, h)
        p.write_text('\n'.join(lines) + '\n')
