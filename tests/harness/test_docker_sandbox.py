"""these tests don't actually call docker — they just verify the cmd we'd run.
keeps the test suite runnable without docker installed locally (CI machine
will run a separate integration suite that does spin a real container)."""
from __future__ import annotations

from pathlib import Path

from harness.docker_sandbox import DockerSandbox


def test_run_cmd_includes_memory_limit(tmp_path):
    sb = DockerSandbox(image="python:3.11-slim", mount_root=tmp_path, memory_mb=1024)
    cmd = sb._build_run_cmd()
    assert "--memory" in cmd
    assert "1024m" in cmd


def test_run_cmd_mounts_workspace(tmp_path):
    sb = DockerSandbox(image="python:3.11-slim", mount_root=tmp_path)
    cmd = sb._build_run_cmd()
    # the -v flag should map mount_root → /workspace
    v_idx = cmd.index("-v")
    assert cmd[v_idx + 1].endswith(":/workspace")
    assert "-w" in cmd
    assert cmd[cmd.index("-w") + 1] == "/workspace"


def test_run_cmd_uses_specified_image(tmp_path):
    sb = DockerSandbox(image="python:3.11-slim", mount_root=tmp_path)
    cmd = sb._build_run_cmd()
    assert "python:3.11-slim" in cmd
