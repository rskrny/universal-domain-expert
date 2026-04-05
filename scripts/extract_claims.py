"""
Claim Extraction Layer for Reddit Knowledge Ingestion.

Takes raw Reddit posts and uses Claude API to extract structured claims:
  - Core insight(s): what's the actual takeaway?
  - Evidence quality: anecdote vs data vs replicated?
  - Novelty: does this extend, contradict, or duplicate existing domain knowledge?
  - Engagement signal: computed from score + comments + user save

Usage:
    python scripts/extract_claims.py                    # Extract from all unprocessed posts
    python scripts/extract_claims.py --dry-run          # Show what would be extracted
    python scripts/extract_claims.py --post-id abc123   # Extract from a single post
    python scripts/extract_claims.py --reprocess        # Re-extract all (ignores tracking)
"""

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env", override=True)

# Fix Windows console encoding
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


# ── Engagement Score ────────────────────────────────────────────────────────

def compute_engagement_score(post: dict) -> float:
    """
    Compute a 0-1 engagement score from Reddit signals.

    Weights:
      - Post score (log-scaled, capped at 1000)
      - Number of comments (log-scaled)
      - Comment quality (avg score of top comments)
      - User saved it (implicit 1.0 baseline since all posts are saves)
    """
    import math

    score = post.get("score", 0)
    num_comments = post.get("num_comments", 0)
    comments = post.get("comments", [])

    # Log-scale the post score. 1000+ is very high engagement.
    score_signal = min(math.log(max(score, 1) + 1) / math.log(1001), 1.0)

    # Log-scale comment count. 100+ comments is very active.
    comment_signal = min(math.log(max(num_comments, 1) + 1) / math.log(101), 1.0)

    # Average quality of stored comments
    if comments:
        avg_comment_score = sum(c.get("score", 0) for c in comments) / len(comments)
        comment_quality = min(math.log(max(avg_comment_score, 1) + 1) / math.log(101), 1.0)
    else:
        comment_quality = 0.0

    # Weighted combination. User saved it, so baseline is already high.
    engagement = (
        0.35 * score_signal +
        0.25 * comment_signal +
        0.20 * comment_quality +
        0.20 * 1.0  # saved = strong intent signal
    )

    return round(engagement, 3)


# ── Evidence Classification ─────────────────────────────────────────────────

EVIDENCE_TYPES = {
    "anecdote": "Personal experience or single case. Low generalizability.",
    "crowd_consensus": "Many practitioners agree (high upvotes/comments). Medium confidence.",
    "data": "Includes numbers, benchmarks, or measurements. Higher confidence.",
    "replicated": "References studies, papers, or independently verified results. Highest.",
    "opinion": "Personal opinion without evidence. Lowest confidence.",
    "tutorial": "Step-by-step how-to. Confidence depends on author credibility.",
}


# ── Claude API Extraction ───────────────────────────────────────────────────

