from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Label:
    """One intent matched in a piece of text. A text can carry several."""

    intent: str
    score: float
    matched: str


@dataclass(frozen=True)
class Switch:
    """An observed "moved from A to B" statement."""

    source: str
    target: str


@dataclass(frozen=True)
class Signals:
    buying: bool = False
    switching: bool = False
    workaround: bool = False
    budget: bool = False
    promotion: bool = False
    from_comments: bool = False

    @property
    def demand(self) -> bool:
        return self.buying or self.switching or self.workaround


@dataclass(frozen=True)
class Comment:
    id: str
    body: str
    score: int
    labels: tuple[Label, ...] = ()
    competitors: tuple[str, ...] = ()
    switches: tuple[Switch, ...] = ()

    @property
    def has_signal(self) -> bool:
        return bool(self.competitors or self.switches or any(l.intent != "promotion" for l in self.labels))


@dataclass(frozen=True)
class Post:
    id: str
    community: str
    title: str
    selftext: str
    url: str
    score: int
    num_comments: int
    created_utc: int
    source: str
    # Filled in by enrichment.
    intent: str = "unknown"
    intent_confidence: float = 0.0
    labels: tuple[Label, ...] = ()
    themes: tuple[str, ...] = ()
    competitors: tuple[str, ...] = ()
    switches: tuple[Switch, ...] = ()
    signals: Signals = field(default_factory=Signals)
    comments: tuple[Comment, ...] = ()
    comments_scanned: int = 0
    comment_intents: tuple[str, ...] = ()  # every label across all scanned comments

    @property
    def engagement(self) -> int:
        return self.score + 2 * self.num_comments


@dataclass(frozen=True)
class FetchResult:
    posts: list[Post]
    source: str
    pages: int
    complete: bool  # False when max_pages ran out before the window start was reached
