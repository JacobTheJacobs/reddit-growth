from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from ..domain import Post
from ..rules import RuleSet
from .scoring import EngagementScorer, confidence

MIN_DEMAND_THREADS = 2


def _evidence(post: Post, scorer: EngagementScorer) -> dict[str, Any]:
    return {
        "title": post.title,
        "url": post.url,
        "community": post.community,
        "intent": post.intent,
        "strength": scorer.post_strength(post),
        "signal_from_comments": post.signals.from_comments,
    }


def competitor_landscape(posts: list[Post]) -> dict[str, Any]:
    mentions: Counter[str] = Counter()
    flows: Counter[tuple[str, str]] = Counter()
    flow_evidence: dict[tuple[str, str], list[str]] = defaultdict(list)
    for post in posts:
        mentions.update(set(post.competitors))  # threads mentioning, not raw mention count
        for switch in post.switches:
            key = (switch.source, switch.target)
            flows[key] += 1
            if len(flow_evidence[key]) < 3:
                flow_evidence[key].append(post.url)
    net: Counter[str] = Counter()
    for (source, target), count in flows.items():
        net[target] += count
        net[source] -= count
    return {
        "mentions": [{"name": n, "threads": c} for n, c in mentions.most_common()],
        "switches": [
            {"from": s, "to": t, "count": c, "evidence": flow_evidence[(s, t)]}
            for (s, t), c in flows.most_common()
        ],
        "net_flow": [{"name": n, "net": c} for n, c in sorted(net.items(), key=lambda kv: (-kv[1], kv[0]))],
    }


def analyze(posts: list[Post], *, rules: RuleSet, now: float, window_hours: float) -> dict[str, Any]:
    scorer = EngagementScorer(posts, now=now, window_hours=window_hours)
    clusters: dict[str, list[Post]] = defaultdict(list)
    for post in posts:
        for theme in post.themes or ("general",):
            clusters[theme].append(post)

    ranked = []
    for theme, members in clusters.items():
        demand_threads = sum(1 for p in members if p.signals.demand)
        communities = sorted({p.community for p in members})
        competitors = Counter(n for p in members for n in set(p.competitors))
        leaving = Counter(sw.source for p in members for sw in p.switches)
        ranked.append({
            "theme": theme,
            "score": scorer.cluster_score(members),
            "confidence": confidence(demand_threads, len(communities)),
            "posts": len(members),
            "demand_threads": demand_threads,
            "communities": communities,
            "buying_signals": sum(p.signals.buying for p in members),
            "switching_signals": sum(p.signals.switching for p in members),
            "workaround_signals": sum(p.signals.workaround for p in members),
            "promotion_posts": sum(p.signals.promotion for p in members),
            "top_competitors": [n for n, _ in competitors.most_common(5)],
            "tools_left": [n for n, _ in leaving.most_common(5)],
            "evidence": [_evidence(p, scorer) for p in sorted(members, key=scorer.post_strength, reverse=True)[:5]],
        })
    ranked.sort(key=lambda c: (-c["score"], c["theme"]))
    for i, cluster in enumerate(ranked, 1):
        cluster["signal_id"] = f"signal_{i:03d}"

    opportunities = []
    for cluster in ranked:
        if cluster["demand_threads"] < MIN_DEMAND_THREADS:
            continue
        template = rules.next_tests.get(cluster["theme"]) or rules.next_tests.get("default", "")
        named = ", ".join(cluster["top_competitors"][:3]) or "the tools people mention"
        opportunities.append({
            "theme": cluster["theme"],
            "signal_id": cluster["signal_id"],
            "score": cluster["score"],
            "confidence": cluster["confidence"],
            "why_it_matters": {
                "demand_threads": cluster["demand_threads"],
                "community_count": len(cluster["communities"]),
                "buying_signals": cluster["buying_signals"],
                "switching_signals": cluster["switching_signals"],
                "workaround_signals": cluster["workaround_signals"],
            },
            "next_test": template.replace("{competitors}", named).replace("{leaving}", ", ".join(cluster["tools_left"][:3]) or named),
        })

    return {
        "post_count": len(posts),
        "communities": dict(Counter(p.community for p in posts)),
        "intent_counts": dict(Counter(p.intent for p in posts)),
        "comment_intent_counts": dict(Counter(i for p in posts for i in p.comment_intents)),
        "signal_clusters": ranked,
        "opportunities": opportunities,
        "competitors": competitor_landscape(posts),
    }