EXTRACTION_PROMPT = """You are a knowledge extraction specialist. Given a Reddit post and its top comments, extract the core claims and insights.

POST TITLE: {title}
SUBREDDIT: r/{subreddit}
SCORE: {score} | COMMENTS: {num_comments}
DATE: {date}

POST BODY:
{body}

TOP COMMENTS:
{comments_text}

---

Extract the following as valid JSON (no markdown fences, just raw JSON):

{{
  "claims": [
    {{
      "claim": "One sentence stating the core insight or takeaway",
      "evidence_type": "anecdote|crowd_consensus|data|replicated|opinion|tutorial",
      "confidence": 0.0-1.0,
      "details": "2-3 sentences expanding on the claim with specifics from the post"
    }}
  ],
  "domain_tags": ["primary-domain", "secondary-domain"],
  "practical_value": "high|medium|low",
  "novelty_assessment": "One sentence: is this common knowledge, emerging practice, or cutting-edge?",
  "key_numbers": ["any specific metrics, benchmarks, or data points mentioned"],
  "counterarguments": ["notable disagreements or caveats from comments"]
}}

Rules:
- Extract 1-3 claims maximum. Quality over quantity.
- A claim must be specific and actionable. "AI is useful" is not a claim. "Using structured output with Claude reduces token usage by 40% compared to free-form" is a claim.
- If the post is mostly opinion with no substance, return practical_value: "low" and a single claim.
- If comments contradict the post, capture that in counterarguments.
- domain_tags MUST use ONLY names from this list (pick 1-2 that fit best):
  accounting-tax, ai-machine-learning, architecture-design, blockchain-web3, branding,
  business-consulting, business-law, career-development, civil-engineering, cloud-infrastructure,
  context-engineering, course-creation, creative-writing, criminal-law, crisis-management,
  customer-success, cybersecurity, data-analytics, data-engineering, devops-sre,
  document-production, ecommerce, economics, education, education-pedagogy,
  electrical-engineering, employment-law, energy-systems, environmental-science, event-planning,
  feishu-lark, frontend-development, game-development, graphic-design, gtm-strategy,
  history, hr-talent, insurance, intellectual-property, international-trade, journalism,
  linguistics, marketing-content, mathematics, mechanical-engineering, medicine-health,
  mental-health, mobile-development, music-production, negotiation, neuroscience, nonprofit,
  nutrition-fitness, operations-automation, personal-finance, philosophy, photography,
  podcasting, political-science, product-design, productivity, project-management,
  psychology-persuasion, public-speaking, quantum-computing, real-estate, research-authoring,
  robotics, saas-building, sales, social-distribution, social-media, software-dev,
  statistics, supply-chain, venture-capital, vibecoding, video-production
- Do NOT invent domain names outside this list. If nothing fits, use the closest match.
- confidence reflects how much you'd trust this claim in a professional context."""


def extract_claims_from_post(post: dict, api_key: str) -> dict:
    """
    Call Claude API to extract structured claims from a Reddit post.

    Returns the parsed JSON structure or an error dict.
    """
    import anthropic

    title = post.get("title", "Untitled")
    subreddit = post.get("subreddit", "unknown")
    score = post.get("score", 0)
    num_comments = post.get("num_comments", 0)
    date = post.get("created_date", "unknown")
    body = post.get("selftext", "")[:4000]  # Cap body length
    comments = post.get("comments", [])

    # Format comments
    comments_text = ""
    if comments:
        for c in comments[:5]:
            author = c.get("author", "anon")
            cscore = c.get("score", 0)
            cbody = c.get("body", "")[:600]
            comments_text += f"u/{author} ({cscore} pts): {cbody}\n\n"
    else:
        comments_text = "(no comments available)"

    # Skip posts with almost no content
    if len(body) < 50 and not comments:
        return {
            "claims": [],
            "domain_tags": ["general"],
            "practical_value": "low",
            "novelty_assessment": "Insufficient content to assess.",
            "key_numbers": [],
            "counterarguments": [],
            "_skipped": True,
            "_reason": "Too short, no comments",
        }

    prompt = EXTRACTION_PROMPT.format(
        title=title,
        subreddit=subreddit,
        score=score,
        num_comments=num_comments,
        date=date,
        body=body if body else "(link post, no body text)",
        comments_text=comments_text,
    )

    client = anthropic.Anthropic(api_key=api_key)

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = response.content[0].text.strip()

        # Try to parse JSON (handle markdown fences if model adds them)
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        result = json.loads(raw)
        result["_extracted"] = True
        result["_model"] = "claude-haiku-4-5-20251001"
        result["_tokens_used"] = response.usage.input_tokens + response.usage.output_tokens
        return result

    except json.JSONDecodeError as e:
        return {
            "claims": [],
            "_extracted": False,
            "_error": f"JSON parse error: {e}",
            "_raw_response": raw[:500] if 'raw' in dir() else "",
        }
    except Exception as e:
        return {
            "claims": [],
            "_extracted": False,
            "_error": str(e),
        }


# ── Batch Processing ────────────────────────────────────────────────────────

def load_posts() -> list:
    """Load saved posts from the Reddit API output."""
    reddit_path = Path("C:/Users/rskrn/Desktop/reddit api/saved_posts_raw.json")
    if not reddit_path.exists():
        print("No saved_posts_raw.json found. Run the Reddit collector first.")
        return []
    return json.loads(reddit_path.read_text(encoding="utf-8"))


def load_extraction_state() -> dict:
    """Load tracking of which posts have been extracted."""
    state_path = ROOT / "state" / "reddit_extractions.json"
    if state_path.exists():
        return json.loads(state_path.read_text(encoding="utf-8"))
    return {}


