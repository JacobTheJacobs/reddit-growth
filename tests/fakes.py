from __future__ import annotations

from typing import Any

from reddit_growth_miner.domain import FetchResult
from reddit_growth_miner.sources import SourceError, post_from_raw

NOW = 1_900_000_000


def raw_post(id: str, title: str, *, sub: str = "SaaS", body: str = "", score: int = 10, comments: int = 5, age_hours: float = 1) -> dict[str, Any]:
    return {
        "id": id, "subreddit": sub, "title": title, "selftext": body, "score": score,
        "num_comments": comments, "created_utc": int(NOW - age_hours * 3600),
        "permalink": f"/r/{sub}/comments/{id}/x/",
    }


class FakeSource:
    def __init__(self, posts: dict[str, list[dict]], comments: dict[str, list[dict]] | None = None, *, name: str = "fake", fail: bool = False):
        self.name = name
        self.posts = posts
        self.comments = comments or {}
        self.fail = fail
        self.comment_calls: list[str] = []

    def fetch_posts(self, subreddit: str, *, after: int, max_pages: int) -> FetchResult:
        if self.fail:
            raise SourceError(self.name, "http_503")
        rows = self.posts.get(subreddit, [])
        return FetchResult([post_from_raw(r, self.name) for r in rows if r["created_utc"] > after], self.name, 1, True)

    def fetch_comments(self, post_id: str, *, limit: int) -> list[dict[str, Any]]:
        self.comment_calls.append(post_id)
        if self.fail:
            raise SourceError(self.name, "http_503")
        return self.comments.get(post_id, [])[:limit]

    def probe(self) -> None:
        if self.fail:
            raise SourceError(self.name, "http_503")
