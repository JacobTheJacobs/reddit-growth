from __future__ import annotations

from typing import Protocol

from ..domain import Label


class Classifier(Protocol):
    def classify(self, title: str, body: str = "") -> list[Label]:
        """Return every intent found, strongest first. Promotion is reported as its own label."""

    def primary(self, labels: list[Label]) -> Label | None:
        """Pick the label that best describes the text, ignoring promotion unless it is the only one."""

    def themes(self, text: str) -> list[str]:
        """Return theme names found in the text."""
