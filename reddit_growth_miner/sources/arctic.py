from __future__ import annotations

from typing import Any

from ..domain import FetchResult
from ..http import HttpClient
from .base import paginate, rows


class ArcticShiftSource:
    name = "arctic-shift"
    POSTS = "https://arctic-shift.photon-reddit.com/api/posts/search"
    COMMENTS = "https://arctic-shift.photon-reddit.com/api/comments/search"
    PAGE_SIZE = 100

    def __init__(self, http: HttpClient):
        self.http = http

    def fetch_posts(self, subreddit: str, *, after: int, max_pages: int) -> FetchResult:
        def page(before: int | None) -> list[dict[str, Any]]:
            params: dict[str, Any] = {"subreddit": subreddit, "after": after, "limit": self.PAGE_SIZE, "sort": "desc"}
            if before is not None:
                params["before"] = before
            return rows(self.http.get_json(self.POSTS, params))

        return paginate(page, after=after, max_pages=max_pages, page_size=self.PAGE_SIZE, source=self.name)

    def fetch_comments(self, post_id: str, *, limit: int) -> list[dict[str, Any]]:
        return rows(self.http.get_json(self.COMMENTS, {"link_id": post_id, "limit": min(limit, 100), "sort": "desc"}))

    def probe(self) -> None:
        self.http.get_json(self.POSTS, {"subreddit": "SaaS", "limit": 1}, timeout=15)
