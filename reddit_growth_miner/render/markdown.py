from __future__ import annotations

from typing import Any


def _link(item: dict[str, Any]) -> str:
    title = (item.get("title") or "(untitled)").replace("[", "(").replace("]", ")")
    return f"[{title}]({item.get('url')})"


def render_markdown(payload: dict[str, Any]) -> str:
    analysis = payload.get("analysis", {})
    statuses = payload.get("source_status", [])
    lines = [
        f"# Reddit Growth Report: {payload.get('target', 'unknown target')}",
        "",
        "## Scope",
        f"- Window: {payload.get('window_hours', '?')} hours",
        f"- Subreddits: {', '.join(payload.get('subreddits', [])) or 'none'}",
        f"- Posts kept: {analysis.get('post_count', len(payload.get('posts', [])))}",
    ]
    problems = [s for s in statuses if s.get("status") != "ok"]
    for s in problems:
        lines.append(f"- **{s.get('status')}** r/{s.get('subreddit')}: {s.get('reason', '')}")
    lines.append("")

    lines.append("## Candidate growth opportunities")
    opportunities = analysis.get("opportunities", [])
    if not opportunities:
        lines.append("No theme reached two independent demand threads. Read the evidence before making a growth claim.")
    for item in opportunities:
        why = item.get("why_it_matters", {})
        lines.extend([
            f"### {item.get('theme')} — score {item.get('score')} ({item.get('confidence')} confidence)",
            f"- Demand threads: {why.get('demand_threads')} across {why.get('community_count')} "
            f"{'community' if why.get('community_count') == 1 else 'communities'}",
            f"- Buying / switching / workaround: {why.get('buying_signals')} / {why.get('switching_signals')} / {why.get('workaround_signals')}",
            f"- Next test: {item.get('next_test')}",
            "",
        ])

    competitors = analysis.get("competitors", {})
    if competitors.get("mentions") or competitors.get("switches"):
        lines.append("## Competitor landscape")
        if competitors.get("mentions"):
            lines.append("| Tool | Threads mentioning |")
            lines.append("|---|---|")
            lines.extend(f"| {m['name']} | {m['threads']} |" for m in competitors["mentions"][:15])
            lines.append("")
        if competitors.get("switches"):
            lines.append("**Observed switches**")
            for s in competitors["switches"][:15]:
                refs = " ".join(f"[{i + 1}]({u})" for i, u in enumerate(s.get("evidence", [])))
                lines.append(f"- {s['from']} → {s['to']} ×{s['count']} {refs}")
            lines.append("")

    lines.append("## Signal clusters")
    clusters = analysis.get("signal_clusters", [])
    if not clusters:
        lines.append("No posts cleared the current filters.")
    for cluster in clusters:
        lines.extend([
            f"### {cluster.get('theme')} — score {cluster.get('score')}",
            f"- Posts: {cluster.get('posts')} (demand threads: {cluster.get('demand_threads')}, promotion: {cluster.get('promotion_posts')})",
            f"- Communities: {', '.join(cluster.get('communities', []))}",
        ])
        if cluster.get("top_competitors"):
            lines.append(f"- Tools mentioned: {', '.join(cluster['top_competitors'])}")
        lines.append("- Strongest evidence:")
        for item in cluster.get("evidence", []):
            via = " (signal in comments)" if item.get("signal_from_comments") else ""
            lines.append(f"  - {_link(item)} — {item.get('community')} · {item.get('intent')}{via}")
        lines.append("")

    lines.extend(["## Raw evidence", ""])
    for post in payload.get("posts", []):
        lines.append(
            f"- {_link(post)} — {post.get('community')} · score {post.get('score')} · "
            f"{post.get('num_comments')} comments · {post.get('intent')}"
        )
        for comment in post.get("comments", []):
            labels = ", ".join(l["intent"] for l in comment.get("labels", [])) or "context"
            lines.append(f"  - > {comment.get('body', '')[:200]} _({labels}, score {comment.get('score')})_")
    lines.append("")
    lines.append("_This report surfaces evidence; it does not prove causality or guarantee that a growth tactic will work._")
    return "\n".join(lines)
