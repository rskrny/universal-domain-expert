"""
Deep project state reader.

Parses all project_*.md memory files into structured ProjectState objects.
Goes beyond deadline scanning to detect:
  - Status category (production, development, proposal, early, completed)
  - Staleness (days since memory was last updated)
  - Blockers and waiting items
  - Next actions
  - Pending communications (waiting on replies)
  - Revenue/financial signals

This is the perception layer for projects. The planner reasons over these states.
"""

import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

MEMORY_DIR = Path(os.getenv(
    "MEMORY_DIR",
    str(Path.home() / ".claude" / "projects"
        / "C--Users-rskrn-Desktop-universal-domain-expert---Copy" / "memory")
))


@dataclass
class ProjectState:
    key: str                          # e.g. "flipside_status"
    name: str                         # e.g. "Flipside Status"
    file_path: str
    status: str = "unknown"           # production, development, proposal, early, completed
    last_modified: Optional[datetime] = None
    days_stale: int = 0               # days since file was last modified
    blockers: list = field(default_factory=list)
    waiting_on: list = field(default_factory=list)   # "waiting on X" items
    next_actions: list = field(default_factory=list)
    deadlines: list = field(default_factory=list)     # (date_str, context) tuples
    revenue_signals: list = field(default_factory=list)
    raw_text: str = ""


# Status detection patterns. Order matters: first match wins.
STATUS_PATTERNS = [
    ("completed", [
        r"\bcompleted?\b", r"\bdelivered\b", r"\bfinished\b",
        r"\bshipped\b", r"\bdone\b", r"\bpaid.*delivered\b",
    ]),
    ("production", [
        r"\bproduction\b.*running", r"\blive\b", r"\bdeployed\b",
        r"fishingbloodline\.com", r"\boperational\b",
    ]),
    ("proposal", [
        r"\bproposal\b", r"\bwaiting on.*procurement\b",
        r"\bpricing\b.*sent", r"\bquote\b",
    ]),
    ("early", [
        r"\bearly stage\b", r"\bexploring\b", r"\bresearch\b",
        r"\bconcept\b",
    ]),
    ("development", [
        r"\bin development\b", r"\bbuilding\b", r"\bin progress\b",
        r"\bediting\b", r"\btesting\b", r"\bphase\b",
    ]),
]

# Blocker patterns
BLOCKER_PATTERNS = [
    r"(?:blocked|blocking|blocker)[:\s]+(.{10,80})",
    r"(?:need[s]? to|must)\s+(.{10,60})\s+(?:before|first)",
    r"(?:can't|cannot)\s+(.{10,60})\s+(?:until|without)",
]

# Waiting-on patterns
WAITING_PATTERNS = [
    r"[Ww]aiting (?:on|for)\s+(.{5,80}?)(?:\.|$|\n)",
    r"[Pp]ending\s+(.{5,60}?)(?:\.|$|\n)",
    r"[Nn]eed[s]? (?:reply|response|confirmation) from\s+(.{5,40})",
    r"[Aa]waiting\s+(.{5,60}?)(?:\.|$|\n)",
]

# Revenue signals
REVENUE_PATTERNS = [
    r"\$[\d,]+(?:\.\d{2})?(?:K|k)?",     # Dollar amounts
    r"(?:revenue|payment|invoice|paid)\s*[:\s]+(.{5,60})",
    r"(?:accepted|signed|closed)\s+(?:at|for)\s+\$",
]


