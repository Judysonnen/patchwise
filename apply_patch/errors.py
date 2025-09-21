"""structured error types so callers can decide what to do, not parse strings."""


class ApplyPatchError(Exception):
    """base class for everything raised by this package."""


class MalformedDiffError(ApplyPatchError):
    """diff didn't parse at all (no --- +++ headers, no hunks, etc.)."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class FencedDiffError(ApplyPatchError):
    """diff appears to be wrapped in markdown fences (```diff ... ```)."""

    def __init__(self, fence_marker: str = "```"):
        super().__init__(f"diff is wrapped in markdown fences ({fence_marker})")
        self.fence_marker = fence_marker


class LineDriftError(ApplyPatchError):
    """hunk's @@ line numbers don't match the actual file."""

    def __init__(self, path: str, hunk_old_start: int):
        super().__init__(
            f"line drift in {path} at hunk @@ -{hunk_old_start} (context did not match)"
        )
        self.path = path
        self.hunk_old_start = hunk_old_start


class PartialHunkError(ApplyPatchError):
    """hunk looks truncated mid-body (response cut off, etc.)."""

    def __init__(self, path: str, hunk_old_start: int, reason: str):
        super().__init__(
            f"partial hunk in {path} at @@ -{hunk_old_start}: {reason}"
        )
        self.path = path
        self.hunk_old_start = hunk_old_start
        self.reason = reason
