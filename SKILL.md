---
name: reddit-growth-miner
description: >
  Evidence-first Reddit growth reconnaissance. Collects public posts from selected
  subreddits, labels buying/switching/recommendation/workaround signals, groups
  repeat patterns, and renders a source-linked report for growth experiments.
---

# Reddit Growth Miner

Project: `JacobTheJacobs/reddit-growth`

Use this skill when the user wants to research a market through Reddit before running a growth experiment.

## Standard workflow

1. Define the target market in one sentence.
2. Choose 3–8 relevant subreddits.
3. Scan a bounded time window.
4. Inspect high-intent evidence manually.
5. Form a falsifiable hypothesis only from repeated, source-linked signals.
6. Recommend the smallest legitimate test. Do not auto-post or impersonate users.

```bash
python3 scripts/reddit_growth_miner.py scan \
  --target "AI coding tools" \
  --subs LocalLLaMA,ClaudeAI,ChatGPTCoding,SideProject \
  --hours 168 \
  --min-score 5 --min-comments 3 \
  --competitors "Cursor,Copilot=GitHub Copilot,Windsurf" \
  --fetch-comments \
  --out /tmp/reddit-growth.json

python3 scripts/reddit_growth_miner.py report \
  --input /tmp/reddit-growth.json \
  --out /tmp/reddit-growth.md
```

## Evidence rules

- A high score is attention, not purchase intent.
- Promotion is not demand evidence.
- A single thread is not a repeatable pattern.
- Keep the original Reddit URLs in every claim.
- If data sources are blocked or rate limited, report the failure rather than routing around access controls.
- If a subreddit's `source_status` is `truncated`, say the window was not fully covered (or rerun with a higher `--max-pages`).
- Treat a cluster's `confidence` as a floor on how hard to claim it: `low` means "worth reading", not "a market".
- Do not infer private traits about Reddit users.
- Do not recommend spam, fake personas, vote manipulation, or automated posting intended to look human.

## Useful high-intent filters

```bash
--intents alternative_search,recommendation_request,purchase_intent,switching_story
```

## Final answer shape

Return:

1. Target and sample window.
2. Strongest repeated signals.
3. Direct links to the evidence.
4. What is still unknown.
5. One cheap experiment with a clear success metric and kill condition.
