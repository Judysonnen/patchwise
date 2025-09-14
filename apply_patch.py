#!/usr/bin/env python3
# quick thing to apply unified diffs. just textbook format for now.
import argparse, re, sys
from pathlib import Path

HUNK = re.compile(r'^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@')


def parse(text):
    files, current = [], None
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        if lines[i].startswith('--- '):
            new_path = lines[i + 1][4:]
            if new_path.startswith('b/'):
                new_path = new_path[2:]
            current = {'path': new_path, 'hunks': []}
            files.append(current)
            i += 2
            continue
        m = HUNK.match(lines[i])
        if m:
            hunk = {'old_start': int(m.group(1)), 'lines': []}
            i += 1
            while i < len(lines) and not lines[i].startswith('@@') and not lines[i].startswith('--- '):
                hunk['lines'].append(lines[i])
                i += 1
            current['hunks'].append(hunk)
            continue
        i += 1
    return files


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
    for f in parse(text):
        p = Path(root) / f['path']
        lines = p.read_text().splitlines()
        for h in reversed(f['hunks']):
            lines = apply_hunk(lines, h)
        p.write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('diff_file', nargs='?')
    ap.add_argument('--root', default='.')
    a = ap.parse_args()
    text = Path(a.diff_file).read_text() if a.diff_file else sys.stdin.read()
    apply_diff(text, a.root)
