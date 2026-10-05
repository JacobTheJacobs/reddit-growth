from __future__ import annotations

from typing import Any

from ..domain import FetchResult
from .base import Source
from .errors import SourceError


class FallbackSource:
    """Try each source in order; the first one that answers wins."""

    def __init__(self, sources: list[Source]):
        if not sources:
            raise ValueError("FallbackSource needs at least one source")
        self.sources = sources
        self.name = "+".join(s.name for s in sources)

    def fetch_posts(self, subreddit: str, *, after: int, max_pages: int) -> FetchResult:
        return self._first(lambda s: s.fetch_posts(subreddit, after=after, max_pages=max_pages))

    def fetch_comments(self, post_id: str, *, limit: int) -> list[dict[str, Any]]:
        return self._first(lambda s: s.fetch_comments(post_id, limit=limit))

    def probe(self) -> None:
        self._first(lambda s: s.probe())

    def _first(self, call):
        errors = []
        for source in self.sources:
            try:
                return call(source)
            except SourceError as error:
                errors.append(f"{source.name}={error.reason}")
        raise SourceError(self.name, ", ".join(errors))


class CachedSource:
    """Memoise fetches for the lifetime of the object."""

    def __init__(self, inner: Source):
        self.inner = inner
        self.name = inner.name
        self._posts: dict[tuple[str, int, int], FetchResult] = {}
        self._comments: dict[tuple[str, int], list[dict[str, Any]]] = {}

    def fetch_posts(self, subreddit: str, *, after: int, max_pages: int) -> FetchResult:
        key = (subreddit.lower(), after, max_pages)
        if key not in self._posts:
            self._posts[key] = self.inner.fetch_posts(subreddit, after=after, max_pages=max_pages)
        return self._posts[key]

    def fetch_comments(self, post_id: str, *, limit: int) -> list[dict[str, Any]]:
        key = (post_id, limit)
        if key not in self._comments:
            self._comments[key] = self.inner.fetch_comments(post_id, limit=limit)
        return list(self._comments[key])

    def probe(self) -> None:
        self.inner.probe()
