from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .domain import Post


@dataclass(frozen=True)
class Spec:
    """Composable post predicate: `MinScore(5) & MinComments(3) & ~IsPromotion()`."""

    test: Callable[[Post], bool]

    def __call__(self, post: Post) -> bool:
        return self.test(post)

    def __and__(self, other: "Spec") -> "Spec":
        return Spec(lambda p: self(p) and other(p))

    def __or__(self, other: "Spec") -> "Spec":
        return Spec(lambda p: self(p) or other(p))

    def __invert__(self) -> "Spec":
        return Spec(lambda p: not self(p))


def Always() -> Spec:
    return Spec(lambda p: True)


def MinScore(n: int) -> Spec:
    return Spec(lambda p: p.score >= n)


def MinComments(n: int) -> Spec:
    return Spec(lambda p: p.num_comments >= n)


def PostedAfter(epoch: int) -> Spec:
    return Spec(lambda p: not p.created_utc or p.created_utc > epoch)


def HasIntent(intents: frozenset[str]) -> Spec:
    """Matches if any of the post's own labels (not only the primary one) is in `intents`."""
    return Spec(lambda p: p.intent in intents or any(l.intent in intents for l in p.labels))


def IsPromotion() -> Spec:
    return Spec(lambda p: p.signals.promotion)
