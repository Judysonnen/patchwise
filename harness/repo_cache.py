"""clone an upstream repo into ~/.cache/patchwise/repos/, check out a sha,
and install it (with test extras) into the current python env so pytest can
import the package.

caching:
  - one git clone per (repo), reused across SHAs via fetch + checkout
  - install state tracked per (repo, sha) in installed.json so we only
    `pip install -e .` when the SHA actually changes
"""
from __future__ import annotations

import json
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
    return target


# ---------------------------------------------------------------------------
# install state — pytest needs the upstream package importable in our env
# ---------------------------------------------------------------------------


def _install_registry() -> Path:
    return cache_root() / "installed.json"


def _read_installed() -> dict[str, str]:
    p = _install_registry()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def _write_installed(data: dict[str, str]) -> None:
    _install_registry().write_text(json.dumps(data, indent=2, sort_keys=True))


def _try_pip_install(repo_path: Path, extras: str) -> tuple[bool, str]:
    """attempt `pip install -e .{extras}`. returns (ok, stderr_tail).

    extras is like "[test]" or "[dev]" or "" (bare).
    """
    cmd = [sys.executable, "-m", "pip", "install", "-q", "-e", f".{extras}"]
    result = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True)
    return result.returncode == 0, (result.stderr or "")[-500:]


def ensure_installed(repo: str, sha: str, repo_path: Path) -> str:
    """install the upstream package + test extras into the current env.

    returns the extras spec that was successfully installed (e.g. "[test]"),
    or "" for a bare install. raises if no install succeeded.

    safe to call repeatedly; no-ops when installed.json already records this
    (repo, sha) as installed.
    """
    installed = _read_installed()
    key = repo
    if installed.get(key) == sha:
        return installed.get(key + "::extras", "")

    last_err = ""
    for extras in ("[test]", "[dev]", ""):
        ok, err = _try_pip_install(repo_path, extras)
        if ok:
            installed[key] = sha
            installed[key + "::extras"] = extras
            _write_installed(installed)
            return extras
        last_err = err

    raise RuntimeError(
        f"pip install of {repo} failed both with extras and without. "
        f"last stderr tail:\n{last_err}"
    )


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
