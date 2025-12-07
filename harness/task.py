"""load a task fixture from disk."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Task:
    slug: str
    repo: str
    base_sha: str
    source_files: list[str]
    test_files: list[str]
    test_command: str
    prompt: str
    difficulty: str
    multi_file: bool
    fixture_dir: Path  # so the runner can find tests/ etc.


def load_task(fixture_dir: Path) -> Task:
    fixture_dir = Path(fixture_dir)
    meta = json.loads((fixture_dir / "meta.json").read_text())
    prompt = (fixture_dir / "prompt.md").read_text()
    return Task(
        slug=fixture_dir.name,
        repo=meta["repo"],
        base_sha=meta["base_sha"],
        source_files=meta["source_files"],
        test_files=meta["test_files"],
        test_command=meta["test_command"],
        prompt=prompt,
        difficulty=meta["difficulty"],
        multi_file=meta["multi_file"],
        fixture_dir=fixture_dir,
    )


def discover_tasks(tasks_dir: Path) -> list[Task]:
    """load all tasks under `tasks_dir`. ignores files starting with `_`."""
    out = []
    for d in sorted(Path(tasks_dir).iterdir()):
        if d.is_dir() and not d.name.startswith("_"):
            try:
                out.append(load_task(d))
            except Exception as e:
                # don't crash the whole eval if one task fixture is malformed —
                # report it and keep going
                print(f"WARN: skipping {d.name}: {type(e).__name__}: {e}")
    return out
