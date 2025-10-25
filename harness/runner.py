"""runs a scaffolded agent against a single task inside a sandbox.

steps:
  1. set up a worktree at the task's `before/` state
  2. start a docker sandbox over that worktree
  3. wire up the trace store
  4. let the scaffold drive the model + tools
  5. tear down sandbox + worktree

most of this is unimplemented; the docker_sandbox / worktree / trace_store
pieces land in subsequent commits, then the runner ties them together.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .docker_sandbox import DockerSandbox
from .model_client import ModelClient
from .trace_store import TraceStore
from .worktree import Worktree


@dataclass
class TaskResult:
    trajectory_id: str
    success: bool
    steps_taken: int
    error: str | None = None


class Runner:
    def __init__(
        self,
        task_dir: Path,
        scaffold,  # callable: scaffold(...) -> Completion | None
        model: ModelClient,
        trace: TraceStore,
        budget_seconds: int = 300,
        budget_memory_mb: int = 2048,
    ):
        self.task_dir = Path(task_dir)
        self.scaffold = scaffold
        self.model = model
        self.trace = trace
        self.budget_seconds = budget_seconds
        self.budget_memory_mb = budget_memory_mb

    def run(self, trajectory_id: str) -> TaskResult:
        # TODO: wire worktree + sandbox + trace + scaffold together
        raise NotImplementedError("runner not implemented yet — see TODOs")
