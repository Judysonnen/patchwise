"""runs commands inside a docker container with no host network and resource caps.

placeholder — wiring is in subsequent commits.
"""
from __future__ import annotations

from pathlib import Path


class DockerSandbox:
    def __init__(
        self,
        image: str,
        mount_root: Path,
        memory_mb: int = 2048,
        wall_clock_s: int = 300,
    ):
        self.image = image
        self.mount_root = Path(mount_root)
        self.memory_mb = memory_mb
        self.wall_clock_s = wall_clock_s

    def start(self) -> None:
        raise NotImplementedError("TODO")

    def exec(self, cmd: list[str]) -> tuple[int, str, str]:
        """run cmd inside the container. returns (returncode, stdout, stderr)."""
        raise NotImplementedError("TODO")

    def stop(self) -> None:
        raise NotImplementedError("TODO")
