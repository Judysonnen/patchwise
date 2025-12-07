"""runs a scaffolded agent against a single task.

steps:
  1. ensure the upstream repo is cloned & checked out at task.base_sha
  2. apply the fixture's test files into the worktree
  3. let the scaffold drive the model + tools
  4. run task.test_command and score success
  5. record the outcome event into the trace store
"""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .model_client import ModelClient
from .repo_cache import checkout, ensure_clone
from .task import Task
from .tools import TOOLS, make_dispatch
from .trace_store import TraceStore


@dataclass
class TaskResult:
    trajectory_id: str
    success: bool
    steps_taken: int
    error: str | None = None
    test_output_tail: str = ""


def _apply_test_files(repo_path: Path, task: Task) -> None:
    """copy fixture's test files into the cloned repo, overwriting any
    existing version. paths in meta.json:test_files are relative to repo root.
    """
    for original_path in task.test_files:
        src = task.fixture_dir / "tests" / Path(original_path).name
        if not src.exists():
            raise RuntimeError(
                f"fixture {task.slug}: test file {src.name} missing under tests/"
            )
        dst = repo_path / original_path
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def _run_test_command(repo_path: Path, command: str, timeout: int = 180) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            command, shell=True, cwd=repo_path,
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, "test command timed out"
    body = (result.stdout + result.stderr)[-4000:]
    return (result.returncode == 0), body


class Runner:
    def __init__(
        self,
        task: Task,
        scaffold: Callable,
        model: ModelClient,
        trace: TraceStore,
        apply_patch_variant: str = "tolerant",
        max_steps: int = 25,
    ):
        self.task = task
        self.scaffold = scaffold
        self.model = model
        self.trace = trace
        self.apply_patch_variant = apply_patch_variant
        self.max_steps = max_steps

    def run(self, trajectory_id: str) -> TaskResult:
        repo_path = ensure_clone(self.task.repo)
        checkout(repo_path, self.task.base_sha)
        _apply_test_files(repo_path, self.task)

        dispatch = make_dispatch(repo_path, self.task.test_command, self.apply_patch_variant)
        steps_taken = 0
        scaffold_error = None
        try:
            self.scaffold(
                task_prompt=self.task.prompt,
                tools=TOOLS,
                tool_dispatch=dispatch,
                model=self.model,
                trace=self.trace,
                trajectory_id=trajectory_id,
                max_steps=self.max_steps,
            )
        except Exception as e:
            scaffold_error = f"{type(e).__name__}: {e}"

        # count steps from the trace (events with positive step number, of type "completion")
        for ev in self.trace.replay_prefix(trajectory_id, up_to_step=10_000):
            if ev["event_type"] == "completion":
                steps_taken += 1

        success, test_tail = _run_test_command(repo_path, self.task.test_command)
        self.trace.append(
            trajectory_id, steps_taken + 1, "outcome",
            {
                "success": success,
                "test_output_tail": test_tail[-1500:],
                "scaffold_error": scaffold_error,
            },
        )
        return TaskResult(
            trajectory_id=trajectory_id,
            success=success,
            steps_taken=steps_taken,
            error=scaffold_error,
            test_output_tail=test_tail[-1500:],
        )
