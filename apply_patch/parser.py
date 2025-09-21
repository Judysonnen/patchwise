import re

HUNK = re.compile(r'^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@')
GIT_HEADER = re.compile(r'^diff --git a/(\S+) b/(\S+)')

# TODO: this whole thing is one big ad-hoc state machine. should probably
# rewrite as a proper line classifier (header / hunk-header / hunk-body / noise)
# but it works on what i've thrown at it so far.


def parse_diff(text):
    """parse a unified diff. handles plain unified diff and `diff --git` headers."""
    files, current = [], None
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]

        # `diff --git` header. skip it; --- / +++ pair below carries the canonical path.
        if GIT_HEADER.match(line):
            i += 1
            continue

        if line.startswith('--- '):
            # +++ might not be exactly i+1: there can be `index ...` or `new file mode ...`
            # lines between them. cheap fix: scan forward up to 4 lines.
            new_path = None
            for j in range(i + 1, min(i + 5, len(lines))):
                if lines[j].startswith('+++ '):
                    new_path = lines[j][4:]
                    i = j + 1
                    break
            if new_path is None:
                i += 1
                continue
            if new_path.startswith('b/'):
                new_path = new_path[2:]
            current = {'path': new_path, 'hunks': []}
            files.append(current)
            continue

        m = HUNK.match(line)
        if m and current is not None:
            hunk = {'old_start': int(m.group(1)), 'lines': []}
            i += 1
            while i < len(lines) and not lines[i].startswith('@@') \
                    and not lines[i].startswith('--- ') \
                    and not GIT_HEADER.match(lines[i]):
                hunk['lines'].append(lines[i])
                i += 1
            current['hunks'].append(hunk)
            continue

        i += 1
    return files
