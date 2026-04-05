"""
Daily Action Planner -- the Jarvis brain.

Reasons across all perception inputs to answer ONE question:
  "What should Ryan do today?"

Inputs:
  - Project states (from project_scanner)
  - Deadlines (from deadline_scanner)
  - Reddit discoveries (from reddit_matcher)
  - Routing patterns (from routing_log.jsonl)
  - System health (from retrieval stats)

Output:
  Ranked list of ActionItem objects with priority, project, description,
  forcing function (why now), and estimated effort.

Scoring uses a weighted priority model:
  1. Time pressure (deadlines approaching)
  2. Revenue impact (money on the table)
  3. Blocked state (something is stuck)
  4. Staleness (project going cold)
  5. Opportunity cost (new info that changes priorities)
"""

import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from scripts.orchestrator import project_scanner

STATE_DIR = ROOT / "state"
ROUTING_LOG = STATE_DIR / "routing_log.jsonl"


@dataclass
class ActionItem:
    priority: float          # 0-100, higher = more urgent
    project: str             # project name
    action: str              # what to do
    why_now: str             # the forcing function
    effort: str              # "5min", "30min", "1hr", "2hr+", "session"
    category: str            # "deadline", "revenue", "blocked", "stale", "opportunity", "maintenance"
    source: str = ""         # what generated this item

    def to_dict(self):
        return {
            "priority": round(self.priority, 1),
            "project": self.project,
            "action": self.action,
            "why_now": self.why_now,
            "effort": self.effort,
            "category": self.category,
            "source": self.source,
        }


def _score_deadline_actions(projects):
    """Generate actions from approaching deadlines."""
    actions = []
    today = datetime.now(timezone.utc).date()

    for p in projects.values():
        if p.status in ("completed", "meta"):
            continue

        for date_str, days_away, context in p.deadlines:
            if days_away < 0:
                # Overdue
                actions.append(ActionItem(
                    priority=95,
                    project=p.name,
                    action=f"OVERDUE: {context}",
                    why_now=f"Was due {date_str}, {abs(days_away)} day(s) ago",
                    effort="session",
                    category="deadline",
                    source="deadline_overdue",
                ))
            elif days_away == 0:
                actions.append(ActionItem(
                    priority=90,
                    project=p.name,
                    action=f"DUE TODAY: {context}",
                    why_now=f"Deadline is today ({date_str})",
                    effort="session",
                    category="deadline",
                    source="deadline_today",
                ))
            elif days_away <= 3:
                actions.append(ActionItem(
                    priority=80 - days_away,
                    project=p.name,
                    action=context,
                    why_now=f"{days_away} day(s) until deadline ({date_str})",
                    effort="1hr",
                    category="deadline",
                    source="deadline_imminent",
                ))
            elif days_away <= 7:
                actions.append(ActionItem(
                    priority=60 - days_away,
                    project=p.name,
                    action=context,
                    why_now=f"Due this week ({date_str})",
                    effort="30min",
                    category="deadline",
                    source="deadline_week",
                ))
            elif days_away <= 14:
                actions.append(ActionItem(
                    priority=40 - (days_away - 7),
                    project=p.name,
                    action=f"Plan for: {context}",
                    why_now=f"Coming up in {days_away} days ({date_str})",
                    effort="5min",
                    category="deadline",
                    source="deadline_upcoming",
                ))

    return actions


def _score_revenue_actions(projects):
    """Generate actions for revenue-related items."""
    actions = []

    for p in projects.values():
        if p.status in ("completed", "meta"):
            continue

        # Projects with active revenue signals AND waiting items
        if p.revenue_signals and p.waiting_on:
            actions.append(ActionItem(
                priority=70,
                project=p.name,
                action=f"Follow up: {p.waiting_on[0]}",
                why_now=f"Revenue at stake. {p.revenue_signals[0] if p.revenue_signals else ''}",
                effort="30min",
                category="revenue",
                source="revenue_waiting",
            ))
        elif p.revenue_signals and p.status == "proposal":
            actions.append(ActionItem(
                priority=65,
                project=p.name,
                action=f"Push proposal forward",
                why_now=f"Active proposal with {p.revenue_signals[0] if p.revenue_signals else 'revenue potential'}",
                effort="30min",
                category="revenue",
                source="revenue_proposal",
            ))

    return actions


