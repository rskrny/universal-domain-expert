"""
The Flip Side podcast production agent.

Monitors episode status, upcoming deadlines, and intelligence bot output.
Posts weekly production status to Lark group chat.

Read-only. Never modifies project files.
"""

import re
import time
from datetime import datetime, timedelta
from pathlib import Path

from .base import BaseAgent, logger


# Key deadlines (update as production progresses)
DEADLINES = {
    "episode_1_publish": "2026-04-17",
    "editor_luo_start": "2026-04-07",
}


class FlipSideAgent(BaseAgent):
    """Monitors The Flip Side podcast production."""

    def __init__(self, *args, d1_database_id: str = "961c5503-b1fc-4047-8a20-6885eb70265b", **kwargs):
        super().__init__(*args, **kwargs)
        self.d1_database_id = d1_database_id

    def _check(self) -> dict:
        findings = {}

        # 1. Read CLAUDE.md for current status
        claude_md = self._read_file_safe("CLAUDE.md")
        if claude_md:
            findings["has_claude_md"] = True
            findings["status_summary"] = self._extract_status(claude_md)
        else:
            findings["has_claude_md"] = False

        # 2. Check deadlines
        findings["deadlines"] = self._check_deadlines()

        # 3. Check intelligence bot health via D1 (the real source of truth)
        findings["bot_health"] = self._check_bot_health_d1()

        # 4. Check local briefing files as fallback
        findings["latest_briefing"] = self._check_briefings()

        # 5. Check episodes directory
        findings["episodes"] = self._check_episodes()

        # 6. Build action items
        findings["action_items"] = self._build_action_items(findings)

        return findings

    def _extract_status(self, claude_md: str) -> str:
        """Extract a brief status from CLAUDE.md content."""
        lines = claude_md.split("\n")
        # Look for status-related sections
        status_lines = []
        in_status = False
        for line in lines[:100]:  # First 100 lines
            lower = line.lower()
            if any(kw in lower for kw in ["status", "current", "active", "episode"]):
                in_status = True
            if in_status:
                if line.strip().startswith("#") and len(status_lines) > 0:
                    break
                if line.strip():
                    status_lines.append(line.strip())
                if len(status_lines) >= 5:
                    break
        return " | ".join(status_lines[:5]) if status_lines else "Status section not found"

    def _check_deadlines(self) -> list[dict]:
        """Check proximity to known deadlines."""
        now = datetime.now()
        deadline_status = []
        for name, date_str in DEADLINES.items():
            try:
                deadline = datetime.strptime(date_str, "%Y-%m-%d")
                days_until = (deadline - now).days
                status = "overdue" if days_until < 0 else "urgent" if days_until <= 3 else "upcoming" if days_until <= 7 else "on_track"
                deadline_status.append({
                    "name": name.replace("_", " ").title(),
                    "date": date_str,
                    "days_until": days_until,
                    "status": status,
                })
            except ValueError:
                continue
        return deadline_status

    def _check_bot_health_d1(self) -> dict:
        """Check the intelligence bot's D1 database for briefing freshness.

        This is the real health check. The trigger may show green checks
        but if D1 has no new rows, the bot isn't actually working.
        """
        try:
            # Import here to avoid hard dependency on Cloudflare MCP
            from retrieval.store import Store as _  # just checking we can import
            import sqlite3

            # We can't query D1 directly from here (needs MCP), so check via
            # the dashboard's own tracking of the last known briefing date.
            # The server endpoint will do the actual D1 check.
            return {
                "check_method": "requires_d1_query",
                "note": "Use /api/agents/flipside/bot-health for live D1 check",
            }
        except Exception:
            return {"check_method": "unavailable"}

    def _check_briefings(self) -> dict:
        """Check the intelligence briefings directory for latest output."""
        briefings_dir = self.folder / "intelligence" / "briefings"
        if not briefings_dir.exists():
            return {"found": False}

        briefing_files = sorted(briefings_dir.glob("*.md"), reverse=True)
        if not briefing_files:
            return {"found": False, "count": 0}

        latest = briefing_files[0]
        return {
            "found": True,
            "count": len(briefing_files),
            "latest_file": latest.name,
            "latest_date": datetime.fromtimestamp(latest.stat().st_mtime).strftime("%Y-%m-%d"),
        }

    def _check_episodes(self) -> dict:
        """Scan episodes directory for production status."""
        episodes_dir = self.folder / "episodes"
        if not episodes_dir.exists():
            return {"found": False}

        episode_dirs = [d for d in episodes_dir.iterdir() if d.is_dir()]
        return {
            "found": True,
            "count": len(episode_dirs),
            "names": [d.name for d in episode_dirs[:5]],
        }

    def _build_action_items(self, findings: dict) -> list[str]:
        """Generate actionable items based on findings."""
        items = []

        # Deadline warnings
        for d in findings.get("deadlines", []):
            if d["status"] == "overdue":
                items.append(f"OVERDUE: {d['name']} was due {abs(d['days_until'])} days ago")
            elif d["status"] == "urgent":
                items.append(f"URGENT: {d['name']} is in {d['days_until']} days ({d['date']})")

        # Briefing freshness
        briefing = findings.get("latest_briefing", {})
        if not briefing.get("found"):
            items.append("No intelligence briefings found. Check if bot is running.")

        return items

    def format_lark_card(self, findings: dict) -> str:
        """Format findings as a Lark message card."""
        lines = ["The Flip Side - Weekly Production Status", ""]

        # Deadlines
        for d in findings.get("deadlines", []):
            icon = "!" if d["status"] in ("overdue", "urgent") else ">"
            lines.append(f"{icon} {d['name']}: {d['date']} ({d['days_until']}d)")

        # Briefing status
        briefing = findings.get("latest_briefing", {})
        if briefing.get("found"):
            lines.append(f"Latest briefing: {briefing['latest_date']} ({briefing['count']} total)")

        # Episodes
        eps = findings.get("episodes", {})
        if eps.get("found"):
            lines.append(f"Episodes in production: {eps['count']}")

        # Action items
        items = findings.get("action_items", [])
        if items:
            lines.append("")
            lines.append("Action Items:")
            for item in items:
                lines.append(f"  - {item}")

        # Folder activity
        folder = findings.get("folder_status", {})
        if folder.get("latest_modified_readable"):
            lines.append(f"\nLast file change: {folder['latest_modified_readable']}")

        return "\n".join(lines)
