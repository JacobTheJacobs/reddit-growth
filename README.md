# Reddit Growth Miner

**Reddit Growth Miner by JacobTheJacobs** · [GitHub](https://github.com/JacobTheJacobs/reddit-growth)

**Mine public Reddit discussions for buying signals, switching intent, competitor gaps, recurring workarounds, and growth opportunities.**

Reddit Growth Miner is an evidence-first Reddit reconnaissance CLI built by JacobTheJacobs. Give it a target market and a subreddit set. It collects public posts, labels intent with transparent rules, groups repeated signals, and emits a source-linked report you can inspect before making a growth claim.

It is intentionally not an auto-reply bot and it does not pretend that correlation is causation.

## Quick start

Requirements: Python 3.10+. No third-party dependencies.

```bash
pip install -e .            # optional: installs the `reddit-growth-miner` command

python3 scripts/reddit_growth_miner.py plan \
  --target "AI coding tools"
```

Run a scan:

```bash
python3 scripts/reddit_growth_miner.py scan \
  --target "AI coding tools" \
  --subs LocalLLaMA,ClaudeAI,ChatGPTCoding,SideProject \
  --hours 168 \
  --min-score 5 \
  --min-comments 3 \
  --competitors "Cursor,Copilot=GitHub Copilot,Windsurf,Claude Code" \
  --fetch-comments \
  --out results.json
```

Render a readable report:

```bash
python3 scripts/reddit_growth_miner.py report \
  --input results.json \
  --out report.md
```

## What it looks for

The scanner labels observable discussion intent:

- `alternative_search` — looking for a replacement
- `recommendation_request` — asking what to use
- `purchase_intent` — explicit budget or willingness to pay
- `switching_story` — leaving a current tool
- `workaround_share` — manual/spreadsheet workaround
- `complaint` — recurring friction or failure
- `help_request` — blocked user trying to solve a problem
- `promotion` — promotional posts, kept separate from demand evidence

Labels are multi-label: "Notion is so slow, any alternative?" is both a `complaint` and an `alternative_search`. Promotion is a separate flag, so a promotional post never counts as demand, but replies to it still can.

With `--fetch-comments`, comments are classified with the same rules. A thread counts as demand evidence if the post *or* its replies carry a buying, switching or workaround signal; the report marks evidence found only in comments.

Posts are grouped into themes (pricing, switching, workflow friction, reliability, discovery, learning, distribution) by whole-word matching.

## Competitor landscape

Pass the tools you care about with `--competitors`. Aliases go after `=`, separated by `|`:

```bash
--competitors "Jira,Linear=linear.app|Linear App,Asana,Monday=monday.com"
```

The scan then reports how many threads mention each tool, every observed "switched from A to B" statement with links, and the net flow per tool. Without `--competitors`, only names that appear in comparison language ("alternative to X", "switched from X to Y", "X vs Y") are reported.

## Scoring

Clusters are ranked by a score that combines:

- **demand threads**: posts with a buying, switching or workaround signal (in the post or its comments)
- **breadth**: distinct subreddits
- **recency** within the scan window
- **relative engagement**: each post's score + 2×comments divided by the median for its own subreddit in the sample, so small communities are not drowned out by large ones

A theme becomes an opportunity only with at least two demand threads. Each opportunity carries a `low` / `medium` / `high` confidence band and a theme-specific next test with a success metric and kill condition, filled in with the tools people mention or leave.

## Example growth-research workflow

1. Start with a target: `"B2B teams using AI SDR tools"`.
2. Pick 3–8 relevant subreddits.
3. Scan a 7–14 day window.
4. Read the linked evidence in the strongest clusters.
5. Separate real demand from self-promotion and one-off complaints.
6. Form one falsifiable growth hypothesis.
7. Test it manually before automating anything.

The tool stops at evidence gathering. It does not auto-post or auto-message users.

## CLI

### Suggest subreddits

```bash
python3 scripts/reddit_growth_miner.py plan --target "SaaS founders"
```

### Scan only high-intent posts

```bash
python3 scripts/reddit_growth_miner.py scan \
  --target "SaaS founders looking for outbound tools" \
  --subs SaaS,startups,sales,Entrepreneur \
  --intents alternative_search,recommendation_request,purchase_intent,switching_story \
  --hours 336 \
  --out outbound-signals.json
```

### Use a custom rule pack

Copy `reddit_growth_miner/rules/default.json`, tune the intent regexes, theme terms or next-test templates for your market, and pass it in:

```bash
python3 scripts/reddit_growth_miner.py scan --target "..." --subs ... --rules my-rules.json
```

### Diagnose sources

```bash
python3 scripts/reddit_growth_miner.py diagnose
```

Reddit Growth Miner reads public Reddit archives (Arctic Shift, falling back to PullPush). It pages back through each subreddit until the scan window is covered or `--max-pages` (default 10 × 100 posts) runs out; a subreddit that ran out of pages is reported as `truncated` rather than silently cut short. A source that answers 403 or 429 is not contacted again for the rest of the run. It does not rotate proxies or bypass access controls.

`scan` exits with code 2 if every subreddit failed.

## Output

A scan JSON (`schema_version` 2.0) contains:

```json
{
  "schema_version": "2.0",
  "target": "AI coding tools",
  "subreddits": ["LocalLLaMA", "ClaudeAI"],
  "source_status": [{"subreddit": "LocalLLaMA", "status": "ok", "pages": 4, "kept": 31}],
  "posts": [{"intent": "alternative_search", "labels": [], "signals": {}, "competitors": [], "switches": [], "comments": []}],
  "analysis": {
    "intent_counts": {},
    "comment_intent_counts": {},
    "signal_clusters": [],
    "opportunities": [],
    "competitors": {"mentions": [], "switches": [], "net_flow": []}
  }
}
```

Each evidence item retains its Reddit URL so you can audit the result manually. See `examples/sample-output.json` and `examples/sample-report.md`.

`report --format json` re-emits the scan; `--format md` (default) renders Markdown.

## Agent skill

`SKILL.md` turns the CLI into a compact workflow for coding agents. The agent is instructed to gather evidence first, then form hypotheses from the linked threads instead of inventing demand.

## Project layout

```text
reddit_growth_miner/
├── domain/models.py      # frozen dataclasses: Post, Comment, Label, Signals, Switch, FetchResult
├── http.py               # HttpClient: per-host pacing, bounded retries, circuit breaker
├── sources/              # Source protocol + Arctic Shift / PullPush adapters
│   ├── base.py           #   paginate(): walk back with `before` cursors to the window start
│   └── composite.py      #   FallbackSource (try in order), CachedSource (memoise)
├── rules/default.json    # rule pack: intent regexes, promotion, theme terms, next-test templates
├── classify/             # Classifier protocol + RuleClassifier (multi-label)
├── analysis/
│   ├── entities.py       # competitor mentions and switch extraction
│   ├── enrich.py         # labels posts and comments, merges thread-level signals
│   ├── scoring.py        # relative engagement, recency, cluster score, confidence
│   └── clustering.py     # theme clusters, opportunities, competitor landscape
├── filters.py            # composable predicates: MinScore(5) & MinComments(3) & HasIntent(...)
├── config.py             # ScanConfig
├── pipeline.py           # ScanPipeline: collect → filter → enrich → comments → analyze
├── render/               # Markdown and JSON renderers
├── planner.py            # subreddit suggestions
└── cli.py                # thin argparse layer
```

Every stage depends on a protocol, not a concrete class, so a different source (e.g. Reddit's official API) or classifier (e.g. an LLM) can be swapped in without touching the pipeline. Tests use an in-memory `FakeSource`.

Run tests: `python3 -m unittest discover -s tests -t tests`

## Safety / data handling

- Public Reddit content only.
- No login bypass, proxy rotation, or anti-bot evasion.
- No automated replies or unsolicited messaging.
- No author profiling; the output is about discussion signals, not people.
- Treat a cluster as evidence worth reading, not proof that a market exists.

## License

MIT. See `LICENSE`.
