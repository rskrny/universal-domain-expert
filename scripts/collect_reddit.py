"""
Expanded Reddit Collection.

Pulls all engagement signals from the user's Reddit account:
  - Saved posts (existing behavior)
  - Upvoted posts (new: stronger signal of approval)
  - User's own comments (new: what you argued about reveals what you care about)

Merges everything into a single enriched dataset with engagement weighting.

Usage:
    python scripts/collect_reddit.py                 # Full collection
    python scripts/collect_reddit.py --saved-only    # Just saved posts (fast)
    python scripts/collect_reddit.py --stats          # Show collection stats
    python scripts/collect_reddit.py --dry-run        # Preview without writing
"""

import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

OUTPUT_PATH = ROOT / "state" / "reddit_full_collection.json"
SAVED_POSTS_PATH = Path("C:/Users/rskrn/Desktop/reddit api/saved_posts_raw.json")


def get_reddit_client():
    """Create authenticated PRAW client using .env credentials."""
    import praw

    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    username = os.getenv("REDDIT_USERNAME")
    password = os.getenv("REDDIT_PASSWORD")

    if not all([client_id, client_secret, username, password]):
        raise ValueError("Missing Reddit credentials in .env")

    return praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        user_agent=f"domain-expert:v2.0 (by /u/{username})",
        username=username,
        password=password,
        requestor_kwargs={"timeout": 30},
    )


def fetch_upvoted_posts(reddit, limit: int = 500) -> list:
    """
    Fetch posts the user upvoted. This is a stronger approval signal than
    just scrolling past something. Reddit API caps at ~1000 items.
    """
    print(f"  Fetching upvoted posts (limit={limit})...")
    posts = []
    try:
        for item in reddit.user.me().upvoted(limit=limit):
            from praw.models import Submission
            if not isinstance(item, Submission):
                continue
            try:
                posts.append({
                    "id": item.id,
                    "title": item.title,
                    "selftext": item.selftext or "",
                    "url": item.url,
                    "subreddit": str(item.subreddit),
                    "author": str(item.author) if item.author else "[deleted]",
                    "created_utc": item.created_utc,
                    "created_date": datetime.fromtimestamp(
                        item.created_utc, tz=timezone.utc
                    ).strftime("%Y-%m-%d"),
                    "score": item.score,
                    "num_comments": item.num_comments,
                    "permalink": f"https://reddit.com{item.permalink}",
                    "comments": [],  # Skip comment fetching for upvotes (too slow)
                    "_engagement_type": "upvoted",
                })
            except Exception:
                continue
    except Exception as e:
        print(f"  WARNING: Could not fetch upvoted posts: {e}")
        print(f"  (This endpoint may be restricted by Reddit. Continuing with saved posts.)")

    print(f"  Got {len(posts)} upvoted posts")
    return posts


def fetch_user_comments(reddit, limit: int = 200) -> list:
    """
    Fetch the user's own comments. What you wrote responses about reveals
    what topics triggered you enough to engage deeply.

    Returns structured comment data with the parent post context.
    """
    print(f"  Fetching user comments (limit={limit})...")
    username = os.getenv("REDDIT_USERNAME")
    comments = []

    try:
        redditor = reddit.redditor(username)
        for comment in redditor.comments.new(limit=limit):
            try:
                # Get parent post for context
                submission = comment.submission
                comments.append({
                    "comment_id": comment.id,
                    "comment_body": comment.body[:2000],
                    "comment_score": comment.score,
                    "comment_created": comment.created_utc,
                    "comment_date": datetime.fromtimestamp(
                        comment.created_utc, tz=timezone.utc
                    ).strftime("%Y-%m-%d"),
                    "parent_post_id": submission.id,
                    "parent_post_title": submission.title,
                    "parent_subreddit": str(submission.subreddit),
                    "parent_score": submission.score,
                    "_engagement_type": "commented",
                })
            except Exception:
                continue
    except Exception as e:
        print(f"  WARNING: Could not fetch comments: {e}")

    print(f"  Got {len(comments)} user comments")
    return comments


def merge_collection(saved: list, upvoted: list, comments: list) -> list:
    """
    Merge all sources into a unified collection with engagement scoring.

    Posts that appear in multiple sources get boosted engagement.
    """
    # Build lookup by post ID
    collection = {}

    # Start with saved posts (baseline engagement)
    for post in saved:
        pid = post["id"]
        post["_signals"] = {"saved": True, "upvoted": False, "commented": False}
        post["_comment_body"] = None
        collection[pid] = post

    # Merge upvoted posts
    for post in upvoted:
        pid = post["id"]
        if pid in collection:
            collection[pid]["_signals"]["upvoted"] = True
        else:
            post["_signals"] = {"saved": False, "upvoted": True, "commented": False}
            post["_comment_body"] = None
            collection[pid] = post

    # Merge comments (enrich existing posts or add new entries)
    for comment in comments:
        pid = comment["parent_post_id"]
        if pid in collection:
            collection[pid]["_signals"]["commented"] = True
            collection[pid]["_comment_body"] = comment["comment_body"]
        else:
            # Create a post entry from the comment metadata
            collection[pid] = {
                "id": pid,
                "title": comment["parent_post_title"],
                "selftext": "",
                "url": "",
                "subreddit": comment["parent_subreddit"],
                "author": "[from comment]",
                "created_utc": comment["comment_created"],
                "created_date": comment["comment_date"],
                "score": comment["parent_score"],
                "num_comments": 0,
                "permalink": "",
                "comments": [],
                "_signals": {"saved": False, "upvoted": False, "commented": True},
                "_comment_body": comment["comment_body"],
            }

    # Compute composite engagement score
    import math
    for pid, post in collection.items():
        signals = post["_signals"]
        score = post.get("score", 0)

        # Base score from post popularity
        base = min(math.log(max(score, 1) + 1) / math.log(1001), 1.0)

        # Engagement multiplier from user signals
        signal_boost = 0.0
        if signals["saved"]:
            signal_boost += 0.3    # Saved = deliberate interest
        if signals["upvoted"]:
            signal_boost += 0.2    # Upvoted = approval
        if signals["commented"]:
            signal_boost += 0.4    # Commented = deep engagement

        # Comment length bonus (longer comment = more invested)
        comment_body = post.get("_comment_body", "")
        if comment_body and len(comment_body) > 100:
            signal_boost += 0.1  # Wrote a substantial response

        post["_engagement_score"] = round(min(base * 0.4 + signal_boost, 1.0), 3)
        post["_signal_count"] = sum(signals.values())

    result = sorted(collection.values(), key=lambda p: p["_engagement_score"], reverse=True)
    return result


