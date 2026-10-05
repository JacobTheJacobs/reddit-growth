from __future__ import annotations

from ..domain import Label
from ..rules import RuleSet

BUYING_INTENTS = frozenset({"purchase_intent", "alternative_search", "recommendation_request"})
SWITCHING_INTENTS = frozenset({"switching_story", "alternative_search"})


class RuleClassifier:
    """Transparent regex classifier. Multi-label: a post can be both a complaint and an alternative search."""

    def __init__(self, rules: RuleSet):
        self.rules = rules
        self._priority = {rule.name: i for i, rule in enumerate(rules.intents)}

    def classify(self, title: str, body: str = "") -> list[Label]:
        text = f"{title}\n{body}"
        labels = []
        for rule in self.rules.intents:
            hits = [m for p in rule.patterns if (m := p.search(text))]
            if not hits:
                continue
            in_title = any(p.search(title) for p in rule.patterns)
            score = min(0.95, 0.55 + 0.15 * len(hits) + (0.1 if in_title else 0.0))
            labels.append(Label(rule.name, round(score, 2), hits[0].group(0)))
        promo = next((m for p in self.rules.promotion if (m := p.search(text))), None)
        if promo:
            labels.append(Label("promotion", 0.8, promo.group(0)))
        return sorted(labels, key=lambda l: (-l.score, self._priority.get(l.intent, len(self._priority))))

    def primary(self, labels: list[Label]) -> Label | None:
        demand = [l for l in labels if l.intent != "promotion"]
        if not demand:
            return labels[0] if labels else None
        return min(demand, key=lambda l: (self._priority.get(l.intent, 99), -l.score))

    def themes(self, text: str) -> list[str]:
        return [name for name, pattern in self.rules.themes.items() if pattern.search(text)]
