"""runs commands inside a docker container with resource caps and (later)
no host network. shells out to the docker CLI rather than using the docker
python SDK because the SDK's version skew with the local docker daemon has
bitten me before.
"""
from __future__ import annotations

import subprocess
import uuid
from pathlib import Path


class SandboxError(RuntimeError):
    pass


class DockerSandbox:
    def __init__(
        self,
        image: str,
        mount_root: Path,
        memory_mb: int = 2048,
        wall_clock_s: int = 300,
    ):
        self.image = image
        self.mount_root = Path(mount_root).resolve()
        self.memory_mb = memory_mb
        self.wall_clock_s = wall_clock_s
        self._name = f"patchwise-{uuid.uuid4().hex[:8]}"
        self._started = False

    def _build_run_cmd(self) -> list[str]:
        return [
            "docker", "run", "-d",
            "--name", self._name,
            # NO NETWORK. confirmed by accident that without this the agent's
            # tools could `pip install` arbitrary packages mid-run, defeating
            # the sandbox. found by curl-ing example.com from inside.
            "--network", "none",
            "--memory", f"{self.memory_mb}m",
            "-v", f"{self.mount_root}:/workspace",
            "-w", "/workspace",
            self.image,
            "sleep", "infinity",
        ]

    def start(self) -> None:
        if self._started:
            return
        cmd = self._build_run_cmd()
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            raise SandboxError(f"docker run failed: {e.stderr.strip()}") from e
        self._started = True

    def exec(self, cmd: list[str]) -> tuple[int, str, str]:
        if not self._started:
            raise SandboxError("sandbox not started")
        # TODO: timeout enforcement is rough — uses subprocess timeout, which
        # leaves the docker exec running in the container even after we kill
        # the local process. need to wire docker kill on timeout.
        full = ["docker", "exec", self._name] + cmd
        result = subprocess.run(
            full, capture_output=True, text=True, timeout=self.wall_clock_s,
        )
        return (result.returncode, result.stdout, result.stderr)

    def stop(self) -> None:
        if not self._started:
            return
        # always force-remove on stop. running containers from interrupted
        # ablation runs were piling up in `docker ps -a`.
        subprocess.run(["docker", "rm", "-f", self._name], capture_output=True)
        self._started = False

    @property
    def container_name(self) -> str:
        return self._name

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *exc):
        self.stop()