def _detect_status(text, frontmatter=""):
    """
    Classify project status from text content.

    Uses a scoring approach instead of first-match. Counts how many signals
    point to each status, weighted by position (early in text = stronger signal).
    Frontmatter description is highest weight.
    """
    text_lower = text.lower()
    fm_lower = frontmatter.lower()

    # Score each status
    scores = {}
    for status, patterns in STATUS_PATTERNS:
        score = 0
        for pattern in patterns:
            # Check frontmatter first (strongest signal)
            if re.search(pattern, fm_lower):
                score += 5

            # Check first 200 chars (likely the summary/header)
            if re.search(pattern, text_lower[:200]):
                score += 3

            # Count total matches (weak signal per match)
            matches = list(re.finditer(pattern, text_lower))
            score += len(matches) * 0.5

        if score > 0:
            scores[status] = score

    if not scores:
        return "development"

    # If "completed" only scores from scattered mentions (< 3), ignore it
    # Real completed projects have it in the summary/frontmatter
    if "completed" in scores and scores["completed"] < 3:
        del scores["completed"]

    if not scores:
        return "development"

    # Return highest-scoring status
    return max(scores, key=scores.get)


def _extract_patterns(text, patterns):
    """Extract all matches for a list of patterns."""
    results = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.MULTILINE):
            captured = match.group(1) if match.lastindex else match.group(0)
            cleaned = " ".join(captured.strip().split())[:120]
            if cleaned and cleaned not in results:
                results.append(cleaned)
    return results


def _extract_next_actions(text):
    """Find next action items from checkbox patterns and explicit markers."""
    actions = []

    # Unchecked checkboxes: - [ ] something
    for match in re.finditer(r"- \[ \]\s+(.{5,120})", text):
        action = match.group(1).strip()
        if action not in actions:
            actions.append(action)

    # "Next:" or "Next steps:" sections
    next_match = re.search(
        r"(?:next steps?|next actions?|todo|to do)[:\s]*\n((?:[-*]\s+.+\n?)+)",
        text, re.IGNORECASE
    )
    if next_match:
        for line in next_match.group(1).split("\n"):
            line = re.sub(r"^[-*\s]+", "", line).strip()
            if len(line) > 5 and line not in actions:
                actions.append(line[:120])

    return actions[:8]  # cap at 8


def _extract_deadlines(text):
    """
    Extract dates that represent actual deadlines.

    Filters out:
      - Metadata timestamps (updated, generated, as of, since)
      - Completed items (paid, delivered, completed, done)
      - Plain reference dates with no action language nearby
    """
    # Signals that a date IS a real deadline
    deadline_signals = [
        "must", "due", "deadline", "by ", "expires", "expiring",
        "file by", "mail by", "before", "cutoff", "renew", "send by",
        "scheduled", "joining", "starts", "launch",
    ]

    # Signals that a date is already handled or just metadata
    done_signals = [
        "complete", "completed", "paid", "done", "delivered",
        "shipped", "sent", "finished", "resolved", "confirmed",
    ]
    metadata_signals = [
        "updated", "generated", "as of", "last ", "since ",
        "created", "logged", "recorded", "migrated", "status",
        "prepared", "transfer", "received",
    ]

    deadlines = []
    today = datetime.now(timezone.utc).date()

    for match in re.finditer(r"\d{4}-\d{2}-\d{2}", text):
        date_str = match.group()
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            continue

        days_away = (d - today).days
        if days_away < -7 or days_away > 90:
            continue

        # Context window around the date
        idx = match.start()
        start = max(0, idx - 100)
        end = min(len(text), idx + len(date_str) + 100)

        # Snap to word boundary
        while start > 0 and text[start] not in (" ", "\n", "\t"):
            start += 1
        window = text[start:end].strip()
        nearby = window.lower()

        # Check the text BEFORE the date for metadata markers
        pre_start = max(0, idx - 40)
        pre_text = text[pre_start:idx].lower()
        if any(sig in pre_text for sig in metadata_signals):
            continue

        # Skip completed items
        if any(sig in nearby for sig in done_signals):
            continue

        # Only keep dates near actual deadline/action language
        if not any(sig in nearby for sig in deadline_signals):
            continue

        # Clean context for display
        context_raw = window.replace(date_str, "").strip()
        context = " ".join(context_raw.split())[:120]

        deadlines.append((date_str, days_away, context))

    # Deduplicate by date
    seen = set()
    unique = []
    for dl in deadlines:
        if dl[0] not in seen:
            seen.add(dl[0])
            unique.append(dl)

    return unique


