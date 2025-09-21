import re

HUNK = re.compile(r'^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@')


def parse_diff(text):
    """parse a unified diff into a list of file dicts.

    each file dict is {'path': str, 'hunks': [{'old_start': int, 'lines': [str]}]}.
    only handles textbook unified diff right now.
    """
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
