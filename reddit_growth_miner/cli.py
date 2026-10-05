from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .analysis import Enricher, EntityExtractor
from .classify import RuleClassifier
from .config import ScanConfig
from .pipeline import ScanPipeline
from .planner import suggest_subreddits
from .render import RENDERERS
from .rules import RuleSet
from .sources import Source, SourceError, build_source


def _emit(text: str, path: str | None) -> None:
    if path:
        Path(path).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


def _write_json(payload: Any, path: str | None) -> None:
    _emit(json.dumps(payload, ensure_ascii=False, indent=2), path)


def _split(value: str | None) -> list[str]:
    return [v.strip() for v in (value or "").split(",") if v.strip()]


def cmd_plan(args: argparse.Namespace) -> int:
    _write_json({"target": args.target, "suggested_subreddits": suggest_subreddits(args.target, max_subs=args.max_subs)}, args.out)
    return 0


def config_from_args(args: argparse.Namespace) -> ScanConfig:
    subs = _split(args.subs) or suggest_subreddits(args.target, max_subs=args.max_subs)
    return ScanConfig(
        target=args.target,
        subreddits=tuple(s.removeprefix("r/") for s in subs),
        hours=args.hours,
        min_score=args.min_score,
        min_comments=args.min_comments,
        intents=frozenset(_split(args.intents)),
        fetch_comments=args.fetch_comments,
        comment_limit=args.comment_limit,
        max_pages=args.max_pages,
        competitors=args.competitors or "",
    )


def build_pipeline(args: argparse.Namespace, source: Source | None = None) -> ScanPipeline:
    rules = RuleSet.load(args.rules)
    enricher = Enricher(RuleClassifier(rules), EntityExtractor.parse(args.competitors))
    return ScanPipeline(source or build_source(fallback=args.fallback), enricher, rules)


def cmd_scan(args: argparse.Namespace, source: Source | None = None) -> int:
    result = build_pipeline(args, source).run(config_from_args(args))
    _write_json(result, args.out)
    return 0 if any(s["status"] != "error" for s in result["source_status"]) else 2


def cmd_report(args: argparse.Namespace) -> int:
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    _emit(RENDERERS[args.format](payload), args.out)
    return 0


def cmd_diagnose(args: argparse.Namespace, sources: list[Source] | None = None) -> int:
    from .http import HttpClient
    from .sources.arctic import ArcticShiftSource
    from .sources.pullpush import PullPushSource

    http = HttpClient(max_retries=0)
    checks = {}
    for source in sources or [ArcticShiftSource(http), PullPushSource(http)]:
        try:
            source.probe()
            checks[source.name] = {"status": "ok"}
        except SourceError as error:
            checks[source.name] = {"status": "unavailable", "reason": error.reason}
    _write_json(checks, args.out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="reddit-growth-miner", description="Evidence-first Reddit growth signal scanner")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("plan", help="Suggest subreddits for a target market")
    p.add_argument("--target", required=True)
    p.add_argument("--max-subs", type=int, default=8)
    p.add_argument("--out")
    p.set_defaults(func=cmd_plan)

    s = sub.add_parser("scan", help="Scan Reddit for buying, switching, complaint and workaround signals")
    s.add_argument("--target", required=True)
    s.add_argument("--subs", help="Comma-separated subreddit names; otherwise use a small heuristic plan")
    s.add_argument("--hours", type=int, default=168)
    s.add_argument("--max-pages", type=int, default=10, help="Pages of 100 posts per subreddit (default 10)")
    s.add_argument("--max-subs", type=int, default=8)
    s.add_argument("--min-score", type=int, default=5)
    s.add_argument("--min-comments", type=int, default=3)
    s.add_argument("--intents", help="Comma-separated intent filter, e.g. alternative_search,recommendation_request,purchase_intent")
    s.add_argument("--competitors", help='Tracked tools, e.g. "Notion,Linear=linear.app|Linear App,Jira"')
    s.add_argument("--rules", help="Path to a custom rule pack JSON (defaults to the bundled one)")
    s.add_argument("--fetch-comments", action="store_true")
    s.add_argument("--comment-limit", type=int, default=50)
    s.add_argument("--no-fallback", dest="fallback", action="store_false")
    s.set_defaults(fallback=True)
    s.add_argument("--out")
    s.set_defaults(func=cmd_scan)

    r = sub.add_parser("report", help="Render a report from a scan JSON")
    r.add_argument("--input", required=True)
    r.add_argument("--format", choices=sorted(RENDERERS), default="md")
    r.add_argument("--out")
    r.set_defaults(func=cmd_report)

    d = sub.add_parser("diagnose", help="Check public Reddit data sources")
    d.add_argument("--out")
    d.set_defaults(func=cmd_diagnose)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
