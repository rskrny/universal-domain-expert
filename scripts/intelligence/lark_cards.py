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


def _rec_icon(rec):
    """Emoji prefix for recommendation level."""
    return {"Implement": ">>", "Watch": ">", "Note": "-"}.get(rec, "-")


def _format_reddit_matches(matches):
    """Format matched Reddit posts as lark_md text with actionable recommendations."""
    if not matches:
        return None

    lines = ["**Discoveries**"]
    for m in matches[:5]:
        title = m["title"][:65]
        url = m["url"]
        rec = m.get("recommendation", "Note")
        rec_reason = m.get("rec_reason", "")
        icon = _rec_icon(rec)

        lines.append(f"{icon} **{rec}**: [{title}]({url})")
        if rec_reason:
            lines.append(f"   {rec_reason}")

    if len(matches) > 5:
        lines.append(f"+ {len(matches) - 5} more")

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


def _format_action_plan(plan_data):
    """Format orchestrator action plan as lark_md text."""
    if not plan_data:
        return None

    actions = plan_data.get("actions", [])
    if not actions:
        return None

    lines = ["**Today's Focus**"]
    for a in actions[:3]:
        tag = "URGENT" if a["priority"] >= 80 else "HIGH" if a["priority"] >= 60 else ""
        prefix = f"[{tag}] " if tag else ""
        lines.append(f">> {prefix}{a['project']}: {a['action'][:70]}")
        lines.append(f"   {a['why_now'][:80]}")

    # Compact "also on radar" for items 4-7
    remaining = actions[3:7]
    if remaining:
        lines.append("")
        lines.append("**Also on Radar**")
        for a in remaining:
            lines.append(f"- {a['project']}: {a['action'][:60]}")

    return "\n".join(lines)


def build_morning_intel(deadlines, reddit_matches, system_stats=None, deltas=None, plan_data=None):
    """
    Build the morning intelligence card.

    Args:
        deadlines: All current deadlines
        reddit_matches: All matched Reddit posts (with recommendation fields)
        system_stats: System health metrics
        deltas: Output from state_tracker.compute_deltas(). If provided,
                new items are highlighted and returning items are condensed.
        plan_data: Output from orchestrator.planner.plan(). If provided,
                   today's prioritized action plan is shown first.

    Returns a Lark interactive card dict ready for send_message().
    """
    now = _now_hst()
    date_str = now.strftime("%b %d")

    color = _header_color(deadlines)

    # Upgrade color if orchestrator found urgent items
    if plan_data and plan_data.get("actions"):
        top_priority = plan_data["actions"][0].get("priority", 0)
        if top_priority >= 80 and color != "red":
            color = "orange"

    # Build card elements
    elements = []

    # NEW: Orchestrator action plan (top of card, most important)
    plan_text = _format_action_plan(plan_data)
    if plan_text:
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": plan_text},
        })

    # Delta summary line (if we have prior state to compare)
    if deltas and not deltas.get("is_first_run"):
        delta_parts = []
        new_r = len(deltas.get("new_reddit", []))
        if new_r:
            delta_parts.append(f"{new_r} new discovery(s)")
        new_d = len(deltas.get("new_deadlines", []))
        if new_d:
            delta_parts.append(f"{new_d} new deadline(s)")
        dl_change = deltas.get("deadline_changes")
        if dl_change and not new_d:
            delta_parts.append(dl_change)

        if delta_parts:
            elements.append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": "**Changes:** " + " | ".join(delta_parts)},
            })
        else:
            elements.append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": "No changes since last briefing."},
            })
            color = "green"

    # Section 1: Deadlines (only if any exist)
    deadline_text = _format_deadlines(deadlines)
    if deadline_text:
        if elements:
            elements.append({"tag": "hr"})
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": deadline_text},
        })

    # Section 2: New discoveries first, then returning
    if deltas and not deltas.get("is_first_run"):
        new_reddit = deltas.get("new_reddit", [])
        returning = deltas.get("returning_reddit", [])

        if new_reddit:
            new_text = _format_reddit_matches(new_reddit)
            if new_text:
                if elements:
                    elements.append({"tag": "hr"})
                elements.append({
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": new_text},
                })

        if returning:
            # Compact list for items already seen
            ret_lines = [f"**Still relevant** ({len(returning)})"]
            for m in returning[:3]:
                title = m["title"][:50]
                ret_lines.append(f"- {m.get('recommendation', 'Note')}: {title}")
            if elements:
                elements.append({"tag": "hr"})
            elements.append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": "\n".join(ret_lines)},
            })
    else:
        # First run or no delta data: show all matches
        reddit_text = _format_reddit_matches(reddit_matches)
        if reddit_text:
            if elements:
                elements.append({"tag": "hr"})
            elements.append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": reddit_text},
            })

    # Section 3: System pulse (compact, with delta if available)
    if system_stats:
        pulse_text = _format_system_pulse(system_stats)
        if deltas and deltas.get("stats_delta"):
            sd = deltas["stats_delta"]
            delta_parts = []
            if sd.get("chunks"):
                delta_parts.append(f"chunks {'+' if sd['chunks'] > 0 else ''}{sd['chunks']}")
            if sd.get("queries"):
                delta_parts.append(f"queries {'+' if sd['queries'] > 0 else ''}{sd['queries']}")
            if delta_parts and pulse_text:
                pulse_text += " (" + ", ".join(delta_parts) + ")"
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
            "text": {"tag": "lark_md", "content": "All clear. No deadlines. No new discoveries. Good day for deep work."},
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
