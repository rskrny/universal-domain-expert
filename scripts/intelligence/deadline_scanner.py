"""
Scan memory files for upcoming deadlines and action items.

Extracted from daily_briefing.py lines 66-146, with improvements:
- 14-day window instead of 30 (urgent only)
- Skips completed/paid/done items
- Categorizes by urgency: TODAY, THIS_WEEK, UPCOMING
- Detects token/auth expiry dates
"""

import os
import re
from datetime import datetime, timezone
from pathlib import Path

MEMORY_DIR = Path(os.getenv(
    "MEMORY_DIR",
    str(Path.home() / ".claude" / "projects"
        / "C--Users-rskrn-Desktop-universal-domain-expert---Copy" / "memory")
))

# Words near a date that indicate it is a deadline (not just a timestamp)
DEADLINE_SIGNALS = [
    "must", "due", "deadline", "by ", "expires", "expiring",
    "file by", "mail by", "before", "cutoff", "renew", "send by",
]

# Words near a date that mean the item is already handled
DONE_SIGNALS = [
    "complete", "completed", "paid", "done", "delivered",
    "shipped", "sent", "finished", "resolved",
]

# Words that are just metadata timestamps, not deadlines
METADATA_SIGNALS = [
    "updated", "generated", "as of", "last ", "since ",
    "created", "logged", "recorded", "migrated",
]


def scan(window_days=14):
    """
    Scan memory files for upcoming deadlines.

    Returns list of dicts sorted by urgency:
        {date, days_away, project, context, urgency}

    urgency is one of: "TODAY", "THIS_WEEK", "UPCOMING"
    """
    deadlines = []
    today = datetime.now(timezone.utc).date()

    if not MEMORY_DIR.exists():
        return deadlines

    for md_file in MEMORY_DIR.glob("project_*.md"):
        text = md_file.read_text(encoding="utf-8", errors="replace")

        # Strip YAML frontmatter
        if text.startswith("---"):
            end = text.find("---", 3)
            if end > 0:
                text = text[end + 3:]

        project_name = md_file.stem.replace("project_", "").replace("_", " ").title()

        # Find ISO dates (2026-04-08)
        for match in re.finditer(r"\d{4}-\d{2}-\d{2}", text):
            date_str = match.group()
            try:
                d = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                continue

            days_away = (d - today).days
            if days_away < 0 or days_away > window_days:
                continue

            # Get context window around the date
            idx = match.start()
            start = max(0, idx - 100)
            end = min(len(text), idx + len(date_str) + 100)

            # Snap to word boundary
            while start > 0 and text[start] not in (" ", "\n", "\t"):
                start += 1
            window = text[start:end].strip()
            nearby = window.lower()

            # Skip metadata dates
            local_idx = idx - start
            pre = window[max(0, local_idx - 40):local_idx].lower()
            if any(sw in pre for sw in METADATA_SIGNALS):
                continue

            # Skip completed items
            if any(dw in nearby for dw in DONE_SIGNALS):
                continue

            # Only keep dates near actual deadline language
            if not any(sig in nearby for sig in DEADLINE_SIGNALS):
                continue

            # Clean context for display
            context_raw = window.replace(date_str, "").strip()
            context = " ".join(context_raw.split())[:120]

            # Categorize urgency
            if days_away == 0:
                urgency = "TODAY"
            elif days_away <= 7:
                urgency = "THIS_WEEK"
            else:
                urgency = "UPCOMING"

            deadlines.append({
                "date": date_str,
                "days_away": days_away,
                "project": project_name,
                "context": context,
                "urgency": urgency,
            })

    # Deduplicate by (date, project)
    seen = set()
    unique = []
    for dl in sorted(deadlines, key=lambda x: x["days_away"]):
        key = (dl["date"], dl["project"])
        if key not in seen:
            seen.add(key)
            unique.append(dl)

    return unique[:10]
