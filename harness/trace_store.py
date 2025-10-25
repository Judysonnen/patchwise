"""sqlite (WAL mode) append-only event store. placeholder."""
from __future__ import annotations

from pathlib import Path
from typing import Iterator


class TraceStore:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)

    def append(self, trajectory_id: str, step: int, event_type: str, payload: dict) -> None:
        raise NotImplementedError("TODO")

    def replay_prefix(self, trajectory_id: str, up_to_step: int) -> Iterator[dict]:
        raise NotImplementedError("TODO")

    def close(self) -> None:
        pass
