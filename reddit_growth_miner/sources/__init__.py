from .base import Source, clean_text, paginate, post_from_raw
from .composite import CachedSource, FallbackSource
from .errors import SourceBlocked, SourceError

__all__ = [
    "CachedSource", "FallbackSource", "Source", "SourceBlocked", "SourceError",
    "clean_text", "paginate", "post_from_raw", "build_source",
]


def build_source(*, fallback: bool = True, http=None) -> Source:
    from ..http import HttpClient
    from .arctic import ArcticShiftSource
    from .pullpush import PullPushSource

    http = http or HttpClient()
    chain: list[Source] = [ArcticShiftSource(http)]
    if fallback:
        chain.append(PullPushSource(http))
    return CachedSource(FallbackSource(chain))
