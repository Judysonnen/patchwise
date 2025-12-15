"""clone an upstream repo into ~/.cache/patchwise/repos/ and check out a sha.

we cache one shallow clone per (repo) and switch between SHAs via `git fetch
{sha} && git checkout {sha}`. saves multi-minute clones on repeat eval runs.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def cache_root() -> Path:
    root = Path(os.environ.get("PATCHWISE_CACHE", Path.home() / ".cache" / "patchwise"))
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_repo_dir(repo: str) -> Path:
    return cache_root() / "repos" / repo.replace("/", "__")


def ensure_clone(repo: str) -> Path:
    """clone the repo if not cached. returns the local repo path."""
    target = _safe_repo_dir(repo)
    if target.exists() and (target / ".git").exists():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        shutil.rmtree(target)  # corrupt or partial; re-clone
    url = f"https://github.com/{repo}.git"
    # full clone (not shallow) because we may need to check out arbitrary
    # historical SHAs. this is more bytes but only happens once per repo.
    subprocess.run(
        ["git", "clone", "--quiet", url, str(target)],
        check=True, capture_output=True, text=True,
    )
    # TODO this is a hack — pytest will ImportError on `import requests` etc.
    # if the upstream package isn't installed in our env. install it now so
    # tests can at least find the module. doesn't handle [test] extras yet,
    # so async-test plugins etc. are still missing. clean this up.
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-q", "-e", str(target)],
        capture_output=True,
    )
    return target


def checkout(repo_path: Path, sha: str) -> None:
    """check out a specific sha in an already-cloned repo. fetches first if missing."""
    rev = subprocess.run(
        ["git", "-C", str(repo_path), "rev-parse", "--verify", sha + "^{commit}"],
        capture_output=True, text=True,
    )
    if rev.returncode != 0:
        # sha not present locally — fetch it from origin
        subprocess.run(
            ["git", "-C", str(repo_path), "fetch", "--quiet", "origin", sha],
            check=True, capture_output=True, text=True,
        )
    subprocess.run(
        ["git", "-C", str(repo_path), "checkout", "--quiet", "--detach", sha],
        check=True, capture_output=True, text=True,
    )
    subprocess.run(
        ["git", "-C", str(repo_path), "reset", "--quiet", "--hard", sha],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repo_path), "clean", "-fdx", "--quiet"],
        check=True, capture_output=True,
    )
