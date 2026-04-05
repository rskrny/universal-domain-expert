"""
State persistence between briefing runs.

Phase 1: Write state after each run.
Phase 2: Read previous state to compute deltas (only surface changes).
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
