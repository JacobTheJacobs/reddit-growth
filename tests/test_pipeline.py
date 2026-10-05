import json
import tempfile
import unittest
from pathlib import Path

from reddit_growth_miner import cli
from reddit_growth_miner.analysis import Enricher, EntityExtractor
from reddit_growth_miner.classify import RuleClassifier
from reddit_growth_miner.config import ScanConfig
from reddit_growth_miner.pipeline import ScanPipeline
from reddit_growth_miner.render import render_markdown
from reddit_growth_miner.rules import RuleSet

from fakes import NOW, FakeSource, raw_post

RULES = RuleSet.load()


def pipeline(source, competitors=""):
    enricher = Enricher(RuleClassifier(RULES), EntityExtractor.parse(competitors))
    return ScanPipeline(source, enricher, RULES, clock=lambda: NOW)


POSTS = {
    "SaaS": [
        raw_post("a1", "Any alternative to Jira? Pricing is too expensive", score=40, comments=20),
        raw_post("a2", "Switched from Jira to Linear, cost was killing us", score=8, comments=4, age_hours=100),
        raw_post("a3", "We just launched our standup bot", score=100, comments=30),
        raw_post("old", "Alternative to Jira?", age_hours=500),
    ],
    "projectmanagement": [
        raw_post("b1", "Looking for a cheaper alternative to Jira for a 5 person team", sub="projectmanagement", score=6, comments=3),
        raw_post("x1", "Switched from Jira to Linear, cost was killing us", sub="projectmanagement", score=2, comments=1),
        raw_post("b2", "Our weekly planning is all manually in a spreadsheet", sub="projectmanagement", score=3, comments=9),
    ],
}


class PipelineTests(unittest.TestCase):
    def run_scan(self, **overrides):
        cfg = ScanConfig(target="PM tools", subreddits=("SaaS", "projectmanagement"), min_score=0, min_comments=0, **overrides)
        return pipeline(FakeSource(POSTS), competitors="Jira,Linear").run(cfg)

    def test_window_and_dedupe(self):
        result = self.run_scan()
        ids = [p["id"] for p in result["posts"]]
        self.assertNotIn("old", ids)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertNotIn("x1", ids)  # crosspost of a2

    def test_pricing_opportunity_ranked_with_competitors(self):
        analysis = self.run_scan()["analysis"]
        opp = {o["theme"]: o for o in analysis["opportunities"]}
        self.assertIn("pricing", opp)
        self.assertIn("switching", opp)
        self.assertIn("importer from Jira.", opp["switching"]["next_test"])
        pricing = next(c for c in analysis["signal_clusters"] if c["theme"] == "pricing")
        self.assertEqual(pricing["communities"], ["r/SaaS", "r/projectmanagement"])
        self.assertEqual(pricing["top_competitors"][0], "Jira")

    def test_clusters_sorted_by_score_and_evidence_by_strength(self):
        clusters = self.run_scan()["analysis"]["signal_clusters"]
        scores = [c["score"] for c in clusters]
        self.assertEqual(scores, sorted(scores, reverse=True))
        for c in clusters:
            strengths = [e["strength"] for e in c["evidence"]]
            self.assertEqual(strengths, sorted(strengths, reverse=True))

    def test_competitor_landscape(self):
        comp = self.run_scan()["analysis"]["competitors"]
        self.assertEqual(comp["mentions"][0], {"name": "Jira", "threads": 3})
        self.assertEqual(comp["switches"][0]["from"], "Jira")
        self.assertEqual(comp["net_flow"][0], {"name": "Linear", "net": 1})

    def test_intent_filter_runs_before_comment_fetch(self):
        source = FakeSource(POSTS)
        cfg = ScanConfig(target="x", subreddits=("SaaS",), min_score=0, min_comments=0,
                         intents=frozenset({"switching_story"}), fetch_comments=True)
        result = pipeline(source).run(cfg)
        self.assertEqual([p["id"] for p in result["posts"]], ["a2"])
        self.assertEqual(source.comment_calls, ["a2"])

    def test_source_failure_is_reported(self):
        cfg = ScanConfig(target="x", subreddits=("SaaS",))
        result = pipeline(FakeSource({}, fail=True)).run(cfg)
        self.assertEqual(result["source_status"][0]["status"], "error")
        self.assertEqual(result["posts"], [])

    def test_markdown_report(self):
        text = render_markdown(self.run_scan())
        self.assertIn("## Competitor landscape", text)
        self.assertIn("Jira → Linear", text)
        self.assertIn("## Candidate growth opportunities", text)


class CliTests(unittest.TestCase):
    def test_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "plan.json"
            self.assertEqual(cli.main(["plan", "--target", "AI coding agents", "--out", str(out)]), 0)
            self.assertIn("LocalLLaMA", json.loads(out.read_text())["suggested_subreddits"])

    def test_plan_matches_whole_words(self):
        from reddit_growth_miner.planner import suggest_subreddits
        self.assertNotIn("LocalLLaMA", suggest_subreddits("email marketing for retail"))
        self.assertIn("LocalLLaMA", suggest_subreddits("AI agents"))

    def test_scan_then_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            scan_out, report_out = Path(tmp) / "scan.json", Path(tmp) / "report.md"
            args = cli.build_parser().parse_args([
                "scan", "--target", "PM tools", "--subs", "r/SaaS", "--min-score", "0", "--min-comments", "0",
                "--hours", "1000000", "--competitors", "Jira", "--out", str(scan_out),
            ])
            self.assertEqual(cli.cmd_scan(args, source=FakeSource(POSTS)), 0)
            payload = json.loads(scan_out.read_text())
            self.assertEqual(payload["schema_version"], "2.0")
            self.assertEqual(payload["subreddits"], ["SaaS"])
            self.assertEqual(cli.main(["report", "--input", str(scan_out), "--out", str(report_out)]), 0)
            self.assertIn("# Reddit Growth Report: PM tools", report_out.read_text())

    def test_scan_exit_code_when_all_sources_fail(self):
        args = cli.build_parser().parse_args(["scan", "--target", "x", "--subs", "SaaS", "--out", "/dev/null"])
        self.assertEqual(cli.cmd_scan(args, source=FakeSource({}, fail=True)), 2)


if __name__ == "__main__":
    unittest.main()
