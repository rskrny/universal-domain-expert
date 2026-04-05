"""
Reddit Intelligence Scanner.

Pulls top posts from subreddits aligned with the user's interests,
scores them for quality and relevance, and produces a curated digest.

Quality scoring is based on engagement signals within each post:
- Upvote ratio (community consensus)
- Comment-to-upvote ratio (discussion depth)
- Award density (community recognition)
- Age-adjusted score (momentum, not just total)
- Content type bonus (tutorials, tools, launches get boosted)

Run: python -m dashboard.reddit_scanner
"""

import os
import time
import math
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("dashboard.reddit_scanner")


# Subreddits grouped by interest category, weighted by user's engagement patterns
SUBREDDIT_CONFIG = {
    # AI/ML (primary interest based on upvotes + saves)
    "ai_agents": {
        "subs": ["vibecoding", "AI_Agents", "AIAgentsInAction", "ClaudeAI", "ChatGPTCoding"],
        "weight": 1.5,  # highest interest signal
        "posts_per_sub": 10,
    },
    "ai_core": {
        "subs": ["LocalLLaMA", "MachineLearning", "artificial", "Rag", "PromptEngineering"],
        "weight": 1.3,
        "posts_per_sub": 10,
    },
    "startup_business": {
        "subs": ["SaaS", "startups", "Entrepreneur", "indiehackers"],
        "weight": 1.0,
        "posts_per_sub": 8,
    },
    "tech_programming": {
        "subs": ["programming", "webdev", "selfhosted", "devops", "Futurology"],
        "weight": 0.8,
        "posts_per_sub": 5,
    },
    # Foundational theory: feeds reasoning/architecture improvements for domain agents
    "theory_reasoning": {
        "subs": [
            "QuantumComputing", "InformationTheory", "compsci",
            "PhilosophyofScience", "CognitiveScience", "complexity",
            "SystemsThinking", "CategoryTheory",
        ],
        "weight": 1.1,
        "posts_per_sub": 5,
    },
}

# Content signals that boost quality score
BOOST_KEYWORDS = {
    "tutorial": 0.15,
    "guide": 0.15,
    "launch": 0.1,
    "released": 0.1,
    "open source": 0.15,
    "tool": 0.1,
    "framework": 0.1,
    "built": 0.1,
    "how i": 0.1,
    "how to": 0.1,
    "ama": 0.1,
    "breakdown": 0.1,
}

# Content signals that reduce quality score
PENALTY_KEYWORDS = {
    "meme": -0.2,
    "hiring": -0.3,
    "promotion": -0.2,
    "self-promotion": -0.3,
    "weekly thread": -0.4,
    "monthly thread": -0.4,
    "megathread": -0.3,
}


def _load_env():
    """Load .env file."""
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def _get_reddit():
    """Create authenticated Reddit instance."""
    import praw
    _load_env()
    return praw.Reddit(
        client_id=os.environ["REDDIT_CLIENT_ID"],
        client_secret=os.environ["REDDIT_CLIENT_SECRET"],
        user_agent="personal-intelligence-scanner/1.0 by slamjacket",
        username=os.environ.get("REDDIT_USERNAME", ""),
        password=os.environ.get("REDDIT_PASSWORD", ""),
    )


def score_post(post, category_weight: float = 1.0) -> float:
    """Score a post based on engagement quality signals.

    Returns a score from 0 to 1 where higher = more valuable.

    Signals used:
    1. Upvote ratio: how much the community agrees (0.5 = controversial, 0.95 = strong consensus)
    2. Engagement depth: comments/upvotes ratio. More discussion = more valuable.
    3. Momentum: score divided by age in hours. Catches fast-rising posts.
    4. Content type: keyword boosts for tutorials, tools, launches.
    5. Category weight: user's demonstrated interest level per subreddit group.
    """
    now = time.time()
    age_hours = max(1, (now - post.created_utc) / 3600)

    # 1. Upvote ratio (0 to 1, already provided by Reddit)
    ratio_score = post.upvote_ratio  # 0.0 to 1.0

    # 2. Engagement depth (comments relative to score)
    score = max(post.score, 1)
    comments = post.num_comments
    # Sweet spot: 0.1-0.5 comments per upvote indicates real discussion
    comment_ratio = min(comments / score, 1.0)
    engagement_score = min(1.0, comment_ratio * 2)  # normalize to 0-1

    # 3. Momentum (age-adjusted popularity)
    # log scale prevents very old popular posts from dominating
    momentum = math.log1p(score) / math.log1p(age_hours)
    momentum_normalized = min(1.0, momentum / 5)  # normalize

    # 4. Content type keywords
    title_lower = post.title.lower()
    content_boost = 0.0
    for keyword, boost in BOOST_KEYWORDS.items():
        if keyword in title_lower:
            content_boost += boost
    for keyword, penalty in PENALTY_KEYWORDS.items():
        if keyword in title_lower:
            content_boost += penalty
    content_boost = max(-0.3, min(0.3, content_boost))  # clamp

    # 5. Combine signals
    raw_score = (
        ratio_score * 0.20 +
        engagement_score * 0.25 +
        momentum_normalized * 0.35 +
        0.20  # base
    ) * category_weight + content_boost

    return round(max(0.0, min(1.0, raw_score)), 4)


