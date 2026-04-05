"""
Action Tracker -- the Jarvis feedback loop.

Tracks what the orchestrator recommended and whether Ryan acted on it.
Over time, this reveals:
  - Which categories of recommendations get acted on (calibrate priority weights)
  - Which projects consistently have stale recommendations (deprioritize or escalate)
  - Average time from recommendation to action (latency metric)

State stored in state/action_log.json.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent.parent
STATE_DIR = ROOT / "state"
ACTION_LOG = STATE_DIR / "action_log.json"
MAX_LOG_SIZE = 500  # cap entries to prevent bloat


def _load_log():
    """Load existing action log."""
    if not ACTION_LOG.exists():
        return []
    try:
        return json.loads(ACTION_LOG.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def _save_log(entries):
    """Save action log, capping at MAX_LOG_SIZE."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    # Keep most recent entries
    capped = entries[-MAX_LOG_SIZE:]
    ACTION_LOG.write_text(
        json.dumps(capped, indent=2, default=str),
        encoding="utf-8"
    )


def record_plan(actions):
    """
    Record a new batch of recommendations from the planner.

    Each action gets a unique ID based on (date, project, action_prefix).
    If the same recommendation appears again, it is NOT duplicated.
    Instead, its "seen_count" increments.

    Args:
        actions: list of action dicts from planner.plan()["actions"]
    """
    log = _load_log()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Index existing by their key
    existing = {}
    for entry in log:
        existing[entry.get("key", "")] = entry

    new_entries = []
    for a in actions:
        key = f"{today}|{a['project'][:30]}|{a['action'][:40]}".lower()

        if key in existing:
            existing[key]["seen_count"] = existing[key].get("seen_count", 1) + 1
            existing[key]["last_seen"] = today
            existing[key]["priority"] = a["priority"]
        else:
            new_entries.append({
                "key": key,
                "generated": today,
                "last_seen": today,
                "project": a["project"],
                "action": a["action"],
                "category": a["category"],
                "priority": a["priority"],
                "status": "pending",    # pending -> acted | dismissed | stale
                "seen_count": 1,
                "acted_date": None,
            })

    log.extend(new_entries)
    _save_log(log)
    return len(new_entries)


def mark_acted(project_substring: str, action_substring: str):
    """
    Mark a recommendation as acted on.

    Matches by substring in project and action fields.
    Returns number of entries updated.
    """
    log = _load_log()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    updated = 0

    p_lower = project_substring.lower()
    a_lower = action_substring.lower()

    for entry in log:
        if entry["status"] != "pending":
            continue
        if p_lower in entry["project"].lower() and a_lower in entry["action"].lower():
            entry["status"] = "acted"
            entry["acted_date"] = today
            updated += 1

    if updated:
        _save_log(log)
    return updated


def mark_stale(days_threshold=7):
    """
    Mark old pending recommendations as stale.

    Called periodically to clean up items that were never acted on.
    Returns number of entries marked stale.
    """
    log = _load_log()
    today = datetime.now(timezone.utc).date()
    staled = 0

    for entry in log:
        if entry["status"] != "pending":
            continue
        try:
            gen_date = datetime.strptime(entry["generated"], "%Y-%m-%d").date()
            if (today - gen_date).days > days_threshold:
                entry["status"] = "stale"
                staled += 1
        except (ValueError, KeyError):
            continue

    if staled:
        _save_log(log)
    return staled


def get_stats():
    """
    Compute action tracking statistics.

    Returns:
        {
            "total": int,
            "pending": int,
            "acted": int,
            "stale": int,
            "dismissed": int,
            "act_rate": float,       # acted / (acted + stale + dismissed)
            "by_category": {category: {acted, stale, total}},
            "avg_days_to_act": float or None,
        }
    """
    log = _load_log()

    stats = {"total": len(log), "pending": 0, "acted": 0, "stale": 0, "dismissed": 0}
    by_cat = {}
    act_days = []

    for entry in log:
        status = entry.get("status", "pending")
        stats[status] = stats.get(status, 0) + 1

        cat = entry.get("category", "unknown")
        if cat not in by_cat:
            by_cat[cat] = {"acted": 0, "stale": 0, "total": 0}
        by_cat[cat]["total"] += 1
        if status == "acted":
            by_cat[cat]["acted"] += 1
            # Compute days to act
            try:
                gen = datetime.strptime(entry["generated"], "%Y-%m-%d").date()
                act = datetime.strptime(entry["acted_date"], "%Y-%m-%d").date()
                act_days.append((act - gen).days)
            except (ValueError, KeyError, TypeError):
                pass
        elif status == "stale":
            by_cat[cat]["stale"] += 1

    # Act rate
    resolved = stats["acted"] + stats["stale"] + stats["dismissed"]
    stats["act_rate"] = round(stats["acted"] / max(resolved, 1), 3)
    stats["by_category"] = by_cat
    stats["avg_days_to_act"] = round(sum(act_days) / len(act_days), 1) if act_days else None

    return stats


if __name__ == "__main__":
    # Auto-stale old entries
    staled = mark_stale()
    if staled:
        print(f"Marked {staled} entries as stale")

    stats = get_stats()
    print(f"Action Log: {stats['total']} total")
    print(f"  Pending: {stats['pending']}")
    print(f"  Acted:   {stats['acted']}")
    print(f"  Stale:   {stats['stale']}")
    print(f"  Act rate: {stats['act_rate']:.0%}")

    if stats.get("avg_days_to_act") is not None:
        print(f"  Avg days to act: {stats['avg_days_to_act']}")

    if stats["by_category"]:
        print("\n  By category:")
        for cat, data in sorted(stats["by_category"].items()):
            print(f"    {cat}: {data['acted']}/{data['total']} acted")
