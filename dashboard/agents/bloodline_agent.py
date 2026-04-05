"""
Bloodline Charters site health agent.

Pings production URL, reads latest maintenance reports, checks for issues.
Reports findings to the dashboard. Does NOT run npm/build/lint (RAM constraint).

Read-only. Never modifies project files.
"""

import time
from datetime import datetime
from pathlib import Path

from .base import BaseAgent, logger


class BloodlineAgent(BaseAgent):
    """Monitors Bloodline Charters site health."""

    def _check(self) -> dict:
        findings = {}

        # 1. Ping production URL
        prod_url = self.config.get("production_url", "https://fishingbloodline.com")
        findings["site_health"] = self._ping_site(prod_url)

        # 2. Read latest maintenance reports
        findings["maintenance"] = self._check_maintenance_reports()

        # 3. Check CLAUDE.md for known issues
        claude_md = self._read_file_safe("bloodline-site/CLAUDE.md")
        if claude_md:
            findings["has_claude_md"] = True
        else:
            findings["has_claude_md"] = False

        # 4. Build action items
        findings["action_items"] = self._build_action_items(findings)

        return findings

    def _ping_site(self, url: str) -> dict:
        """HTTP GET the production URL. Returns status and response time."""
        try:
            import httpx
            start = time.time()
            response = httpx.get(url, timeout=15, follow_redirects=True)
            elapsed_ms = round((time.time() - start) * 1000)

            return {
                "url": url,
                "status_code": response.status_code,
                "response_ms": elapsed_ms,
                "healthy": 200 <= response.status_code < 400,
                "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }
        except Exception as e:
            return {
                "url": url,
                "status_code": 0,
                "response_ms": 0,
                "healthy": False,
                "error": str(e),
                "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }

    def _check_maintenance_reports(self) -> dict:
        """Find and summarize maintenance reports."""
        # Reports are at the root of the Bloodline folder
        reports = sorted(self.folder.glob("MAINTENANCE_REPORT_*.md"), reverse=True)

        if not reports:
            return {"found": False, "count": 0}

        latest = reports[0]
        latest_content = self._read_file_safe(str(latest.relative_to(self.folder)), max_chars=2000)

        # Extract key findings from the latest report
        issues = []
        for line in latest_content.split("\n"):
            lower = line.lower()
            if any(kw in lower for kw in ["error", "fail", "warning", "issue", "broken"]):
                issues.append(line.strip())

        return {
            "found": True,
            "count": len(reports),
            "latest_file": latest.name,
            "latest_date": latest.name.replace("MAINTENANCE_REPORT_", "").replace(".md", "").replace("_pipeline", ""),
            "issues_found": issues[:5],
        }

    def _build_action_items(self, findings: dict) -> list[str]:
        """Generate actionable items."""
        items = []

        # Site health
        health = findings.get("site_health", {})
        if not health.get("healthy"):
            items.append(f"SITE DOWN: {health.get('url')} returned {health.get('status_code', 'no response')}")
        elif health.get("response_ms", 0) > 3000:
            items.append(f"Slow response: {health['response_ms']}ms (target: <3000ms)")

        # Maintenance
        maint = findings.get("maintenance", {})
        if not maint.get("found"):
            items.append("No maintenance reports found. Run site-maintainer skill.")
        elif maint.get("issues_found"):
            items.append(f"{len(maint['issues_found'])} issues in latest report")

        return items