def save_extraction_state(state: dict):
    """Persist extraction tracking."""
    state_path = ROOT / "state" / "reddit_extractions.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def save_extracted_chunk(post: dict, extraction: dict, engagement: float):
    """
    Write an enriched markdown chunk that includes both raw content and
    structured claims. This replaces the old raw-dump approach.
    """
    post_id = post.get("id", "unknown")
    title = post.get("title", "Untitled")
    subreddit = post.get("subreddit", "unknown")
    score = post.get("score", 0)
    date = post.get("created_date", "")
    permalink = post.get("permalink", "")
    selftext = post.get("selftext", "")

    # Determine output domain from extraction
    domain_tags = extraction.get("domain_tags", ["general"])
    primary_domain = domain_tags[0] if domain_tags else "general"

    # Map common variations
    domain_map = {
        "ai": "ai-machine-learning",
        "ml": "ai-machine-learning",
        "machine-learning": "ai-machine-learning",
        "software": "software-dev",
        "coding": "software-dev",
        "programming": "software-dev",
        "rag": "context-engineering",
        "retrieval": "context-engineering",
        "web3": "blockchain-web3",
        "crypto": "blockchain-web3",
        "security": "cybersecurity",
        "frontend": "frontend-development",
        "react": "frontend-development",
        "saas": "saas-building",
        "devops": "devops-sre",
        "cloud": "cloud-infrastructure",
    }
    primary_domain = domain_map.get(primary_domain, primary_domain)

    out_dir = ROOT / "prompts" / "context" / "by-domain" / primary_domain
    if primary_domain == "general":
        out_dir = ROOT / "prompts" / "context" / "shared" / "reddit"
    out_dir.mkdir(parents=True, exist_ok=True)

    import re
    safe_title = re.sub(r'[^\w\s-]', '', title)[:50].strip().replace(' ', '-').lower()
    safe_title = re.sub(r'-+', '-', safe_title)
    filename = f"reddit-{post_id}-{safe_title}.md"
    filepath = out_dir / filename

    # Build enriched markdown
    lines = [
        f"# {title}",
        "",
        f"Source: {permalink}",
        f"Subreddit: r/{subreddit} | Score: {score} | Date: {date}",
        f"Engagement: {engagement} | Practical Value: {extraction.get('practical_value', 'unknown')}",
        "",
    ]

    # Structured claims section (the high-value part)
    claims = extraction.get("claims", [])
    if claims:
        lines.append("## Extracted Claims")
        lines.append("")
        for i, claim in enumerate(claims, 1):
            lines.append(f"**Claim {i}:** {claim.get('claim', '')}")
            lines.append(f"- Evidence: {claim.get('evidence_type', 'unknown')} (confidence: {claim.get('confidence', 0)})")
            lines.append(f"- Details: {claim.get('details', '')}")
            lines.append("")

    # Key numbers
    key_numbers = extraction.get("key_numbers", [])
    if key_numbers:
        lines.append("## Key Data Points")
        for n in key_numbers:
            lines.append(f"- {n}")
        lines.append("")

    # Novelty
    novelty = extraction.get("novelty_assessment", "")
    if novelty:
        lines.append(f"**Novelty:** {novelty}")
        lines.append("")

    # Counterarguments
    counters = extraction.get("counterarguments", [])
    if counters:
        lines.append("## Counterarguments")
        for c in counters:
            lines.append(f"- {c}")
        lines.append("")

    # Original content (truncated)
    lines.append("---")
    lines.append("")
    if selftext:
        content = selftext[:2000]
        if len(selftext) > 2000:
            content += "\n\n[Truncated]"
        lines.append(content)

    # Top comments
    comments = post.get("comments", [])
    if comments:
        lines.append("")
        lines.append("## Top Comments")
        lines.append("")
        for c in comments[:3]:
            body = c.get("body", "")[:400]
            author = c.get("author", "anon")
            cscore = c.get("score", 0)
            lines.append(f"**u/{author}** ({cscore} pts):")
            lines.append(f"> {body}")
            lines.append("")

    filepath.write_text("\n".join(lines), encoding="utf-8")
    return filepath, primary_domain


