"""tool catalog the agent can call.

the apply_patch tool has two implementations selectable per run:

  - "tolerant": uses our apply_patch.apply_diff (handles fenced markdown,
    line drift, partial hunks)
  - "naive": uses git apply, no recovery — fails on the first irregular diff
    the model produces

swapping them across runs is what isolates the "tool layer" lever in the eval.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable


def _shell_env_with_venv() -> dict:
    """see runner._test_env — same reason. don't .resolve() the python path."""
    env = dict(os.environ)
    venv_bin = str(Path(sys.executable).parent)
    env["PATH"] = venv_bin + os.pathsep + env.get("PATH", "")
    return env

from apply_patch import apply_diff as tolerant_apply_diff
from apply_patch.errors import ApplyPatchError

from .model_client import ToolCall, ToolDef


# ---------------------------------------------------------------------------
# tool definitions exposed to the model
# ---------------------------------------------------------------------------

TOOLS: list[ToolDef] = [
    ToolDef(
        name="read_file",
        description="Read a file from the workspace and return its full contents.",
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Path relative to repo root."}},
            "required": ["path"],
        },
    ),
    ToolDef(
        name="list_files",
        description="List files in a directory (recursive). Returns at most 200 entries.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory relative to repo root.", "default": "."}
            },
        },
    ),
    ToolDef(
        name="search_repo",
        description="grep-like search through .py files. Returns matching lines with file:line: prefix.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Substring to search for."},
                "file_glob": {"type": "string", "description": "Glob to limit search.", "default": "**/*.py"},
            },
            "required": ["query"],
        },
    ),
    ToolDef(
        name="apply_patch",
        description=(
            "Apply a unified diff to the workspace. The diff body must use unified "
            "format with --- a/path and +++ b/path headers and @@ hunk markers. "
            "Returns 'ok' on success or a structured error describing what went wrong."
        ),
        parameters={
            "type": "object",
            "properties": {"diff": {"type": "string", "description": "The unified diff text."}},
            "required": ["diff"],
        },
    ),
    ToolDef(
        name="run_tests",
        description="Run the task's test command. Returns the test output and a final pass/fail line.",
        parameters={"type": "object", "properties": {}},
    ),
]


# ---------------------------------------------------------------------------
# implementations
# ---------------------------------------------------------------------------


def _read_file(workspace: Path, path: str) -> str:
    p = workspace / path
    if not p.exists():
        return f"error: {path} does not exist"
    if not p.is_file():
        return f"error: {path} is not a file"
    text = p.read_text(errors="replace")
    if len(text) > 50_000:
        return text[:50_000] + f"\n\n... [truncated, file is {len(text)} chars total]"
    return text


def _list_files(workspace: Path, path: str = ".") -> str:
    base = workspace / path
    if not base.exists():
        return f"error: {path} does not exist"
    out = []
    for p in sorted(base.rglob("*")):
        if any(part.startswith(".") for part in p.relative_to(workspace).parts):
            continue
        if p.is_dir():
            continue
        out.append(str(p.relative_to(workspace)))
        if len(out) >= 200:
            out.append(f"... [{200} entries shown, more present]")
            break
    return "\n".join(out)


def _search_repo(workspace: Path, query: str, file_glob: str = "**/*.py") -> str:
    matches = []
    for p in workspace.glob(file_glob):
        if not p.is_file():
            continue
        if any(part.startswith(".") for part in p.relative_to(workspace).parts):
            continue
        try:
            text = p.read_text(errors="replace")
        except Exception:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if query in line:
                matches.append(f"{p.relative_to(workspace)}:{i}: {line}")
                if len(matches) >= 100:
                    break
        if len(matches) >= 100:
            matches.append("... [100+ matches, refine query]")
            break
    return "\n".join(matches) if matches else f"(no matches for {query!r})"


def _apply_patch_tolerant(workspace: Path, diff: str) -> str:
    try:
        tolerant_apply_diff(diff, root=workspace)
    except ApplyPatchError as e:
        # surface the specific error type so the agent can react
        return f"error ({type(e).__name__}): {e}"
    except Exception as e:
        return f"error ({type(e).__name__}): {e}"
    return "ok"


