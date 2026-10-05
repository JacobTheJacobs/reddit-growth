from __future__ import annotations

import json
from typing import Any, Callable

from .markdown import render_markdown

Renderer = Callable[[dict[str, Any]], str]


def render_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


RENDERERS: dict[str, Renderer] = {"md": render_markdown, "json": render_json}

__all__ = ["RENDERERS", "Renderer", "render_json", "render_markdown"]
