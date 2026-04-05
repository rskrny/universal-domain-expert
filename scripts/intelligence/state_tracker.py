"""
State persistence and delta computation between briefing runs.

Tracks what was surfaced in each run. On the next run, computes deltas
so only NEW information gets highlighted. Repeat items are still included
but marked as "seen before" so the card stays useful without nagging.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
STATE_FILE = ROOT / "state" / "briefing_state.json"


def save(deadlines, reddit_matches, system_stats=None):
    """Save current briefing state for future delta computation."""
    state = {
        "last_run": datetime.now(timezone.utc).isoformat(),
        "deadlines_surfaced": [
            f"{d['date']}|{d['project']}" for d in deadlines
        ],
        "reddit_ids_surfaced": [
            m.get("id", m.get("url", "")) for m in reddit_matches
        ],
        "reddit_count": len(reddit_matches),
        "deadline_count": len(deadlines),
        "system_stats": system_stats or {},
    }

    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return state


def load_previous():
    """Load the previous run's state. Returns None if no previous run."""
    if not STATE_FILE.exists():
        return None
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def compute_deltas(deadlines, reddit_matches, system_stats=None):
    """
    Compare current data against previous run. Returns a delta dict:
    {
        "new_deadlines": [...],        # deadlines not in previous run
        "new_reddit": [...],           # reddit posts not previously surfaced
        "returning_reddit": [...],     # posts seen before (still relevant)
        "deadline_changes": str,       # human summary of deadline movement
        "stats_delta": {...},          # changes in system stats
        "is_first_run": bool,          # True if no previous state exists
    }
    """
    prev = load_previous()

    if prev is None:
        return {
            "new_deadlines": deadlines,
            "new_reddit": reddit_matches,
            "returning_reddit": [],
            "deadline_changes": None,
            "stats_delta": {},
            "is_first_run": True,
        }

    # Deadline deltas
    prev_dl_keys = set(prev.get("deadlines_surfaced", []))
    curr_dl_keys = {f"{d['date']}|{d['project']}" for d in deadlines}
    new_dl_keys = curr_dl_keys - prev_dl_keys

    new_deadlines = [
        d for d in deadlines
        if f"{d['date']}|{d['project']}" in new_dl_keys
    ]

    # Deadline movement summary
    dl_change = None
    prev_count = prev.get("deadline_count", 0)
    curr_count = len(deadlines)
    if curr_count > prev_count:
        dl_change = f"+{curr_count - prev_count} new deadline(s) since last briefing"
    elif curr_count < prev_count:
        dl_change = f"{prev_count - curr_count} deadline(s) cleared since last briefing"

    # Reddit deltas
    prev_ids = set(prev.get("reddit_ids_surfaced", []))
    new_reddit = []
    returning_reddit = []
    for m in reddit_matches:
        mid = m.get("id", m.get("url", ""))
        if mid in prev_ids:
            returning_reddit.append(m)
        else:
            new_reddit.append(m)

    # System stats deltas
    stats_delta = {}
    prev_stats = prev.get("system_stats", {})
    if system_stats and prev_stats:
        for key in ["chunks", "queries", "routed"]:
            old_val = prev_stats.get(key, 0)
            new_val = (system_stats or {}).get(key, 0)
            if old_val and new_val and new_val != old_val:
                stats_delta[key] = new_val - old_val

    return {
        "new_deadlines": new_deadlines,
        "new_reddit": new_reddit,
        "returning_reddit": returning_reddit,
        "deadline_changes": dl_change,
        "stats_delta": stats_delta,
        "is_first_run": False,
    }
