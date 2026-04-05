"""
Match Reddit posts against active project descriptions.

Two-tier matching:
  Tier 1 (always): Keyword overlap between post text and project keywords.
  Tier 2 (optional): Semantic similarity via sentence-transformers.

Only returns posts that are relevant to at least one project.
"""

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

# Bypass proxy before any network calls
for k in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"]:
    os.environ.pop(k, None)

# Stop words to exclude from keyword matching
STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "it", "this", "that", "are", "was",
    "be", "has", "had", "have", "do", "does", "did", "will", "can", "my",
    "i", "you", "we", "he", "she", "they", "not", "no", "so", "if", "up",
    "out", "about", "just", "how", "what", "when", "who", "all", "been",
    "more", "some", "like", "than", "into", "its", "your", "their", "our",
    "am", "as", "im", "ive", "dont", "get", "got", "one", "new", "use",
    "using", "used", "make", "made", "way", "would", "could", "should",
}

# Keywords per project. Two tiers:
# - "strong": Highly specific. A single match is meaningful.
# - "weak": Generic terms. Need 2+ weak matches or 1 weak + 1 strong.
PROJECT_KEYWORDS = {
    "the-flip-side": {
        "strong": {"podcast", "feishu", "brandpal", "lark", "tiktok"},
        "weak": {"media", "china", "episodes", "social", "editing", "content", "instagram", "youtube"},
    },
    "bloodline": {
        "strong": {"supabase", "charter", "booking", "fishing", "railway"},
        "weak": {"next.js", "nextjs", "react", "seo", "website"},
    },
    "shopmyroom-vids": {
        "strong": {"ffmpeg", "short-form", "reels", "shorts", "shopmyroom", "fal.ai"},
        "weak": {"video", "pipeline", "rendering", "ar", "furniture", "e-commerce", "product"},
    },
    "goldie-group": {
        "strong": {"email-triage", "triage", "classification", "gmail", "outlook"},
        "weak": {"email", "nlp", "enterprise", "workflow"},
    },
    "ai-beginner-course": {
        "strong": {"course", "curriculum", "teaching", "education", "beginner"},
        "weak": {"tutorial", "learning", "prompt"},
    },
    "smr-aws": {
        "strong": {"aws", "ec2", "lambda", "inference", "gpu"},
        "weak": {"cloud", "compute", "cost", "pricing", "hardware", "deployment"},
    },
    "habitat-homeostasis": {
        "strong": {"climate", "sustainability", "epw", "carbon", "homeostasis"},
        "weak": {"energy", "weather", "green"},
    },
    "pepper-coo": {
        "strong": {"telegram", "arcade", "claw", "openclaw"},
        "weak": {"bot", "vps", "hosting", "oauth"},
    },
    "ges-hub": {
        "strong": {"consulting", "outreach", "b2b", "proposal"},
        "weak": {"strategy", "pricing", "linkedin", "saas", "agency"},
    },
    "tax-finance": {
        "strong": {"irs", "tax", "filing", "wfoe", "5471"},
        "weak": {"crypto", "llc"},
    },
}

# Human-readable project names for display
PROJECT_NAMES = {
    "the-flip-side": "The Flip Side",
    "bloodline": "Bloodline Charters",
    "shopmyroom-vids": "AutomateShortVids SMR",
    "goldie-group": "Goldie Group",
    "ai-beginner-course": "AI Beginner Course",
    "smr-aws": "SMR Compute",
    "habitat-homeostasis": "Habitat Homeostasis",
    "pepper-coo": "Pepper OpenClaw",
    "ges-hub": "GES Hub",
    "tax-finance": "Tax/Finance",
}

# General interest keywords that indicate broadly useful content
# (applies to the domain expert system itself and Ryan's work style)
GENERAL_KEYWORDS = {
    "agent", "agents", "multi-agent", "rag", "retrieval", "embedding",
    "claude", "anthropic", "llm", "gpt", "openai", "local", "self-hosted",
    "automation", "pipeline", "workflow", "api", "mcp", "tool-use",
    "cloudflare", "workers", "d1", "r2", "next.js", "nextjs", "react",
    "python", "typescript", "fastapi", "supabase", "railway",
    "startup", "indie", "founder", "solo", "saas", "revenue",
    "prompt", "engineering", "fine-tune", "lora",
}


