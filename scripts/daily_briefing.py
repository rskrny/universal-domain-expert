#!/usr/bin/env python3
"""
Daily Briefing -- Jarvis-style morning intelligence digest.

Combines all data sources into a single briefing delivered to both
a local file and the Brain Feed Lark chat.

Sections:
  1. Deadline Alerts (from memory files)
  2. Project Status Snapshot (from project memory)
  3. Reddit Intelligence (from reddit_scanner)
  4. Lark Messages (from lark_digest logic)
  5. System Health (retrieval stats, routing log)
  6. Recommended Actions (synthesized priorities)

Usage:
    python scripts/daily_briefing.py               # Full briefing
    python scripts/daily_briefing.py --no-lark      # Local file only
    python scripts/daily_briefing.py --no-reddit    # Skip Reddit (faster)

Scheduled via Claude Code scheduled-tasks MCP:
    cron: "0 1 * * *"  (1 AM CST = 7 AM HST Hawaii)
"""

import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Bypass proxy (Clash Verge fix)
for k in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"]:
    os.environ.pop(k, None)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

# Constants
MEMORY_DIR = Path(os.getenv(
    "MEMORY_DIR",
    str(Path.home() / ".claude" / "projects"
        / "C--Users-rskrn-Desktop-universal-domain-expert---Copy" / "memory")
))
STATE_DIR = ROOT / "state"
BRIEFING_PATH = STATE_DIR / "daily_briefing.md"
ROUTING_LOG = STATE_DIR / "routing_log.jsonl"

# Hawaii timezone offset for display
HST_OFFSET = timedelta(hours=-10)


def now_hst() -> datetime:
    """Current time in Hawaii."""
    return datetime.now(timezone.utc) + HST_OFFSET


# ---------------------------------------------------------------------------
# Section 1: Deadline Alerts
# ---------------------------------------------------------------------------

def extract_deadlines() -> list:
    """Scan memory files for dates and flag upcoming deadlines."""
    deadlines = []
    today = datetime.now(timezone.utc).date()

    if not MEMORY_DIR.exists():
        return deadlines

    for md_file in MEMORY_DIR.glob("project_*.md"):
        text = md_file.read_text(encoding="utf-8", errors="replace")

        # Strip YAML frontmatter before scanning
        if text.startswith("---"):
            end = text.find("---", 3)
            if end > 0:
                text = text[end + 3:]

        # Find dates in various formats
        # ISO dates: 2026-04-08, 2026-06-15
        date_matches = re.findall(
            r"(\d{4}-\d{2}-\d{2})",
            text
        )
        # Named dates: Apr 7, April 8, Jun 15, June 15
        named_matches = re.findall(
            r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2})",
            text, re.IGNORECASE
        )

        project_name = md_file.stem.replace("project_", "").replace("_", " ").title()

        for date_str in date_matches:
            try:
                d = datetime.strptime(date_str, "%Y-%m-%d").date()
                days_away = (d - today).days
                if 0 <= days_away <= 30:
                    # Find context around the date (word-boundary safe)
                    idx = text.find(date_str)
                    start = max(0, idx - 100)
                    end = min(len(text), idx + len(date_str) + 100)
                    # Expand start to nearest word boundary
                    while start > 0 and text[start] not in (" ", "\n", "\t"):
                        start += 1
                    context_raw = text[start:end].strip()
                    # Remove the date itself since it displays separately
                    context_raw = context_raw.replace(date_str, "").strip()
                    context = " ".join(context_raw.split())[:150]

                    # Skip metadata dates (updated, generated, etc.)
                    skip_patterns = ["updated 20", "generated 20", "as of 20", "Updated 20"]
                    if any(sp in context_raw[max(0, idx - 20):idx + len(date_str)] for sp in skip_patterns):
                        continue

                    deadlines.append({
                        "date": date_str,
                        "days_away": days_away,
                        "project": project_name,
                        "context": context,
                    })
            except ValueError:
                continue

    # Deduplicate and sort by urgency
    seen = set()
    unique = []
    for d in sorted(deadlines, key=lambda x: x["days_away"]):
        key = (d["date"], d["project"])
        if key not in seen:
            seen.add(key)
            unique.append(d)

    return unique[:10]


# ---------------------------------------------------------------------------
# Section 2: Project Status
# ---------------------------------------------------------------------------