def _score_blocked_actions(projects):
    """Generate actions for stuck projects."""
    actions = []

    for p in projects.values():
        if p.status in ("completed", "meta"):
            continue

        for blocker in p.blockers:
            actions.append(ActionItem(
                priority=55,
                project=p.name,
                action=f"Unblock: {blocker}",
                why_now="Project is stuck. Every day blocked is a day lost.",
                effort="1hr",
                category="blocked",
                source="blocker_detected",
            ))

        for waiting in p.waiting_on:
            # Waiting items get lower priority than blockers (less in your control)
            actions.append(ActionItem(
                priority=45,
                project=p.name,
                action=f"Check status: {waiting}",
                why_now="Pending external response. Follow up to keep momentum.",
                effort="5min",
                category="blocked",
                source="waiting_on",
            ))

    return actions


def _score_stale_actions(projects):
    """Generate nudges for projects going cold."""
    actions = []

    for p in projects.values():
        if p.status in ("completed", "early", "meta"):
            continue

        if p.days_stale > 14 and p.status in ("development", "production"):
            actions.append(ActionItem(
                priority=35,
                project=p.name,
                action=f"Touch base. No updates in {p.days_stale} days.",
                why_now=f"Project going cold. Last updated {p.days_stale} days ago.",
                effort="5min",
                category="stale",
                source="stale_project",
            ))
        elif p.days_stale > 7 and p.status == "proposal":
            actions.append(ActionItem(
                priority=50,  # proposals going cold are worse
                project=p.name,
                action=f"Follow up on proposal. {p.days_stale} days since update.",
                why_now="Proposals die from silence. Follow up before they forget you.",
                effort="30min",
                category="stale",
                source="stale_proposal",
            ))

    return actions


def _score_opportunity_actions(reddit_matches=None):
    """Generate actions from new intelligence discoveries."""
    actions = []

    if not reddit_matches:
        return actions

    for m in reddit_matches:
        rec = m.get("recommendation", "Note")
        if rec == "Implement":
            actions.append(ActionItem(
                priority=40,
                project=m.get("matched_project", "General"),
                action=f"Evaluate: {m.get('title', '')[:80]}",
                why_now=m.get("rec_reason", "New tool/technique discovered"),
                effort="30min",
                category="opportunity",
                source="reddit_implement",
            ))
        elif rec == "Watch":
            actions.append(ActionItem(
                priority=20,
                project=m.get("matched_project", "General"),
                action=f"Bookmark: {m.get('title', '')[:80]}",
                why_now=m.get("rec_reason", "Relevant development worth tracking"),
                effort="5min",
                category="opportunity",
                source="reddit_watch",
            ))

    return actions


def _score_maintenance_actions(system_stats=None):
    """Generate system maintenance recommendations."""
    actions = []

    # Check if git has a remote configured
    try:
        import subprocess
        result = subprocess.run(
            ["git", "remote"],
            cwd=str(ROOT),
            capture_output=True, text=True, timeout=5,
        )
        has_remote = bool(result.stdout.strip())
    except Exception:
        has_remote = False

    if not has_remote:
        actions.append(ActionItem(
            priority=60,
            project="Domain Expert System",
            action="Set up GitHub remote. All commits are local only.",
            why_now="One bad disk and 18+ sessions of work is gone.",
            effort="5min",
            category="maintenance",
            source="no_git_remote",
        ))

    return actions


def _get_routing_patterns():
    """Analyze routing log for recent activity patterns."""
    patterns = {
        "total_queries": 0,
        "recent_domains": [],  # domains used in last 7 days
        "top_domains": [],     # most-used domains overall
    }

    if not ROUTING_LOG.exists():
        return patterns

    try:
        lines = ROUTING_LOG.read_text(encoding="utf-8").strip().split("\n")
        entries = [json.loads(l) for l in lines if l.strip()]
    except Exception:
        return patterns

    patterns["total_queries"] = len(entries)

    # Domain frequency
    domain_counts = {}
    for entry in entries:
        domain = entry.get("domain", "")
        if domain:
            domain_counts[domain] = domain_counts.get(domain, 0) + 1

    sorted_domains = sorted(domain_counts.items(), key=lambda x: x[1], reverse=True)
    patterns["top_domains"] = sorted_domains[:10]

    return patterns


