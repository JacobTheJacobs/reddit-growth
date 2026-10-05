from __future__ import annotations

from typing import Any

from ..domain import FetchResult
from ..http import HttpClient
from .base import paginate, rows


class PullPushSource:
    name = "pullpush"
    POSTS = "https://api.pullpush.io/reddit/search/submission/"
    COMMENTS = "https://api.pullpush.io/reddit/search/comment/"
    PAGE_SIZE = 100

    def __init__(self, http: HttpClient):
        self.http = http

    def fetch_posts(self, subreddit: str, *, after: int, max_pages: int) -> FetchResult:
        def page(before: int | None) -> list[dict[str, Any]]:
            params: dict[str, Any] = {
                "subreddit": subreddit, "after": after, "size": self.PAGE_SIZE,
                "sort": "desc", "sort_type": "created_utc",
            }
            if before is not None:
                params["before"] = before
            return rows(self.http.get_json(self.POSTS, params))

        return paginate(page, after=after, max_pages=max_pages, page_size=self.PAGE_SIZE, source=self.name)

    def fetch_comments(self, post_id: str, *, limit: int) -> list[dict[str, Any]]:
        return rows(self.http.get_json(self.COMMENTS, {"link_id": post_id, "size": min(limit, 100), "sort": "desc"}))

    def probe(self) -> None:
        self.http.get_json(self.POSTS, {"subreddit": "SaaS", "size": 1}, timeout=15)
