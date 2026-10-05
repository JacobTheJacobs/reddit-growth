from __future__ import annotations

import re
from typing import Any, Callable, Protocol

from ..domain import FetchResult, Post


class Source(Protocol):
    name: str

    def fetch_posts(self, subreddit: str, *, after: int, max_pages: int) -> FetchResult:
        """Return every post in `subreddit` created after `after`, newest first."""

    def fetch_comments(self, post_id: str, *, limit: int) -> list[dict[str, Any]]:
        """Return raw comment rows for one post."""

    def probe(self) -> None:
        """Raise SourceError if the source is unreachable."""


def clean_text(text: Any, limit: int = 800) -> str:
    if not text or text in {"[removed]", "[deleted]"}:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()[:limit]


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def post_from_raw(raw: dict[str, Any], source: str) -> Post:
    subreddit = str(raw.get("subreddit") or "unknown").removeprefix("r/")
    permalink = raw.get("permalink")
    return Post(
        id=str(raw.get("id") or ""),
        community=f"r/{subreddit}",
        title=clean_text(raw.get("title"), 300),
        selftext=clean_text(raw.get("selftext"), 1500),
        url=f"https://www.reddit.com{permalink}" if permalink else str(raw.get("url") or ""),
        score=max(_int(raw.get("score")), _int(raw.get("ups"))),
        num_comments=_int(raw.get("num_comments")),
        created_utc=_int(raw.get("created_utc")),
        source=source,
    )


def rows(payload: Any) -> list[dict[str, Any]]:
    data = payload.get("data", []) if isinstance(payload, dict) else payload
    return [row for row in data if isinstance(row, dict)] if isinstance(data, list) else []


def paginate(
    fetch_page: Callable[[int | None], list[dict[str, Any]]],
    *,
    after: int,
    max_pages: int,
    page_size: int,
    source: str,
) -> FetchResult:
    """Walk a newest-first listing backwards with `before` cursors until `after` is reached."""
    seen: set[str] = set()
    collected: list[dict[str, Any]] = []
    before: int | None = None
    pages = 0
    complete = False
    while pages < max_pages:
        page = fetch_page(before)
        pages += 1
        fresh = 0
        for row in page:
            key = str(row.get("id") or "")
            if key and key not in seen:
                seen.add(key)
                collected.append(row)
                fresh += 1
        timestamps = [_int(row.get("created_utc")) for row in page if row.get("created_utc")]
        if not fresh or not timestamps or len(page) < page_size or min(timestamps) <= after:
            complete = True
            break
        # +1 keeps posts sharing the boundary second; duplicates are dropped by `seen`.
        before = min(timestamps) + 1
    posts = [post_from_raw(row, source) for row in collected if _int(row.get("created_utc")) > after]
    return FetchResult(posts=posts, source=source, pages=pages, complete=complete)
