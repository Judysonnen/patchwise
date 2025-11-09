from __future__ import annotations

from harness.trace_store import TraceStore


def test_append_and_replay_in_step_order(tmp_path):
    db = tmp_path / "trace.sqlite"
    with TraceStore(db) as ts:
        ts.append("traj-a", 0, "start", {"prompt": "fix it"})
        ts.append("traj-a", 1, "completion", {"text": "i'll read foo.py"})
        ts.append("traj-a", 2, "tool_result", {"name": "read_file", "result": "..."})
        events = list(ts.replay_prefix("traj-a", up_to_step=10))
    assert [e["event_type"] for e in events] == ["start", "completion", "tool_result"]
    assert [e["step"] for e in events] == [0, 1, 2]
    assert events[0]["payload"]["prompt"] == "fix it"


def test_replay_prefix_truncates_at_step(tmp_path):
    db = tmp_path / "trace.sqlite"
    with TraceStore(db) as ts:
        for s in range(5):
            ts.append("traj-b", s, "completion", {"i": s})
        events = list(ts.replay_prefix("traj-b", up_to_step=2))
    assert [e["step"] for e in events] == [0, 1, 2]


def test_trajectories_lists_distinct_ids(tmp_path):
    db = tmp_path / "trace.sqlite"
    with TraceStore(db) as ts:
        ts.append("traj-a", 0, "start", {})
        ts.append("traj-b", 0, "start", {})
        ts.append("traj-a", 1, "completion", {})
        assert ts.trajectories() == ["traj-a", "traj-b"]


def test_wal_mode_enabled(tmp_path):
    db = tmp_path / "trace.sqlite"
    with TraceStore(db) as ts:
        mode = ts.query("PRAGMA journal_mode")[0][0]
    assert mode.lower() == "wal"


def test_replay_returns_payload_decoded(tmp_path):
    """payload round-trips through json — replay should return a dict, not a string."""
    db = tmp_path / "trace.sqlite"
    with TraceStore(db) as ts:
        ts.append("t", 0, "completion", {"nested": {"k": [1, 2, 3]}})
        events = list(ts.replay_prefix("t", up_to_step=0))
    assert events[0]["payload"] == {"nested": {"k": [1, 2, 3]}}