def _tokenize(text):
    """Extract lowercase word tokens, removing stop words."""
    words = set(re.findall(r"[a-z][a-z0-9.+-]+", text.lower()))
    return words - STOP_WORDS


def _get_project_descriptions():
    """Load project descriptions from the registry."""
    try:
        from dashboard.projects_registry import PROJECT_REGISTRY
        return {
            key: proj["description"]
            for key, proj in PROJECT_REGISTRY.items()
        }
    except ImportError:
        return {}


def match_post_to_projects(post, project_keywords=None):
    """
    Match a single Reddit post against all projects using two-tier keywords.

    Strong keywords: a single match is meaningful.
    Weak keywords: need 2+ weak matches or 1 weak + context from strong.

    Returns list of (project_key, relevance_score, matched_keywords) tuples,
    sorted by relevance descending. Empty list if no match.
    """
    if project_keywords is None:
        project_keywords = PROJECT_KEYWORDS

    title = post.get("title", "")
    preview = post.get("selftext_preview", "")
    post_text = f"{title} {preview}"
    post_tokens = _tokenize(post_text)

    matches = []
    for proj_key, tiers in project_keywords.items():
        strong = tiers.get("strong", set())
        weak = tiers.get("weak", set())

        strong_hits = post_tokens & strong
        weak_hits = post_tokens & weak
        all_hits = strong_hits | weak_hits

        if not all_hits:
            continue

        # Scoring rules:
        # - 1+ strong hit = valid match
        # - 2+ weak hits with 0 strong = valid match
        # - 1 weak hit alone = skip (too generic)
        if not strong_hits and len(weak_hits) < 2:
            continue

        # Score: strong hits worth 3x, weak hits worth 1x
        raw = len(strong_hits) * 3 + len(weak_hits)
        total_possible = len(strong) * 3 + len(weak)
        score = raw / max(total_possible, 1)

        # Boost multi-signal matches
        if len(all_hits) >= 4:
            score *= 1.5
        elif len(all_hits) >= 3:
            score *= 1.3

        score = min(1.0, score)

        if score >= 0.05:
            matches.append((proj_key, score, all_hits))

    # General interest keywords: only if no project-specific match
    if not matches:
        general_overlap = post_tokens & GENERAL_KEYWORDS
        if len(general_overlap) >= 3:  # need 3+ general keywords to qualify
            score = len(general_overlap) / len(GENERAL_KEYWORDS)
            matches.append(("general", score, general_overlap))

    matches.sort(key=lambda x: x[1], reverse=True)
    return matches


def _build_match_reason(matched_keywords, project_key):
    """Generate a human-readable match reason from keyword overlap."""
    name = PROJECT_NAMES.get(project_key, project_key)
    kw_list = sorted(matched_keywords, key=len, reverse=True)[:3]
    kw_str = ", ".join(kw_list)
    return f"{kw_str} relevant to {name}"


def match(skip_scan=False, cached_posts=None):
    """
    Run the full Reddit matching pipeline.

    Args:
        skip_scan: If True, skip Reddit API call (use cached posts)
        cached_posts: Pre-fetched posts to match against

    Returns:
        List of matched post dicts with project relevance info,
        sorted by combined_score descending.
    """
    # Get Reddit posts
    posts = cached_posts
    if posts is None and not skip_scan:
        try:
            from dashboard.reddit_scanner import run_scan
            result = run_scan(verbose=False)
            posts = result.get("posts", [])
        except Exception as e:
            print(f"  Reddit scan failed: {e}")
            return []

    if not posts:
        return []

    # Match each post against projects
    matched = []
    for post in posts:
        project_matches = match_post_to_projects(post)
        if not project_matches:
            continue

        best_proj, best_score, best_keywords = project_matches[0]

        matched.append({
            "title": post.get("title", ""),
            "url": post.get("url", ""),
            "subreddit": post.get("subreddit", ""),
            "score": post.get("score", 0),
            "quality": post.get("quality", 0.0),
            "relevance": best_score,
            "matched_project": PROJECT_NAMES.get(best_proj, best_proj),
            "matched_project_key": best_proj,
            "match_reason": _build_match_reason(best_keywords, best_proj),
            "matched_keywords": list(best_keywords),
            "combined_score": round(best_score * 0.6 + post.get("quality", 0) * 0.4, 4),
            "id": post.get("url", ""),
        })

    # Sort by combined score
    matched.sort(key=lambda x: x["combined_score"], reverse=True)

    # Cap at 8 matches
    return matched[:8]
