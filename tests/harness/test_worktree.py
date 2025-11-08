"""worktree tests use a real git repo set up in tmp_path."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from harness.worktree import Worktree


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True, capture_output=True, text=True,
    ).stdout


@pytest.fixture
def source_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "src"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "test")
    (repo / "x.py").write_text("def f():\n    return 1\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "initial")
    return repo


def test_create_yields_a_directory_at_base_ref(source_repo, tmp_path):
    parent = tmp_path / "wt"
    parent.mkdir()
    wt = Worktree(source_repo)
    path = wt.create(parent)
    try:
        assert path.exists()
        assert (path / "x.py").read_text() == "def f():\n    return 1\n"
    finally:
        wt.remove()


def test_reset_undoes_local_modifications(source_repo, tmp_path):
    parent = tmp_path / "wt"
    parent.mkdir()
    wt = Worktree(source_repo)
    path = wt.create(parent)
    try:
        # simulate the agent making a change
        (path / "x.py").write_text("def f():\n    return 999\n")
        (path / "garbage.txt").write_text("untracked file\n")
        wt.reset()
        assert (path / "x.py").read_text() == "def f():\n    return 1\n"
        assert not (path / "garbage.txt").exists()
    finally:
        wt.remove()


def test_remove_is_idempotent(source_repo, tmp_path):
    parent = tmp_path / "wt"
    parent.mkdir()
    wt = Worktree(source_repo)
    wt.create(parent)
    wt.remove()
    wt.remove()  # should not raise