def scan_project(file_path):
    """Parse a single project memory file into a ProjectState."""
    path = Path(file_path)
    text = path.read_text(encoding="utf-8", errors="replace")

    # Split YAML frontmatter from body
    frontmatter = ""
    body = text
    if body.startswith("---"):
        end = body.find("---", 3)
        if end > 0:
            frontmatter = body[3:end]
            body = body[end + 3:]

    # File metadata
    stat = path.stat()
    modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
    days_stale = (datetime.now(timezone.utc) - modified).days

    # Key from filename
    key = path.stem.replace("project_", "")
    name = key.replace("_", " ").title()

    # The "all_projects_map" is a meta-file, not a single project
    is_meta = key in ("all_projects_map",)

    return ProjectState(
        key=key,
        name=name,
        file_path=str(path),
        status="meta" if is_meta else _detect_status(body, frontmatter),
        last_modified=modified,
        days_stale=days_stale,
        blockers=_extract_patterns(body, BLOCKER_PATTERNS),
        waiting_on=_extract_patterns(body, WAITING_PATTERNS),
        next_actions=_extract_next_actions(body),
        deadlines=_extract_deadlines(body),
        revenue_signals=_extract_patterns(body, REVENUE_PATTERNS),
        raw_text=body,
    )


def scan_all():
    """
    Scan all project memory files. Returns dict of key -> ProjectState.

    Skips non-project memory files (user_*, feedback_*, reference_*).
    """
    projects = {}

    if not MEMORY_DIR.exists():
        return projects

    for md_file in sorted(MEMORY_DIR.glob("project_*.md")):
        try:
            state = scan_project(md_file)
            projects[state.key] = state
        except Exception as e:
            print(f"  Warning: failed to scan {md_file.name}: {e}")

    return projects


def summarize(projects):
    """
    Generate a compact summary of all project states.

    Returns a dict with:
      - active_count, stale_count, blocked_count
      - stale_projects (>7 days since update)
      - blocked_projects (have blockers or waiting items)
      - upcoming_deadlines (within 14 days)
      - revenue_active (projects with $ signals)
    """
    active = [p for p in projects.values() if p.status not in ("completed", "meta")]
    stale = [p for p in active if p.days_stale > 7]
    blocked = [p for p in active if p.blockers or p.waiting_on]

    upcoming = []
    for p in active:
        for date_str, days_away, context in p.deadlines:
            if 0 <= days_away <= 14:
                upcoming.append({
                    "project": p.name,
                    "date": date_str,
                    "days_away": days_away,
                    "context": context,
                })
    upcoming.sort(key=lambda x: x["days_away"])

    revenue = [p for p in active if p.revenue_signals]

    return {
        "active_count": len(active),
        "stale_count": len(stale),
        "blocked_count": len(blocked),
        "stale_projects": [
            {"name": p.name, "days_stale": p.days_stale, "status": p.status}
            for p in stale
        ],
        "blocked_projects": [
            {
                "name": p.name,
                "blockers": p.blockers,
                "waiting_on": p.waiting_on,
            }
            for p in blocked
        ],
        "upcoming_deadlines": upcoming[:10],
        "revenue_active": [
            {"name": p.name, "signals": p.revenue_signals[:3]}
            for p in revenue
        ],
    }


if __name__ == "__main__":
    import json

    projects = scan_all()
    print(f"Scanned {len(projects)} projects\n")

    for key, p in projects.items():
        print(f"  {p.name}")
        print(f"    Status: {p.status} | Stale: {p.days_stale}d")
        if p.waiting_on:
            print(f"    Waiting: {p.waiting_on}")
        if p.next_actions:
            print(f"    Next: {p.next_actions[:2]}")
        if p.deadlines:
            print(f"    Deadlines: {[(d[0], d[1]) for d in p.deadlines[:3]]}")
        print()

    summary = summarize(projects)
    print("Summary:")
    print(json.dumps(summary, indent=2, default=str))
