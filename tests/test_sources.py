import io
import json
import unittest
import urllib.error
import urllib.parse

from reddit_growth_miner.http import HttpClient
from reddit_growth_miner.sources import CachedSource, FallbackSource, SourceBlocked, SourceError, paginate
from reddit_growth_miner.sources.arctic import ArcticShiftSource

from fakes import FakeSource, raw_post


def listing(start: int, count: int, step: int = 60):
    """`count` rows, newest first, starting at epoch `start`."""
    return [{"id": f"p{start - i * step}", "subreddit": "SaaS", "title": "t", "created_utc": start - i * step} for i in range(count)]


class PaginationTests(unittest.TestCase):
    def test_walks_back_until_window_start(self):
        all_rows = listing(100_000, 350)
        calls = []

        def page(before):
            calls.append(before)
            eligible = [r for r in all_rows if before is None or r["created_utc"] < before]
            return eligible[:100]

        after = 100_000 - 300 * 60  # window covers the newest 300 rows
        result = paginate(page, after=after, max_pages=10, page_size=100, source="x")
        self.assertTrue(result.complete)
        self.assertEqual(len(result.posts), 300)
        self.assertGreater(len(calls), 3)
        self.assertTrue(all(p.created_utc > after for p in result.posts))

    def test_reports_truncation_when_pages_run_out(self):
        all_rows = listing(100_000, 1000)
        result = paginate(lambda b: [r for r in all_rows if b is None or r["created_utc"] < b][:100],
                          after=0, max_pages=2, page_size=100, source="x")
        self.assertFalse(result.complete)
        self.assertEqual(len(result.posts), 199)  # page 2 re-reads the boundary second

    def test_stops_when_page_repeats(self):
        same = listing(100_000, 100, step=0)  # 100 posts in the same second
        result = paginate(lambda b: same, after=0, max_pages=10, page_size=100, source="x")
        self.assertEqual(result.pages, 2)
        self.assertEqual(len(result.posts), 1)  # identical ids collapse


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class HttpClientTests(unittest.TestCase):
    def client(self, opener):
        return HttpClient(min_interval=0, max_retries=2, opener=opener, sleep=lambda s: None)

    def test_blocked_host_is_not_retried_or_slept_on(self):
        calls = []

        def opener(request, timeout):
            calls.append(request.full_url)
            raise urllib.error.HTTPError(request.full_url, 429, "slow down", {"Retry-After": "30"}, None)

        client = self.client(opener)
        with self.assertRaises(SourceBlocked):
            client.get_json("https://a.test/x")
        with self.assertRaises(SourceBlocked):
            client.get_json("https://a.test/y")
        self.assertEqual(len(calls), 1)

    def test_retries_transient_errors(self):
        attempts = []

        def opener(request, timeout):
            attempts.append(1)
            if len(attempts) < 2:
                raise urllib.error.HTTPError(request.full_url, 503, "busy", {}, None)
            return FakeResponse(b'{"data": []}')

        self.assertEqual(self.client(opener).get_json("https://a.test/x"), {"data": []})
        self.assertEqual(len(attempts), 2)

    def test_arctic_passes_window_and_cursor(self):
        seen = []

        def opener(request, timeout):
            query = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(request.full_url).query))
            seen.append(query)
            before = int(query.get("before", 10**12))
            rows = [r for r in listing(50_000, 150) if r["created_utc"] < before][:100]
            return FakeResponse(json.dumps({"data": rows}).encode())

        result = ArcticShiftSource(self.client(opener)).fetch_posts("SaaS", after=0, max_pages=5)
        self.assertEqual(len(result.posts), 150)
        self.assertEqual(seen[0]["after"], "0")
        self.assertNotIn("before", seen[0])
        self.assertIn("before", seen[1])


class CompositeTests(unittest.TestCase):
    def test_fallback_uses_next_source(self):
        good = FakeSource({"SaaS": [raw_post("a", "hello")]}, name="good")
        result = FallbackSource([FakeSource({}, name="bad", fail=True), good]).fetch_posts("SaaS", after=0, max_pages=1)
        self.assertEqual(result.source, "good")

    def test_fallback_reports_every_failure(self):
        with self.assertRaises(SourceError) as ctx:
            FallbackSource([FakeSource({}, name="a", fail=True), FakeSource({}, name="b", fail=True)]).probe()
        self.assertIn("a=http_503", str(ctx.exception))
        self.assertIn("b=http_503", str(ctx.exception))

    def test_cache_memoises_comments(self):
        inner = FakeSource({}, {"x": [{"id": "c", "body": "hi"}]})
        cached = CachedSource(inner)
        cached.fetch_comments("x", limit=5)
        cached.fetch_comments("x", limit=5)
        self.assertEqual(inner.comment_calls, ["x"])


if __name__ == "__main__":
    unittest.main()
