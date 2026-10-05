from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable

from .sources.errors import SourceBlocked, SourceError

RETRYABLE_CODES = {408, 425, 500, 502, 503, 504}
DEFAULT_USER_AGENT = "reddit-growth-miner/0.2 (+https://github.com/JacobTheJacobs/reddit-growth)"


class HttpClient:
    """JSON GET client with per-host pacing, bounded retries and a circuit breaker.

    A host that answers 403 or 429 is marked blocked for the rest of the run;
    the client never retries around access controls.
    """

    def __init__(
        self,
        *,
        user_agent: str | None = None,
        min_interval: float | None = None,
        max_retries: int | None = None,
        timeout: float = 45,
        opener: Callable[..., Any] = urllib.request.urlopen,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.user_agent = user_agent or os.getenv("REDDIT_GROWTH_MINER_USER_AGENT", DEFAULT_USER_AGENT)
        self.min_interval = max(0.0, min_interval if min_interval is not None else float(os.getenv("REDDIT_GROWTH_MINER_SOURCE_MIN_INTERVAL", "1.2")))
        self.max_retries = max(0, max_retries if max_retries is not None else int(os.getenv("REDDIT_GROWTH_MINER_HTTP_MAX_RETRIES", "1")))
        self.timeout = timeout
        self._opener = opener
        self._sleep = sleep
        self._clock = clock
        self._last_request: dict[str, float] = {}
        self._blocked: dict[str, str] = {}

    def get_json(self, url: str, params: dict[str, Any] | None = None, *, timeout: float | None = None) -> Any:
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        try:
            return json.loads(self._get(url, timeout or self.timeout).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise SourceError(urllib.parse.urlparse(url).netloc, f"invalid_json:{type(error).__name__}") from error

    def _pace(self, host: str) -> None:
        wait = self.min_interval - (self._clock() - self._last_request.get(host, float("-inf")))
        if wait > 0:
            self._sleep(wait)
        self._last_request[host] = self._clock()

    def _get(self, url: str, timeout: float) -> bytes:
        host = urllib.parse.urlparse(url).netloc.lower()
        if host in self._blocked:
            raise SourceBlocked(host, self._blocked[host])
        request = urllib.request.Request(url, headers={"User-Agent": self.user_agent, "Accept": "application/json"})
        for attempt in range(self.max_retries + 1):
            self._pace(host)
            try:
                with self._opener(request, timeout=timeout) as response:
                    return response.read()
            except urllib.error.HTTPError as error:
                if error.code in {403, 429}:
                    self._blocked[host] = f"http_{error.code}"
                    raise SourceBlocked(host, self._blocked[host]) from error
                if error.code not in RETRYABLE_CODES or attempt == self.max_retries:
                    raise SourceError(host, f"http_{error.code}") from error
            except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
                if attempt == self.max_retries:
                    raise SourceError(host, type(error).__name__) from error
            self._sleep(min(4.0, 2**attempt))
        raise AssertionError("unreachable")
