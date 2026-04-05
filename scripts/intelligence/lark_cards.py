"""
Lark interactive card builder for intelligence briefings.

Uses the Lark message card format with:
- Color-coded headers (red=urgent, orange=soon, blue=normal, green=clear)
- lark_md sections with bold, links, line breaks
- Horizontal dividers between sections
- Max 3 sections per card to keep it readable on mobile
"""

import json
from datetime import datetime, timezone, timedelta


# Hawaii timezone for display
HST = timedelta(hours=-10)


def _now_hst():
    return datetime.now(timezone.utc) + HST


def _header_color(deadlines):
    """Pick header color based on deadline urgency."""
    if not deadlines:
        return "green"
    min_days = min(d["days_away"] for d in deadlines)
    if min_days == 0:
        return "red"
    elif min_days <= 3:
        return "orange"
    return "blue"


def _format_deadlines(deadlines):
    """Format deadline items as lark_md text."""
    if not deadlines:
        return None

    lines = ["**Action Required**"]
    for dl in deadlines[:5]:
        urgency_label = ""
        if dl["urgency"] == "TODAY":
            urgency_label = "TODAY"
        elif dl["urgency"] == "THIS_WEEK":
            urgency_label = f"{dl['days_away']}d"
        else:
            urgency_label = f"{dl['days_away']}d"

        context = dl["context"][:80] if dl["context"] else dl["project"]
        lines.append(f"{dl['project']} ({urgency_label}): {context}")

    return "\n".join(lines)


def _format_reddit_matches(matches):
    """Format matched Reddit posts as lark_md text."""
    if not matches:
        return None

    lines = ["**Relevant Discoveries**"]
    for m in matches[:5]:
        title = m["title"][:70]
        project = m["matched_project"]
        reason_keywords = ", ".join(m.get("matched_keywords", [])[:3])
        url = m["url"]
        lines.append(f"[{title}]({url})")
        lines.append(f"  -> {project}: {reason_keywords}")

    if len(matches) > 5:
        lines.append(f"  + {len(matches) - 5} more matched posts")

    return "\n".join(lines)


def _format_system_pulse(stats):
    """Format system health as compact lark_md text."""
    parts = []
    if stats.get("chunks"):
        parts.append(f"{stats['chunks']:,} chunks")
    if stats.get("queries"):
        parts.append(f"{stats['queries']} queries routed")

    if not parts:
        return None

    return "**System** | " + " | ".join(parts)


def build_morning_intel(deadlines, reddit_matches, system_stats=None):
    """
    Build the morning intelligence card.

    Returns a Lark interactive card dict ready for send_message().
    """
    now = _now_hst()
    date_str = now.strftime("%b %d")

    color = _header_color(deadlines)

    # Build card elements
    elements = []

    # Section 1: Deadlines (only if any exist)
    deadline_text = _format_deadlines(deadlines)
    if deadline_text:
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": deadline_text},
        })

    # Section 2: Reddit Intelligence (only if matches exist)
    reddit_text = _format_reddit_matches(reddit_matches)
    if reddit_text:
        if elements:
            elements.append({"tag": "hr"})
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": reddit_text},
        })

    # Section 3: System pulse (compact)
    if system_stats:
        pulse_text = _format_system_pulse(system_stats)
        if pulse_text:
            if elements:
                elements.append({"tag": "hr"})
            elements.append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": pulse_text},
            })

    # Fallback if nothing to report
    if not elements:
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": "All clear. No deadlines. No matched discoveries. Good day for deep work."},
        })
        color = "green"

    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"Morning Intel | {date_str}"},
            "template": color,
        },
        "elements": elements,
    }

    return card


def card_to_json(card):
    """Serialize card dict for Lark API send_message."""
    return json.dumps(card)
