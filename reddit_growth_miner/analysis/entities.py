from __future__ import annotations

import re

from ..domain import Switch

# A product-like name: one or two capitalised tokens ("Notion", "Google Docs", "Cursor.sh").
_NAME = r"([A-Z][\w.+-]{1,30}(?: [A-Z][\w.+-]{1,30})?)"

SWITCH_PATTERNS = [
    re.compile(rf"(?i:\b(?:switched|switching|migrated|migrating|moved|moving|went|transitioned)\s+(?:over\s+|back\s+)?from)\s+{_NAME}\s+(?i:to)\s+{_NAME}"),
    re.compile(rf"(?i:\breplaced)\s+{_NAME}\s+(?i:with)\s+{_NAME}"),
    re.compile(rf"(?i:\b(?:left|ditched|dropped|dumped))\s+{_NAME}\s+(?i:for)\s+{_NAME}"),
]
MENTION_PATTERNS = [
    re.compile(rf"(?i:\balternatives?\s+(?:to|for))\s+{_NAME}"),
    re.compile(rf"(?i:\binstead\s+of)\s+{_NAME}"),
    re.compile(rf"{_NAME}\s+(?i:vs\.?|versus)\s+{_NAME}"),
    re.compile(rf"(?i:\b(?:cancell?ed|stopped\s+using|gave\s+up\s+on))\s+{_NAME}"),
]
_NOT_NAMES = {"I", "A", "An", "The", "My", "Our", "It", "This", "That", "Reddit", "Edit", "Update", "TLDR"}


def _tidy(name: str) -> str:
    name = name.strip(".-+ ")
    first = name.split(" ")[0]
    return "" if first in _NOT_NAMES or len(name) < 2 else name


class EntityExtractor:
    """Find competitor mentions and switch statements.

    With a known list (`--competitors`), mentions are exact word matches against
    names and aliases, and switch endpoints are normalised to the canonical name.
    Without one, only names appearing in comparison language are reported.
    """

    def __init__(self, known: dict[str, list[str]] | None = None):
        self.known = known or {}
        self._alias_patterns = [
            (canonical, re.compile(r"(?<!\w)(?:" + "|".join(re.escape(a) for a in [canonical, *aliases]) + r")(?!\w)", re.IGNORECASE))
            for canonical, aliases in self.known.items()
        ]

    @classmethod
    def parse(cls, spec: str | None) -> "EntityExtractor":
        """`"Notion,Linear=linear.app|Linear App,Jira"` → canonical names with optional aliases."""
        known: dict[str, list[str]] = {}
        for item in (spec or "").split(","):
            if not item.strip():
                continue
            name, _, aliases = item.partition("=")
            known[name.strip()] = [a.strip() for a in aliases.split("|") if a.strip()]
        return cls(known)

    def _resolve(self, captured: str) -> str | None:
        if not self.known:
            return _tidy(captured) or None
        for canonical, pattern in self._alias_patterns:
            if pattern.search(captured):
                return canonical
        return None

    def mentions(self, text: str) -> list[str]:
        if self.known:
            return [canonical for canonical, pattern in self._alias_patterns if pattern.search(text)]
        found: list[str] = []
        for pattern in [*SWITCH_PATTERNS, *MENTION_PATTERNS]:
            for match in pattern.finditer(text):
                found.extend(n for g in match.groups() if g and (n := _tidy(g)))
        return list(dict.fromkeys(found))

    def switches(self, text: str) -> list[Switch]:
        found: list[Switch] = []
        for pattern in SWITCH_PATTERNS:
            for match in pattern.finditer(text):
                source, target = self._resolve(match.group(1)), self._resolve(match.group(2))
                if self.known:
                    # Keep the switch if at least one side is a tracked competitor.
                    if not (source or target):
                        continue
                    source = source or _tidy(match.group(1)) or "other"
                    target = target or _tidy(match.group(2)) or "other"
                if source and target and source != target:
                    found.append(Switch(source, target))
        return list(dict.fromkeys(found))
