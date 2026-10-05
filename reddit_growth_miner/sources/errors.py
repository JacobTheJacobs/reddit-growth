from __future__ import annotations


class SourceError(RuntimeError):
    def __init__(self, source: str, reason: str):
        self.source = source
        self.reason = reason
        super().__init__(f"{source}: {reason}")


class SourceBlocked(SourceError):
    """The source refused access (403/429). Not retried for the rest of the run."""
