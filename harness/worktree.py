"""per-task git worktree wrapper. placeholder."""
from __future__ import annotations

from pathlib import Path


class Worktree:
    def __init__(self, source_repo: Path, base_ref: str = "HEAD"):
        self.source_repo = Path(source_repo)
        self.base_ref = base_ref
        self.path: Path | None = None

    def create(self, parent_dir: Path) -> Path:
        raise NotImplementedError("TODO")

    def reset(self) -> None:
        raise NotImplementedError("TODO")

    def remove(self) -> None:
        raise NotImplementedError("TODO")
