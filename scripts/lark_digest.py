"""
Generate a Lark message digest for Claude's situational awareness.

Reads recent messages from the Brain Feed chat, extracts key information,
and saves a structured digest to state/lark_digest.md.

Usage:
    python scripts/lark_digest.py                   -- default: last 30 messages
    python scripts/lark_digest.py --count 50         -- last 50 messages
    python scripts/lark_digest.py --hours 4          -- messages from last 4 hours

The digest file is designed to be read at session start for context.
"""

import json
import os
import sys
from datetime import datetime, timedelta

# Bypass proxy (Clash Verge fix)
for k in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"]:
    os.environ.pop(k, None)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Import from sibling module
sys.path.insert(0, os.path.join(BASE_DIR, "scripts"))
from lark_reader import (
    load_env,
    get_opener,
    get_token,
    get_messages,
    format_message,
)

BRAINFEED_CHAT_ID = "oc_ab26f9abaea8f93912614f7e7284abd6"
DIGEST_PATH = os.path.join(BASE_DIR, "state", "lark_digest.md")


def classify_message(formatted_msg):
    """Classify a message into categories for the digest."""
    content = formatted_msg["content"].lower()
    categories = []

    # Action items
    action_keywords = [
        "todo", "action item", "need to", "please", "can you",
        "should", "must", "deadline", "asap", "urgent", "follow up",
        "complete", "finish", "submit", "send", "review", "approve",
    ]
    if any(kw in content for kw in action_keywords):
        categories.append("action")

    # Decisions
    decision_keywords = [
        "decided", "decision", "agreed", "confirmed", "approved",
        "go with", "we'll use", "final", "settled", "chose", "picked",
        "selected", "moving forward with",
    ]
    if any(kw in content for kw in decision_keywords):
        categories.append("decision")

    # Updates / status
    update_keywords = [
        "update", "status", "progress", "shipped", "deployed",
        "launched", "released", "merged", "completed", "done",
        "fixed", "resolved", "live", "ready",
    ]
    if any(kw in content for kw in update_keywords):
        categories.append("update")

    # Questions
    if "?" in formatted_msg["content"]:
        categories.append("question")

    # Files and links shared
    if formatted_msg["type"] in ("file", "image", "media"):
        categories.append("shared_file")
    if "http" in content or "https" in content:
        categories.append("link")

    if not categories:
        categories.append("general")

    return categories


def build_digest(messages, hours_filter=None):
    """Build a structured digest from messages."""
    formatted = [format_message(m) for m in messages]
    formatted.reverse()  # chronological order

    # Filter by time if requested
    if hours_filter:
        cutoff = datetime.now() - timedelta(hours=hours_filter)
        cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")
        formatted = [m for m in formatted if m["time"] >= cutoff_str]

    if not formatted:
        return None

    # Classify each message
    classified = []
    for msg in formatted:
        cats = classify_message(msg)
        classified.append({**msg, "categories": cats})

    # Group by category
    actions = [m for m in classified if "action" in m["categories"]]
    decisions = [m for m in classified if "decision" in m["categories"]]
    updates = [m for m in classified if "update" in m["categories"]]
    questions = [m for m in classified if "question" in m["categories"]]

    # Build markdown
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    oldest = formatted[0]["time"] if formatted else "N/A"
    newest = formatted[-1]["time"] if formatted else "N/A"

    lines = [
        "# Lark Message Digest",
        "",
        f"> Generated: {now}",
        f"> Chat: Brain Feed ({BRAINFEED_CHAT_ID})",
        f"> Period: {oldest} to {newest}",
        f"> Messages scanned: {len(formatted)}",
        "",
        "---",
        "",
    ]

    if actions:
        lines.append("## Action Items")
        lines.append("")
        for m in actions:
            lines.append(f"- **[{m['time']}]** {m['sender']}: {m['content']}")
        lines.append("")

    if decisions:
        lines.append("## Decisions")
        lines.append("")
        for m in decisions:
            lines.append(f"- **[{m['time']}]** {m['sender']}: {m['content']}")
        lines.append("")

    if updates:
        lines.append("## Updates & Status")
        lines.append("")
        for m in updates:
            lines.append(f"- **[{m['time']}]** {m['sender']}: {m['content']}")
        lines.append("")

    if questions:
        lines.append("## Open Questions")
        lines.append("")
        for m in questions:
            lines.append(f"- **[{m['time']}]** {m['sender']}: {m['content']}")
        lines.append("")

    lines.append("## Full Message Log")
    lines.append("")
    lines.append("```")
    for m in formatted:
        content_oneline = m["content"].replace("\n", " | ")
        lines.append(f"[{m['time']}] {m['sender']} ({m['type']}): {content_oneline}")
    lines.append("```")
    lines.append("")

    return "\n".join(lines)


def main():
    load_env()

    count = 30
    hours_filter = None

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--count" and i + 1 < len(args):
            count = int(args[i + 1])
            i += 2
        elif args[i] == "--hours" and i + 1 < len(args):
            hours_filter = float(args[i + 1])
            # Fetch more messages when filtering by time
            count = max(count, 100)
            i += 2
        else:
            i += 1

    opener = get_opener()
    token = get_token(opener)

    print(f"Fetching last {count} messages from Brain Feed chat...")
    messages = get_messages(opener, token, BRAINFEED_CHAT_ID, count=count)

    if not messages:
        print("No messages retrieved. Check permissions (im:message:readonly scope needed).")
        # Write empty digest
        with open(DIGEST_PATH, "w", encoding="utf-8") as f:
            f.write("# Lark Message Digest\n\n> No messages available. Check API permissions.\n")
        return

    print(f"Retrieved {len(messages)} messages. Building digest...")
    digest = build_digest(messages, hours_filter=hours_filter)

    if not digest:
        print("No messages matched the time filter.")
        return

    # Ensure state directory exists
    os.makedirs(os.path.dirname(DIGEST_PATH), exist_ok=True)

    with open(DIGEST_PATH, "w", encoding="utf-8") as f:
        f.write(digest)

    print(f"Digest saved to {DIGEST_PATH}")
    print(f"Messages in digest: {len(messages)}")


if __name__ == "__main__":
    main()
