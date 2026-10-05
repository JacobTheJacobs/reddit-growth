from __future__ import annotations

import re
import time
from dataclasses import asdict
from typing import Any, Callable

from .analysis import Enricher, analyze
from .config import ScanConfig
from .domain import Post
from .filters import Always, HasIntent, MinComments, MinScore, PostedAfter
from .rules import RuleSet
from .sources import Source, SourceError

SCHEMA_VERSION = "2.0"


def _content_key(post: Post) -> str:
    """Crossposts carry new ids; a long-enough identical title is the same discussion."""
    title = re.sub(r"\W+", " ", post.title.lower()).strip()
    return f"title:{title}" if len(title) >= 20 else f"id:{post.id or post.url}"


class ScanPipeline:
    """collect → filter → enrich → intent filter → comments → analyze."""

    def __init__(self, source: Source, enricher: Enricher, rules: RuleSet, *, clock: Callable[[], float] = time.time):
        self.source = source
        self.enricher = enricher
        self.rules = rules
        self.clock = clock

    def run(self, cfg: ScanConfig) -> dict[str, Any]:
        now = self.clock()
        after = int(now - cfg.hours * 3600)
        prefilter = MinScore(cfg.min_score) & MinComments(cfg.min_comments) & PostedAfter(after)
        intent_filter = HasIntent(cfg.intents) if cfg.intents else Always()

        posts: dict[str, Post] = {}
        seen: set[str] = set()
        statuses: list[dict[str, Any]] = []
        for sub in cfg.subreddits:
            try:
                fetched = self.source.fetch_posts(sub, after=after, max_pages=cfg.max_pages)
            except SourceError as error:
                statuses.append({"subreddit": sub, "status": "error", "reason": error.reason})
                continue
            kept, comment_errors = 0, 0
            for post in fetched.posts:
                key, content = post.id or post.url, _content_key(post)
                if key in seen or content in seen or not prefilter(post):
                    continue
                seen.update((key, content))
                post = self.enricher.enrich(post)
                if not intent_filter(post):
                    continue
                if cfg.fetch_comments and post.id and post.num_comments:
                    try:
                        post = self.enricher.attach_comments(post, self.source.fetch_comments(post.id, limit=cfg.comment_limit))
                    except SourceError:
                        comment_errors += 1
                posts[key] = post
                kept += 1
            statuses.append({
                "subreddit": sub,
                "status": "ok" if fetched.complete else "truncated",
                "source": fetched.source,
                "pages": fetched.pages,
                "candidates": len(fetched.posts),
                "kept": kept,
                "comment_errors": comment_errors,
                **({} if fetched.complete else {"reason": f"max_pages={cfg.max_pages} reached before window start"}),
            })

        kept_posts = list(posts.values())
        return {
            "schema_version": SCHEMA_VERSION,
            "target": cfg.target,
            "window_hours": cfg.hours,
            "generated_at": int(now),
            "subreddits": list(cfg.subreddits),
            "filters": cfg.filters_dict(),
            "competitors": cfg.competitors or None,
            "source_status": statuses,
            "posts": [asdict(p) for p in kept_posts],
            "analysis": {"target": cfg.target, **analyze(kept_posts, rules=self.rules, now=now, window_hours=cfg.hours)},
        }
