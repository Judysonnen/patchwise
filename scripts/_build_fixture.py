#!/usr/bin/env python3
"""one-shot helper: pulls a PR's test file contents and writes a fixture skeleton.

usage:
    python scripts/_build_fixture.py <repo> <pr_num> <slug> "<short bug description>"

prints the fixture path on success. test file selection: any file under a
tests/ or test/ directory that's MODIFIED or ADDED in the PR.
"""
from __future__ import annotations

import base64
import json
import subprocess
import sys
from pathlib import Path


def gh_json(*args: str) -> dict:
    out = subprocess.run(
        ["gh", *args, "--jq", "."],
        check=True, capture_output=True, text=True,
    ).stdout
    return json.loads(out)


def fetch_file(repo: str, ref: str, path: str) -> str:
    out = subprocess.run(
        ["gh", "api", f"repos/{repo}/contents/{path}?ref={ref}", "--jq", ".content"],
        check=True, capture_output=True, text=True,
    ).stdout
    return base64.b64decode(out.strip()).decode("utf-8")


def is_test_path(p: str) -> bool:
    parts = p.split("/")
    return any(part in ("tests", "test") for part in parts)


def main():
    repo, pr_num, slug, summary = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    repo_root = Path(__file__).resolve().parent.parent
    out_dir = repo_root / "harness" / "tasks" / slug
    if out_dir.exists():
        print(f"already exists: {out_dir}", file=sys.stderr)
        sys.exit(2)

    pr = gh_json(
        "pr", "view", pr_num, "--repo", repo,
        "--json", "number,title,baseRefOid,mergeCommit,files,url",
    )
    base_sha = pr["baseRefOid"]
    merge_sha = pr["mergeCommit"]["oid"]

    source_files = []
    test_files = []
    for f in pr["files"]:
        path = f["path"]
        if path.endswith((".rst", ".md")) and ("CHANGES" in path or "CHANGELOG" in path or "changelog" in path):
            continue  # skip changelog files — agent doesn't need to touch
        if is_test_path(path):
            test_files.append(path)
        else:
            source_files.append(path)

    out_dir.mkdir(parents=True)
    (out_dir / "tests").mkdir()

    # fetch test files at merge sha (these are what the harness will apply
    # into the worktree to score the agent's fix)
    for tf in test_files:
        content = fetch_file(repo, merge_sha, tf)
        # flatten the path: tests/foo/bar.py -> tests/bar.py for the fixture,
        # but record original path so the harness can place it back correctly
        out_path = out_dir / "tests" / Path(tf).name
        out_path.write_text(content)

    meta = {
        "url": pr["url"],
        "repo": repo,
        "pr_number": int(pr_num),
        "base_sha": base_sha,
        "source_files": source_files,
        "test_files": test_files,
        "summary": summary,
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")

    # TODO: also pull the source-file before-state for offline-only fixtures.
    # right now we lean on the harness to clone+checkout at run time. fine
    # for evals on a connected box but slow on first run.
    print(out_dir)


if __name__ == "__main__":
    main()
