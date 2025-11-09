"""sqlite (WAL mode) append-only event store.

events are keyed by (trajectory_id, step, event_type) so we can index, query,
and replay. picking sqlite because:

  - we want to query "all trajectories that hit failure mode X after step N"
    cheaply, which kills JSONL
  - the harness has to run offline on a laptop, which kills postgres
  - WAL mode lets a separate analyze script read concurrently while a run
    is still writing, which is how i actually use it during long evals

a trajectory is a single (task, scaffold, model, trial) tuple. trajectory_id
is up to the caller to choose; the runner uses
"{task}__{scaffold}__{model}__{trial}".
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Iterator


SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    trajectory_id TEXT NOT NULL,
    step INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    payload TEXT NOT NULL,
    ts REAL NOT NULL,
    PRIMARY KEY (trajectory_id, step, event_type)
);
CREATE INDEX IF NOT EXISTS idx_events_traj_step ON events (trajectory_id, step);
"""


class TraceStore:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self._conn = sqlite3.connect(str(self.db_path), isolation_level=None)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.executescript(SCHEMA)

    def append(
        self,
        trajectory_id: str,
        step: int,
        event_type: str,
        payload: dict,
    ) -> None:
        # INSERT OR REPLACE because re-runs of the same (traj, step, type)
        # during local debugging shouldn't blow up — they should overwrite.
        self._conn.execute(
            "INSERT OR REPLACE INTO events "
            "(trajectory_id, step, event_type, payload, ts) VALUES (?, ?, ?, ?, ?)",
            (trajectory_id, step, event_type, json.dumps(payload), time.time()),
        )

    def replay_prefix(self, trajectory_id: str, up_to_step: int) -> Iterator[dict]:
        """yield events for `trajectory_id` with step <= up_to_step, in order."""
        cur = self._conn.execute(
            "SELECT step, event_type, payload, ts FROM events "
            "WHERE trajectory_id = ? AND step <= ? "
            "ORDER BY step, event_type",
            (trajectory_id, up_to_step),
        )
        for row in cur:
            yield {
                "step": row[0],
                "event_type": row[1],
                "payload": json.loads(row[2]),
                "ts": row[3],
            }

    def trajectories(self) -> list[str]:
        cur = self._conn.execute(
            "SELECT DISTINCT trajectory_id FROM events ORDER BY trajectory_id"
        )
        return [row[0] for row in cur]

    def query(self, sql: str, params: tuple = ()) -> list[tuple]:
        """escape hatch for analysis scripts that want raw SQL."""
        return list(self._conn.execute(sql, params))

    def close(self) -> None:
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
