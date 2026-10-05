from __future__ import annotations

import math
from collections import defaultdict
from statistics import median

from ..domain import Post


class EngagementScorer:
    """Scores posts and clusters so that rankings are comparable across communities.

    Engagement is normalised by the median engagement of the post's own community
    in this sample, so a 40-upvote thread in a small subreddit is not drowned out
    by a 400-upvote thread in a huge one.
    """

    def __init__(self, posts: list[Post], *, now: float, window_hours: float):
        self.now = now
        self.window_seconds = max(1.0, window_hours * 3600)
        by_community: dict[str, list[int]] = defaultdict(list)
        for post in posts:
            by_community[post.community].append(post.engagement)
        self._median = {c: max(1.0, float(median(v))) for c, v in by_community.items()}

    def relative_engagement(self, post: Post) -> float:
        return min(5.0, post.engagement / self._median.get(post.community, 1.0))

    def recency(self, post: Post) -> float:
        if not post.created_utc:
            return 0.5
        age = max(0.0, self.now - post.created_utc)
        return math.exp(-age / self.window_seconds)

    def post_strength(self, post: Post) -> float:
        demand = 1.0 if post.signals.demand else 0.0
        return round(2.0 * demand + math.log1p(self.relative_engagement(post)) + 0.5 * self.recency(post), 4)

    def cluster_score(self, members: list[Post]) -> float:
        demand_threads = sum(1 for p in members if p.signals.demand)
        communities = len({p.community for p in members})
        recency = sum(self.recency(p) for p in members) / len(members) if members else 0.0
        engagement = sum(math.log1p(self.relative_engagement(p)) for p in members)
        return round(demand_threads * (1 + math.log1p(communities)) * (0.5 + 0.5 * recency) + 0.5 * engagement, 2)


def confidence(demand_threads: int, communities: int) -> str:
    if demand_threads >= 6 and communities >= 3:
        return "high"
    if demand_threads >= 3 and communities >= 2:
        return "medium"
    return "low"
