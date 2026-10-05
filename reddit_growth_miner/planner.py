from __future__ import annotations

import re
from typing import Any

HINTS: list[dict[str, Any]] = [
    {"keywords": ["saas", "startup", "founder", "indie", "micro saas"], "subs": ["SaaS", "startups", "Entrepreneur", "indiehackers", "SideProject", "EntrepreneurRideAlong"]},
    {"keywords": ["developer", "coding", "programmer", "devtool", "api"], "subs": ["webdev", "programming", "ExperiencedDevs", "SideProject", "SaaS"]},
    {"keywords": ["ai", "llm", "agent", "claude", "chatgpt"], "subs": ["LocalLLaMA", "ClaudeAI", "ChatGPT", "MachineLearning", "artificial"]},
    {"keywords": ["marketing", "growth", "seo", "content"], "subs": ["marketing", "SEO", "content_marketing", "Entrepreneur", "SaaS"]},
    {"keywords": ["sales", "sdr", "outbound", "crm"], "subs": ["sales", "salesdevelopment", "CRM", "SaaS", "Entrepreneur"]},
    {"keywords": ["ecommerce", "shopify", "store"], "subs": ["ecommerce", "shopify", "FulfillmentByAmazon", "Entrepreneur"]},
]


def suggest_subreddits(target: str, *, max_subs: int = 8) -> list[str]:
    lower = target.lower()
    selected: list[str] = []
    for hint in HINTS:
        if any(re.search(rf"(?<!\w){re.escape(keyword)}(?!\w)", lower) for keyword in hint["keywords"]):
            for sub in hint["subs"]:
                if sub not in selected:
                    selected.append(sub)
    if not selected:
        selected = ["Entrepreneur", "SaaS", "startups", "SideProject"]
    return selected[:max_subs]
