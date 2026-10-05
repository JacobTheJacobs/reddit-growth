from __future__ import annotations

from dataclasses import replace
from typing import Any

from ..classify import BUYING_INTENTS, SWITCHING_INTENTS, Classifier
from ..domain import Comment, Label, Post, Signals
from ..sources import clean_text
from .entities import EntityExtractor


def _signals(labels: list[Label], has_switches: bool, *, from_comments: bool = False) -> Signals:
    intents = {l.intent for l in labels}
    return Signals(
        buying=bool(intents & BUYING_INTENTS),
        switching=bool(intents & SWITCHING_INTENTS) or has_switches,
        workaround="workaround_share" in intents,
        budget="purchase_intent" in intents,
        promotion="promotion" in intents,
        from_comments=from_comments,
    )


def _merge(post_signals: Signals, comment_signals: Signals) -> Signals:
    # A promotional post's own wording is not demand evidence; replies to it still are.
    base = Signals(promotion=True) if post_signals.promotion else post_signals
    gained = (
        (comment_signals.buying and not base.buying)
        or (comment_signals.switching and not base.switching)
        or (comment_signals.workaround and not base.workaround)
    )
    return Signals(
        buying=base.buying or comment_signals.buying,
        switching=base.switching or comment_signals.switching,
        workaround=base.workaround or comment_signals.workaround,
        budget=base.budget or comment_signals.budget,
        promotion=post_signals.promotion,
        from_comments=gained,
    )


class Enricher:
    """Turns raw posts and comments into labelled evidence."""

    def __init__(self, classifier: Classifier, extractor: EntityExtractor, *, comment_evidence_limit: int = 3):
        self.classifier = classifier
        self.extractor = extractor
        self.comment_evidence_limit = comment_evidence_limit

    def enrich(self, post: Post) -> Post:
        text = f"{post.title}\n{post.selftext}"
        labels = self.classifier.classify(post.title, post.selftext)
        primary = self.classifier.primary(labels)
        switches = self.extractor.switches(text)
        signals = _signals(labels, bool(switches))
        if signals.promotion:
            signals = Signals(promotion=True)
        return replace(
            post,
            intent=primary.intent if primary else "unknown",
            intent_confidence=primary.score if primary else 0.0,
            labels=tuple(labels),
            themes=tuple(self.classifier.themes(text) or ["general"]),
            competitors=tuple(self.extractor.mentions(text)),
            switches=tuple(switches),
            signals=signals,
        )

    def classify_comment(self, raw: dict[str, Any]) -> Comment | None:
        body = clean_text(raw.get("body"), 600)
        if not body:
            return None
        return Comment(
            id=str(raw.get("id") or ""),
            body=body,
            score=int(raw.get("score") or 0),
            labels=tuple(self.classifier.classify("", body)),
            competitors=tuple(self.extractor.mentions(body)),
            switches=tuple(self.extractor.switches(body)),
        )

    def attach_comments(self, post: Post, raw_comments: list[dict[str, Any]]) -> Post:
        comments = [c for raw in raw_comments if (c := self.classify_comment(raw))]
        demand_labels = [l for c in comments for l in c.labels if l.intent != "promotion"]
        comment_switches = [s for c in comments for s in c.switches]
        signals = _merge(post.signals, _signals(demand_labels, bool(comment_switches), from_comments=True))
        ranked = sorted(comments, key=lambda c: (c.has_signal, c.score), reverse=True)
        return replace(
            post,
            signals=signals,
            competitors=tuple(dict.fromkeys([*post.competitors, *(n for c in comments for n in c.competitors)])),
            switches=tuple(dict.fromkeys([*post.switches, *comment_switches])),
            comments=tuple(ranked[: self.comment_evidence_limit]),
            comments_scanned=len(comments),
            comment_intents=tuple(l.intent for c in comments for l in c.labels),
        )