def run_extraction(dry_run: bool = False, post_id: str = None, reprocess: bool = False):
    """
    Main extraction loop. Process unextracted posts through Claude API.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set in .env")
        return

    posts = load_posts()
    if not posts:
        return

    state = load_extraction_state() if not reprocess else {}

    # Filter to target posts
    if post_id:
        posts = [p for p in posts if p.get("id") == post_id]
        if not posts:
            print(f"Post {post_id} not found in saved posts.")
            return

    # Skip already extracted
    if not reprocess:
        posts = [p for p in posts if p.get("id") not in state]

    # Apply subreddit filter (skip noise subs)
    try:
        from scripts.subreddit_config import is_allowed, is_denied
        before = len(posts)
        posts = [p for p in posts if not is_denied(p.get("subreddit", ""))
                 and (is_allowed(p.get("subreddit", "")) or post_id)]
        filtered = before - len(posts)
        if filtered > 0:
            print(f"Subreddit filter: {filtered} posts from noise subs removed")
    except ImportError:
        pass  # No filter config, process everything

    # Sort by engagement (highest first)
    for p in posts:
        p["_engagement"] = compute_engagement_score(p)
    posts.sort(key=lambda p: p["_engagement"], reverse=True)

    print(f"Posts to extract: {len(posts)}")
    if dry_run:
        for p in posts[:20]:
            eng = p["_engagement"]
            print(f"  [{eng:.3f}] r/{p['subreddit']}: {p['title'][:70]}")
        if len(posts) > 20:
            print(f"  ... and {len(posts) - 20} more")
        return

    stats = {"extracted": 0, "skipped": 0, "errors": 0, "domains": {}}
    total_tokens = 0

    for i, post in enumerate(posts):
        pid = post.get("id", "unknown")
        title = post.get("title", "Untitled")[:60]
        engagement = post["_engagement"]

        # Skip very low engagement unless explicitly requested
        if engagement < 0.15 and not post_id:
            stats["skipped"] += 1
            state[pid] = {"status": "skipped", "reason": "low_engagement", "engagement": engagement}
            continue

        print(f"  [{i+1}/{len(posts)}] Extracting: {title}...")

        extraction = extract_claims_from_post(post, api_key)

        if extraction.get("_skipped"):
            stats["skipped"] += 1
            state[pid] = {"status": "skipped", "reason": extraction.get("_reason", "unknown")}
            continue

        if not extraction.get("_extracted", False):
            stats["errors"] += 1
            state[pid] = {"status": "error", "error": extraction.get("_error", "")}
            print(f"    ERROR: {extraction.get('_error', 'unknown')}")
            continue

        total_tokens += extraction.get("_tokens_used", 0)

        # Save enriched chunk
        filepath, domain = save_extracted_chunk(post, extraction, engagement)
        stats["extracted"] += 1
        stats["domains"][domain] = stats["domains"].get(domain, 0) + 1

        # Track
        state[pid] = {
            "status": "extracted",
            "domain": domain,
            "engagement": engagement,
            "claims_count": len(extraction.get("claims", [])),
            "practical_value": extraction.get("practical_value", "unknown"),
            "extracted_at": time.strftime("%Y-%m-%d %H:%M"),
        }

        # Save state periodically
        if (i + 1) % 10 == 0:
            save_extraction_state(state)
            print(f"    Checkpoint: {stats['extracted']} extracted, {total_tokens} tokens used")

        # Small delay to respect API rate limits
        time.sleep(0.3)

    save_extraction_state(state)

    print(f"\nExtraction Complete")
    print(f"  Extracted: {stats['extracted']}")
    print(f"  Skipped: {stats['skipped']}")
    print(f"  Errors: {stats['errors']}")
    print(f"  Total tokens: {total_tokens:,}")
    if stats["domains"]:
        print(f"  By domain:")
        for d, count in sorted(stats["domains"].items(), key=lambda x: -x[1]):
            print(f"    {d}: {count}")


# ── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Extract claims from Reddit posts")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be extracted")
    parser.add_argument("--post-id", type=str, help="Extract from a single post")
    parser.add_argument("--reprocess", action="store_true", help="Re-extract all posts")
    args = parser.parse_args()

    run_extraction(dry_run=args.dry_run, post_id=args.post_id, reprocess=args.reprocess)