def get_project_status() -> str:
    """Read the all-projects map for a quick snapshot."""
    projects_file = MEMORY_DIR / "project_all_projects_map.md"
    if not projects_file.exists():
        return "Project map not found."

    text = projects_file.read_text(encoding="utf-8", errors="replace")

    # Extract the numbered list items
    lines = []
    for line in text.split("\n"):
        if re.match(r"^\d+\.\s", line.strip()):
            lines.append(line.strip())
        elif line.strip().startswith("- Tax") or line.strip().startswith("- Pepper"):
            lines.append(line.strip())

    return "\n".join(lines) if lines else "No project data found."


# ---------------------------------------------------------------------------
# Section 3: Reddit Intelligence
# ---------------------------------------------------------------------------

def get_reddit_digest(max_posts: int = 10) -> str:
    """Run the reddit scanner and return top posts."""
    try:
        sys.path.insert(0, str(ROOT))
        from dashboard.reddit_scanner import run_scan
        result = run_scan(verbose=False)
        posts = result.get("posts", [])[:max_posts]

        if not posts:
            return "No Reddit posts found (API may be unreachable)."

        lines = []
        for i, p in enumerate(posts, 1):
            # Quality score may be under different keys
            qs = p.get("quality", p.get("quality_score", p.get("final_score", 0)))
            if isinstance(qs, (int, float)) and qs > 0:
                score_bar = "#" * min(int(qs * 10), 10)
            else:
                score_bar = ""
            title = p.get("title", "")[:90]
            sub = p.get("subreddit", "?")
            upvotes = p.get("score", p.get("ups", 0))
            lines.append(f"{i}. [{score_bar}] r/{sub} ({upvotes} pts)")
            lines.append(f"   {title}")
            if p.get("url"):
                lines.append(f"   {p['url']}")
            lines.append("")

        return "\n".join(lines)
    except Exception as e:
        return f"Reddit scan failed: {e}"


# ---------------------------------------------------------------------------
# Section 4: Lark Messages
# ---------------------------------------------------------------------------

def get_lark_summary() -> str:
    """Pull recent Lark messages and show a simple summary."""
    try:
        from lark_reader import load_env as lark_load_env, get_opener, get_token, get_messages, format_message

        BRAINFEED_CHAT_ID = "oc_ab26f9abaea8f93912614f7e7284abd6"

        lark_load_env()
        opener = get_opener()
        token = get_token(opener, org_key="brainfeed")
        messages = get_messages(opener, token, BRAINFEED_CHAT_ID, count=10)

        if not messages:
            return "No recent Lark messages."

        lines = []
        for msg in messages:
            formatted = format_message(msg)
            if formatted and isinstance(formatted, str):
                # Take first 120 chars of each message
                lines.append(f"- {formatted[:120]}")

        if lines:
            return f"{len(lines)} recent messages:\n" + "\n".join(lines[:8])
        return "No recent Lark messages."
    except Exception as e:
        return f"Lark unavailable: {e}"


# ---------------------------------------------------------------------------
# Section 5: System Health
# ---------------------------------------------------------------------------

def get_system_health() -> str:
    """Check retrieval index and routing log health."""
    lines = []

    # Retrieval stats (use sqlite directly to avoid import complexity)
    try:
        import sqlite3
        db_path = ROOT / "retrieval" / "store" / "metadata.db"
        if db_path.exists():
            conn = sqlite3.connect(str(db_path))
            count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
            conn.close()
            lines.append(f"Knowledge index: {count:,} chunks")
        else:
            lines.append("Knowledge index: database not found")
    except Exception as e:
        lines.append(f"Knowledge index: unable to read ({e})")

    # Routing log
    if ROUTING_LOG.exists():
        try:
            entries = [json.loads(l) for l in ROUTING_LOG.read_text().strip().split("\n") if l.strip()]
            routed = sum(1 for e in entries if e.get("routed"))
            total = len(entries)
            lines.append(f"Routing log: {total} queries ({routed} routed)")
        except Exception:
            lines.append("Routing log: unable to read")
    else:
        lines.append("Routing log: empty (no queries yet)")

    # Reddit ingestion status
    ingested_path = STATE_DIR / "reddit_ingested.json"
    if ingested_path.exists():
        try:
            ingested = json.loads(ingested_path.read_text())
            lines.append(f"Reddit ingested: {len(ingested)} posts")
        except Exception:
            pass

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Section 6: Recommended Actions
# ---------------------------------------------------------------------------