def run_collection(saved_only: bool = False, dry_run: bool = False):
    """Main collection pipeline."""
    # Load existing saved posts
    saved = []
    if SAVED_POSTS_PATH.exists():
        saved = json.loads(SAVED_POSTS_PATH.read_text(encoding="utf-8"))
        print(f"Loaded {len(saved)} saved posts from existing file")
    else:
        print("No saved_posts_raw.json found. Fetching from Reddit...")
        reddit = get_reddit_client()
        from praw.models import Submission
        for item in reddit.user.me().saved(limit=1000):
            if isinstance(item, Submission):
                saved.append({
                    "id": item.id,
                    "title": item.title,
                    "selftext": item.selftext or "",
                    "url": item.url,
                    "subreddit": str(item.subreddit),
                    "author": str(item.author) if item.author else "[deleted]",
                    "created_utc": item.created_utc,
                    "created_date": datetime.fromtimestamp(
                        item.created_utc, tz=timezone.utc
                    ).strftime("%Y-%m-%d"),
                    "score": item.score,
                    "num_comments": item.num_comments,
                    "permalink": f"https://reddit.com{item.permalink}",
                    "comments": [],
                })

    upvoted = []
    comments = []

    if not saved_only:
        try:
            reddit = get_reddit_client()
            upvoted = fetch_upvoted_posts(reddit, limit=500)
            comments = fetch_user_comments(reddit, limit=200)
        except Exception as e:
            print(f"WARNING: Reddit API error: {e}")
            print("Continuing with saved posts only.")

    # Merge
    collection = merge_collection(saved, upvoted, comments)

    # Stats
    signal_counts = {"saved_only": 0, "multi_signal": 0, "upvoted_only": 0, "commented_only": 0}
    for post in collection:
        sc = post["_signal_count"]
        if sc > 1:
            signal_counts["multi_signal"] += 1
        elif post["_signals"]["saved"]:
            signal_counts["saved_only"] += 1
        elif post["_signals"]["upvoted"]:
            signal_counts["upvoted_only"] += 1
        elif post["_signals"]["commented"]:
            signal_counts["commented_only"] += 1

    print(f"\nCollection Summary")
    print(f"  Total unique posts: {len(collection)}")
    print(f"  From saves: {len(saved)}")
    print(f"  From upvotes: {len(upvoted)}")
    print(f"  From comments: {len(comments)}")
    print(f"  Multi-signal (saved+upvoted or +commented): {signal_counts['multi_signal']}")
    print(f"\n  Top 10 by engagement:")
    for p in collection[:10]:
        signals = p["_signals"]
        flags = ("S" if signals["saved"] else ".") + ("U" if signals["upvoted"] else ".") + ("C" if signals["commented"] else ".")
        print(f"    [{p['_engagement_score']:.3f}] [{flags}] r/{p['subreddit']}: {p['title'][:60]}")

    if not dry_run:
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(json.dumps(collection, indent=2, default=str), encoding="utf-8")
        print(f"\nSaved to: {OUTPUT_PATH}")
    else:
        print("\n(dry run, nothing saved)")


def show_stats():
    """Show stats from last collection."""
    if not OUTPUT_PATH.exists():
        print("No collection found. Run collect_reddit.py first.")
        return

    collection = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    print(f"Collection: {len(collection)} posts")

    # Subreddit breakdown
    subs = {}
    for p in collection:
        sub = p.get("subreddit", "?")
        subs[sub] = subs.get(sub, 0) + 1

    print("\nSubreddit distribution:")
    for sub, count in sorted(subs.items(), key=lambda x: -x[1])[:20]:
        print(f"  r/{sub}: {count}")

    # Engagement distribution
    scores = [p.get("_engagement_score", 0) for p in collection]
    high = sum(1 for s in scores if s >= 0.6)
    mid = sum(1 for s in scores if 0.3 <= s < 0.6)
    low = sum(1 for s in scores if s < 0.3)
    print(f"\nEngagement: {high} high, {mid} medium, {low} low")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Expanded Reddit collection")
    parser.add_argument("--saved-only", action="store_true", help="Only use saved posts")
    parser.add_argument("--stats", action="store_true", help="Show collection stats")
    parser.add_argument("--dry-run", action="store_true", help="Preview without saving")
    args = parser.parse_args()

    if args.stats:
        show_stats()
    else:
        run_collection(saved_only=args.saved_only, dry_run=args.dry_run)
