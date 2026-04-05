"""
Intelligence Briefing Orchestrator.

Replaces the legacy daily_briefing.py with focused, useful output:
- Deadline scanning (14-day window, urgency-categorized)
- Reddit posts matched semantically against active projects
- Clean Lark interactive card delivery to Brain Feed only
- State tracking for future delta computation

Usage:
    python -m scripts.intelligence.briefing              # Full run
    python -m scripts.intelligence.briefing --no-lark    # Local only
    python -m scripts.intelligence.briefing --no-reddit  # Skip Reddit
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Bypass proxy before any network calls
for k in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"]:
    os.environ.pop(k, None)

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from scripts.intelligence import deadline_scanner, reddit_matcher, lark_cards, state_tracker

# Constants
STATE_DIR = ROOT / "state"
BRIEFING_PATH = STATE_DIR / "daily_briefing.md"
ROUTING_LOG = STATE_DIR / "routing_log.jsonl"
HST = timedelta(hours=-10)


def _now_hst():
    return datetime.now(timezone.utc) + HST


def _get_system_stats():
    """Lightweight system health check."""
    stats = {}

    # Knowledge index chunk count
    try:
        import sqlite3
        db_path = ROOT / "retrieval" / "store" / "metadata.db"
        if db_path.exists():
            conn = sqlite3.connect(str(db_path))
            stats["chunks"] = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
            conn.close()
    except Exception:
        pass

    # Routing log count
    if ROUTING_LOG.exists():
        try:
            lines = [l for l in ROUTING_LOG.read_text().strip().split("\n") if l.strip()]
            entries = [json.loads(l) for l in lines]
            stats["queries"] = len(entries)
            stats["routed"] = sum(1 for e in entries if e.get("routed"))
        except Exception:
            pass

    return stats


def _save_local_briefing(deadlines, matches, stats):
    """Save a clean markdown copy of the briefing locally."""
    now = _now_hst()

    lines = [
        f"# Intelligence Briefing | {now.strftime('%A, %B %d, %Y')}",
        f"> Generated {now.strftime('%I:%M %p HST')}",
        "",
    ]

    # Deadlines
    if deadlines:
        lines.append("## Action Required")
        for dl in deadlines:
            lines.append(f"- **{dl['urgency']}** {dl['project']}: {dl['context']} ({dl['date']}, {dl['days_away']}d)")
        lines.append("")
    else:
        lines.append("## Action Required")
        lines.append("No deadlines within 14 days.")
        lines.append("")

    # Reddit matches with recommendations
    if matches:
        lines.append("## Discoveries")
        for m in matches:
            rec = m.get("recommendation", "Note")
            rec_reason = m.get("rec_reason", "")
            lines.append(f"- **{rec}**: [{m['title'][:80]}]({m['url']})")
            lines.append(f"  -> {m['matched_project']}: {m['match_reason']}")
            if rec_reason:
                lines.append(f"  Action: {rec_reason}")
        lines.append("")
    else:
        lines.append("## Discoveries")
        lines.append("No Reddit posts matched active projects today.")
        lines.append("")

    # System pulse
    if stats:
        lines.append("## System Pulse")
        parts = []
        if stats.get("chunks"):
            parts.append(f"Knowledge: {stats['chunks']:,} chunks")
        if stats.get("queries"):
            parts.append(f"Routing: {stats['queries']} queries ({stats.get('routed', 0)} routed)")
        lines.append(" | ".join(parts))
        lines.append("")

    briefing_text = "\n".join(lines)

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    BRIEFING_PATH.write_text(briefing_text, encoding="utf-8")
    return briefing_text


def _deliver_card(card):
    """Send card to Brain Feed Lark chat via direct API."""
    try:
        from send_to_lark import load_env, get_opener, get_token, get_chat_id, send_message

        load_env()
        opener = get_opener()
        token = get_token(opener)
        chat_id = get_chat_id()

        card_json = json.dumps(card)
        send_message(opener, token, chat_id, "interactive", card_json)
        return True
    except Exception as e:
        print(f"  Lark delivery failed: {e}")
        return False


def run(skip_reddit=False, skip_lark=False):
    """Run the full intelligence briefing pipeline."""
    now = _now_hst()
    print(f"Intelligence Briefing | {now.strftime('%Y-%m-%d %I:%M %p HST')}")
    print("=" * 50)

    # 1. Scan deadlines
    print("  [1/5] Scanning deadlines...")
    deadlines = deadline_scanner.scan()
    if deadlines:
        print(f"        {len(deadlines)} deadline(s) found")
    else:
        print("        No deadlines within 14 days")

    # 2. Match Reddit posts to projects
    matches = []
    if not skip_reddit:
        print("  [2/5] Scanning Reddit + matching to projects...")
        matches = reddit_matcher.match()
        if matches:
            print(f"        {len(matches)} post(s) matched to projects")
        else:
            print("        No project-relevant posts found")
    else:
        print("  [2/5] Reddit skipped (--no-reddit)")

    # 3. System stats
    print("  [3/5] Checking system health...")
    stats = _get_system_stats()

    # 4. Compute deltas and build
    print("  [4/5] Computing deltas...")
    deltas = state_tracker.compute_deltas(deadlines, matches, stats)
    if deltas.get("is_first_run"):
        print("        First run, no previous state to compare")
    else:
        new_r = len(deltas.get("new_reddit", []))
        ret_r = len(deltas.get("returning_reddit", []))
        new_d = len(deltas.get("new_deadlines", []))
        print(f"        {new_r} new posts, {ret_r} returning, {new_d} new deadlines")

    print("  [5/5] Building briefing...")

    # Build card with delta awareness
    card = lark_cards.build_morning_intel(deadlines, matches, stats, deltas=deltas)

    # Save state AFTER building (so next run compares against this one)
    state_tracker.save(deadlines, matches, stats)

    # Save local markdown
    briefing_text = _save_local_briefing(deadlines, matches, stats)
    print(f"\nSaved to {BRIEFING_PATH}")

    # Deliver to Lark
    if not skip_lark:
        print("Sending card to Brain Feed...")
        if _deliver_card(card):
            print("Delivered to Brain Feed chat.")
        else:
            print("Lark delivery failed. Briefing saved locally only.")
    else:
        print("Lark delivery skipped (--no-lark)")

    print("\nDone.")
    return card


def main():
    skip_reddit = "--no-reddit" in sys.argv
    skip_lark = "--no-lark" in sys.argv
    run(skip_reddit=skip_reddit, skip_lark=skip_lark)


if __name__ == "__main__":
    main()
