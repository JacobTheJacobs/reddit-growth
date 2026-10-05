from __future__ import annotations

import json
import re
from dataclasses import dataclass
from importlib import resources
from pathlib import Path


@dataclass(frozen=True)
class IntentRule:
    name: str
    patterns: tuple[re.Pattern[str], ...]


@dataclass(frozen=True)
class RuleSet:
    """A market-specific rule pack: intent regexes, promotion regexes, theme terms, test templates."""

    intents: tuple[IntentRule, ...]  # ordered by priority for the primary intent
    promotion: tuple[re.Pattern[str], ...]
    themes: dict[str, re.Pattern[str]]
    next_tests: dict[str, str]

    @classmethod
    def load(cls, path: str | Path | None = None) -> "RuleSet":
        if path is None:
            text = resources.files(__package__).joinpath("default.json").read_text(encoding="utf-8")
        else:
            text = Path(path).read_text(encoding="utf-8")
        return cls.from_dict(json.loads(text))

    @classmethod
    def from_dict(cls, data: dict) -> "RuleSet":
        def compile_all(patterns: list[str]) -> tuple[re.Pattern[str], ...]:
            return tuple(re.compile(p, re.IGNORECASE) for p in patterns)

        def term_pattern(terms: list[str]) -> re.Pattern[str]:
            # Whole-word match: "api" must not match "therapist", "seo" must not match "Seoul".
            alternation = "|".join(re.escape(t) for t in sorted(terms, key=len, reverse=True))
            return re.compile(rf"(?<!\w)(?:{alternation})(?!\w)", re.IGNORECASE)

        return cls(
            intents=tuple(IntentRule(i["name"], compile_all(i["patterns"])) for i in data["intents"]),
            promotion=compile_all(data.get("promotion", [])),
            themes={name: term_pattern(terms) for name, terms in data.get("themes", {}).items()},
            next_tests=dict(data.get("next_tests", {})),
        )