_NAIVE_HUNK = re.compile(r'^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@')


def _apply_patch_naive(workspace: Path, diff: str) -> str:
    """deliberately bare-bones diff applier. no fence detection, no drift recovery,
    no truncation detection. mirrors what a fresh weekend hack looks like — and
    what most off-the-shelf simple appliers do.

    used as the BASELINE in the eval to measure what the tolerant applier is
    actually buying.
    """
    try:
        files: list[dict] = []
        current = None
        lines = diff.splitlines()
        i = 0
        while i < len(lines):
            if lines[i].startswith('--- '):
                if i + 1 >= len(lines):
                    return "error (MalformedDiff): truncated header"
                new_path = lines[i + 1][4:]
                if new_path.startswith('b/'):
                    new_path = new_path[2:]
                current = {'path': new_path, 'hunks': []}
                files.append(current)
                i += 2
                continue
            m = _NAIVE_HUNK.match(lines[i])
            if m and current is not None:
                hunk = {'old_start': int(m.group(1)), 'lines': []}
                i += 1
                while i < len(lines) and not lines[i].startswith('@@') \
                        and not lines[i].startswith('--- '):
                    hunk['lines'].append(lines[i])
                    i += 1
                current['hunks'].append(hunk)
                continue
            i += 1
        if not files:
            return "error (MalformedDiff): no file headers found"
        for f in files:
            p = workspace / f['path']
            if not p.exists():
                return f"error (MalformedDiff): {f['path']} does not exist"
            file_lines = p.read_text().splitlines()
            for h in reversed(f['hunks']):
                out = list(file_lines[:h['old_start'] - 1])
                cur = h['old_start'] - 1
                for hl in h['lines']:
                    if hl.startswith(' '):
                        out.append(file_lines[cur])
                        cur += 1
                    elif hl.startswith('-'):
                        cur += 1
                    elif hl.startswith('+'):
                        out.append(hl[1:])
                out.extend(file_lines[cur:])
                file_lines = out
            p.write_text('\n'.join(file_lines) + '\n')
    except Exception as e:
        return f"error ({type(e).__name__}): {e}"
    return "ok"


def _run_tests(workspace: Path, test_command: str, timeout: int = 120) -> str:
    try:
        result = subprocess.run(
            test_command, shell=True, cwd=workspace,
            capture_output=True, text=True, timeout=timeout,
            env=_shell_env_with_venv(),
        )
    except subprocess.TimeoutExpired:
        return "error: test command timed out"
    body = (result.stdout + result.stderr)[-8000:]
    final = "PASS" if result.returncode == 0 else "FAIL"
    return f"{body}\n\n[exit={result.returncode}, {final}]"


# ---------------------------------------------------------------------------
# dispatch builder — captures workspace + apply_patch variant in a closure
# ---------------------------------------------------------------------------


def make_dispatch(
    workspace: Path,
    test_command: str,
    apply_patch_variant: str,  # "tolerant" or "naive"
) -> Callable[[ToolCall], str]:
    if apply_patch_variant == "tolerant":
        apply_impl = _apply_patch_tolerant
    elif apply_patch_variant == "naive":
        apply_impl = _apply_patch_naive
    else:
        raise ValueError(f"unknown apply_patch_variant: {apply_patch_variant!r}")

    def dispatch(call: ToolCall) -> str:
        args = call.arguments or {}
        if call.name == "read_file":
            return _read_file(workspace, args.get("path", ""))
        if call.name == "list_files":
            return _list_files(workspace, args.get("path", "."))
        if call.name == "search_repo":
            return _search_repo(workspace, args.get("query", ""), args.get("file_glob", "**/*.py"))
        if call.name == "apply_patch":
            return apply_impl(workspace, args.get("diff", ""))
        if call.name == "run_tests":
            return _run_tests(workspace, test_command)
        return f"error: unknown tool {call.name!r}"

    return dispatch
