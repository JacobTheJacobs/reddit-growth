from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ScanConfig:
    target: str
    subreddits: tuple[str, ...]
    hours: int = 168
    min_score: int = 5
    min_comments: int = 3
    intents: frozenset[str] = field(default_factory=frozenset)
    fetch_comments: bool = False
    comment_limit: int = 50
    max_pages: int = 10
    competitors: str = ""

    def filters_dict(self) -> dict:
        return {
            "min_score": self.min_score,
            "min_comments": self.min_comments,
            "intents": sorted(self.intents) or None,
            "max_pages": self.max_pages,
        }