def generate_recommendations(deadlines: list, project_status: str) -> str:
    """Synthesize priorities based on all gathered data."""
    actions = []

    # Deadline-based actions
    for d in deadlines[:3]:
        if d["days_away"] == 0:
            actions.append(f"TODAY: {d['project']} -- {d['context'][:80]}")
        elif d["days_away"] <= 3:
            actions.append(f"URGENT ({d['days_away']}d): {d['project']} -- {d['context'][:80]}")
        elif d["days_away"] <= 7:
            actions.append(f"This week ({d['days_away']}d): {d['project']} -- {d['context'][:60]}")

    # Static high-priority items (from known project state)
    if "tax" in project_status.lower() and "mail" in project_status.lower():
        actions.append("STANDING: Tax return needs printing, signing, and mailing by June 15")

    if not actions:
        actions.append("No urgent deadlines. Good day for deep work.")

    return "\n".join(f"  {i+1}. {a}" for i, a in enumerate(actions[:5]))


# ---------------------------------------------------------------------------
# Assemble Briefing
# ---------------------------------------------------------------------------

def build_briefing(skip_reddit: bool = False) -> str:
    """Build the complete daily briefing markdown."""
    now = now_hst()
    date_str = now.strftime("%A, %B %d, %Y")
    time_str = now.strftime("%I:%M %p HST")

    sections = []
    sections.append(f"# Daily Briefing -- {date_str}")
    sections.append(f"> Generated {time_str}\n")

    # Section 1: Deadlines
    print("  [1/6] Scanning deadlines...")
    deadlines = extract_deadlines()
    if deadlines:
        deadline_lines = []
        for d in deadlines:
            urgency = "!!" if d["days_away"] <= 3 else "!" if d["days_away"] <= 7 else ""
            deadline_lines.append(
                f"- {urgency} **{d['date']}** ({d['days_away']}d) -- {d['project']}: {d['context'][:80]}"
            )
        sections.append("## Deadline Alerts\n" + "\n".join(deadline_lines))
    else:
        sections.append("## Deadline Alerts\nNo deadlines within 30 days.")

    # Section 2: Projects
    print("  [2/6] Reading project status...")
    status = get_project_status()
    sections.append("## Project Status\n" + status)

    # Section 3: Reddit
    if skip_reddit:
        sections.append("## Reddit Intelligence\nSkipped (--no-reddit flag).")
    else:
        print("  [3/6] Scanning Reddit...")
        reddit = get_reddit_digest(max_posts=10)
        sections.append("## Reddit Intelligence\n" + reddit)

    # Section 4: Lark
    print("  [4/6] Checking Lark messages...")
    lark = get_lark_summary()
    sections.append("## Lark Messages\n" + lark)

    # Section 5: System
    print("  [5/6] Checking system health...")
    health = get_system_health()
    sections.append("## System Health\n" + health)

    # Section 6: Actions
    print("  [6/6] Generating recommendations...")
    recommendations = generate_recommendations(deadlines, status)
    sections.append("## Recommended Actions\n" + recommendations)

    return "\n\n---\n\n".join(sections)


# ---------------------------------------------------------------------------
# Delivery
# ---------------------------------------------------------------------------

def send_to_lark(briefing_text: str) -> bool:
    """Send briefing to Brain Feed Lark chat."""
    try:
        from send_to_lark import load_env as sl_load_env, get_opener, get_token, get_chat_id, send_message

        sl_load_env()
        opener = get_opener()
        token = get_token(opener)
        chat_id = get_chat_id()

        # Lark text messages have a ~4000 char limit. Truncate if needed.
        text = briefing_text
        if len(text) > 3800:
            text = text[:3800] + "\n\n[...truncated. Full briefing in state/daily_briefing.md]"

        content = json.dumps({"text": text})
        send_message(opener, token, chat_id, "text", content)
        return True
    except Exception as e:
        print(f"  Lark delivery failed: {e}")
        return False


def main():
    skip_reddit = "--no-reddit" in sys.argv
    skip_lark = "--no-lark" in sys.argv

    print(f"Daily Briefing -- {now_hst().strftime('%Y-%m-%d %I:%M %p HST')}")
    print("=" * 50)

    briefing = build_briefing(skip_reddit=skip_reddit)

    # Save locally
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    BRIEFING_PATH.write_text(briefing, encoding="utf-8")
    print(f"\nSaved to {BRIEFING_PATH}")

    # Send to Lark
    if not skip_lark:
        print("Sending to Lark...")
        if send_to_lark(briefing):
            print("Delivered to Brain Feed chat.")
        else:
            print("Lark delivery failed. Briefing saved locally only.")

    print("\nDone.")


if __name__ == "__main__":
    main()