def plan(reddit_matches=None, system_stats=None):
    """
    Generate today's action plan.

    Returns:
        {
            "generated": ISO timestamp,
            "actions": [ActionItem.to_dict(), ...],  # sorted by priority desc
            "project_summary": {...},  # from project_scanner.summarize()
            "routing_patterns": {...},
            "focus_areas": [str, ...],  # top 3 categories for today
        }
    """
    # Scan all projects
    projects = project_scanner.scan_all()
    summary = project_scanner.summarize(projects)

    # Generate actions from all scoring functions
    all_actions = []
    all_actions.extend(_score_deadline_actions(projects))
    all_actions.extend(_score_revenue_actions(projects))
    all_actions.extend(_score_blocked_actions(projects))
    all_actions.extend(_score_stale_actions(projects))
    all_actions.extend(_score_opportunity_actions(reddit_matches))
    all_actions.extend(_score_maintenance_actions(system_stats))

    # Deduplicate by (project, action prefix)
    seen = set()
    unique = []
    for a in all_actions:
        key = (a.project.lower(), a.action[:40].lower())
        if key not in seen:
            seen.add(key)
            unique.append(a)

    # Sort by priority descending
    unique.sort(key=lambda a: a.priority, reverse=True)

    # Determine focus areas (top 3 categories by highest-priority item)
    category_max = {}
    for a in unique:
        if a.category not in category_max or a.priority > category_max[a.category]:
            category_max[a.category] = a.priority
    focus = sorted(category_max.keys(), key=lambda c: category_max[c], reverse=True)[:3]

    # Get routing patterns
    routing = _get_routing_patterns()

    return {
        "generated": datetime.now(timezone.utc).isoformat(),
        "actions": [a.to_dict() for a in unique[:15]],  # top 15
        "project_summary": summary,
        "routing_patterns": routing,
        "focus_areas": focus,
    }


def format_plan(plan_data):
    """Format the plan as readable markdown for the briefing."""
    lines = []

    actions = plan_data.get("actions", [])
    if not actions:
        lines.append("No action items detected.")
        return "\n".join(lines)

    # Top 3 focus items
    top = actions[:3]
    lines.append("### Today's Focus")
    for i, a in enumerate(top, 1):
        priority_tag = "URGENT" if a["priority"] >= 80 else "HIGH" if a["priority"] >= 60 else "MEDIUM"
        lines.append(f"{i}. **[{priority_tag}]** {a['project']}: {a['action']}")
        lines.append(f"   Why now: {a['why_now']} ({a['effort']})")
    lines.append("")

    # Remaining items grouped by category
    remaining = actions[3:]
    if remaining:
        lines.append("### Also on Radar")
        for a in remaining[:7]:
            lines.append(f"- [{a['category'].upper()}] {a['project']}: {a['action']}")
        lines.append("")

    # Project health pulse
    summary = plan_data.get("project_summary", {})
    if summary.get("stale_projects") or summary.get("blocked_projects"):
        lines.append("### Project Health")
        for s in summary.get("stale_projects", [])[:3]:
            lines.append(f"- {s['name']}: no updates in {s['days_stale']} days ({s['status']})")
        for b in summary.get("blocked_projects", [])[:3]:
            items = b.get("waiting_on", []) or b.get("blockers", [])
            lines.append(f"- {b['name']}: waiting on {items[0] if items else 'unknown'}")
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    result = plan()
    print(format_plan(result))
    print(f"\n--- Raw ({len(result['actions'])} actions) ---")
    for a in result["actions"]:
        print(f"  [{a['priority']:5.1f}] [{a['category']:12s}] {a['project']}: {a['action'][:60]}")
