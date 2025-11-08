"""per-task git worktree wrapper.

each trial gets a fresh worktree off the task's `before` ref. between trials
we `git reset --hard` + `git clean -fdx` rather than recreate the worktree —
recreating costs ~3-4s per task on a real run and we do dozens of trials.
"""
from __future__ import annotations

import shutil
import subprocess
import uuid
from pathlib import Path


class WorktreeError(RuntimeError):
    pass


class Worktree:
    def __init__(self, source_repo: Path, base_ref: str = "HEAD"):
        self.source_repo = Path(source_repo).resolve()
        self.base_ref = base_ref
        self.path: Path | None = None
        self._name = f"patchwise-wt-{uuid.uuid4().hex[:8]}"

    def create(self, parent_dir: Path) -> Path:
        target = Path(parent_dir).resolve() / self._name
        try:
            subprocess.run(
                ["git", "-C", str(self.source_repo), "worktree", "add",
                 "--detach", str(target), self.base_ref],
                check=True, capture_output=True, text=True,
            )
        except subprocess.CalledProcessError as e:
            raise WorktreeError(f"git worktree add failed: {e.stderr.strip()}") from e
        self.path = target
        return self.path

    def reset(self) -> None:
        """undo any changes the agent made; bring worktree back to base_ref."""
        if self.path is None:
            raise WorktreeError("worktree not created")
        subprocess.run(
            ["git", "-C", str(self.path), "reset", "--hard", self.base_ref],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(self.path), "clean", "-fdx"],
            check=True, capture_output=True,
        )

    def remove(self) -> None:
        if self.path is None:
            return
        # `worktree remove --force` may fail if the worktree was already
        # cleaned up out from under us (e.g. parent_dir was a tmpdir that
        # got nuked). don't crash on cleanup.
        subprocess.run(
            ["git", "-C", str(self.source_repo), "worktree", "remove",
             "--force", str(self.path)],
            capture_output=True,
        )
        if self.path.exists():
            shutil.rmtree(self.path, ignore_errors=True)
        self.path = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.remove()