def scan_subreddits(
    time_filter: str = "day",
    min_score: float = 0.3,
    max_results: int = 30,
    verbose: bool = False,
) -> list[dict]:
    """Scan configured subreddits and return scored, ranked posts.

    Args:
        time_filter: "hour", "day", "week" for Reddit's top filter
        min_score: minimum quality score to include
        max_results: maximum posts to return
        verbose: print progress

    Returns:
        List of post dicts sorted by quality score descending
    """
    reddit = _get_reddit()
    all_posts = []

    for category, config in SUBREDDIT_CONFIG.items():
        weight = config["weight"]
        posts_per = config["posts_per_sub"]

        for sub_name in config["subs"]:
            try:
                sub = reddit.subreddit(sub_name)
                posts = list(sub.top(time_filter=time_filter, limit=posts_per))

                if not posts:
                    # Fall back to hot if top is empty
                    posts = list(sub.hot(limit=posts_per))

                for post in posts:
                    if post.stickied:
                        continue  # skip pinned posts

                    quality = score_post(post, weight)
                    if quality < min_score:
                        continue

                    all_posts.append({
                        "title": post.title,
                        "subreddit": str(post.subreddit),
                        "category": category,
                        "score": post.score,
                        "comments": post.num_comments,
                        "upvote_ratio": post.upvote_ratio,
                        "quality": quality,
                        "url": f"https://reddit.com{post.permalink}",
                        "created_utc": post.created_utc,
                        "age_hours": round((time.time() - post.created_utc) / 3600, 1),
                        "selftext_preview": (post.selftext or "")[:200],
                        "is_link": not post.is_self,
                        "link_url": post.url if not post.is_self else None,
                    })

                if verbose:
                    print(f"  r/{sub_name}: {len(posts)} posts scanned")

            except Exception as e:
                logger.warning("Failed to scan r/%s: %s", sub_name, e)
                if verbose:
                    print(f"  r/{sub_name}: ERROR - {e}")

    # Sort by quality score, deduplicate by title similarity
    all_posts.sort(key=lambda x: x["quality"], reverse=True)

    # Simple dedup: skip posts with very similar titles
    seen_titles = set()
    deduped = []
    for post in all_posts:
        title_key = post["title"].lower()[:50]
        if title_key not in seen_titles:
            seen_titles.add(title_key)
            deduped.append(post)

    return deduped[:max_results]


def format_digest(posts: list[dict], title: str = "Reddit Intelligence Digest") -> str:
    """Format scored posts into a readable digest."""
    lines = [f"# {title}", f"## {datetime.now().strftime('%B %d, %Y')}", ""]

    # Group by category
    categories = {}
    for post in posts:
        cat = post["category"]
        categories.setdefault(cat, []).append(post)

    category_labels = {
        "ai_agents": "AI Agents & Vibe Coding",
        "ai_core": "AI/ML Core",
        "startup_business": "Startups & Business",
        "tech_programming": "Tech & Programming",
    }

    for cat_key, cat_posts in categories.items():
        label = category_labels.get(cat_key, cat_key)
        lines.append(f"### {label}")
        lines.append("")

        for i, post in enumerate(cat_posts[:8], 1):
            quality_bar = "+" * min(5, int(post["quality"] * 5))
            lines.append(
                f"**{i}. [{post['title'][:80]}]({post['url']})** "
                f"(r/{post['subreddit']})"
            )
            lines.append(
                f"   Score: {post['score']:,} | Comments: {post['comments']} | "
                f"Quality: [{quality_bar}] {post['quality']:.2f}"
            )
            if post.get("selftext_preview"):
                preview = post["selftext_preview"].replace("\n", " ")[:120]
                lines.append(f"   > {preview}...")
            lines.append("")

    lines.append(f"*Scanned {len(posts)} posts across {len(SUBREDDIT_CONFIG)} categories*")
    return "\n".join(lines)


def run_scan(verbose: bool = True) -> dict:
    """Run a full scan and return the digest."""
    if verbose:
        print("Scanning Reddit...")

    posts = scan_subreddits(time_filter="day", min_score=0.25, max_results=30, verbose=verbose)

    if verbose:
        print(f"\nFound {len(posts)} quality posts")

    digest = format_digest(posts)

    if verbose:
        print("\n" + digest)

    return {
        "posts": posts,
        "digest": digest,
        "scanned_at": time.time(),
        "count": len(posts),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_scan(verbose=True)
