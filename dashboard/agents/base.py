"""
Base agent for project monitoring.

All agents are read-only. They scan project folders and report findings.
They never modify project files.
"""

import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("dashboard.agents")


class BaseAgent:
    """Base class for autonomous project agents."""

    def __init__(self, project_key: str, project_config: dict, db=None):
        self.project_key = project_key
        self.config = project_config
        self.folder = Path(project_config["path"])
        self.db = db

    def run(self) -> dict:
        """Execute the agent. Returns findings dict."""
        findings = {
            "timestamp": time.time(),
            "project": self.project_key,
            "agent": self.__class__.__name__,
        }

        try:
            # Base scan: file stats
            findings["folder_status"] = self._scan_folder_status()

            # Subclass-specific checks
            agent_findings = self._check()
            findings.update(agent_findings)
            findings["status"] = "success"

        except Exception as e:
            findings["status"] = "error"
            findings["error"] = str(e)
            logger.error("Agent %s failed for %s: %s", self.__class__.__name__, self.project_key, e)

        # Log to database
        if self.db:
            self.db.log_agent_run(
                project=self.project_key,
                agent_type=self.__class__.__name__,
                status=findings.get("status", "unknown"),
                findings=findings,
            )

        return findings

    def _check(self) -> dict:
        """Override in subclasses for project-specific checks."""
        return {}

    def _scan_folder_status(self) -> dict:
        """Get basic folder statistics. Read-only."""
        if not self.folder.exists():
            return {"exists": False}

        # Count files by extension (top-level scan, skip excluded dirs)
        file_counts = {}
        total_size = 0
        latest_modified = 0
        latest_file = ""

        skip_dirs = {"node_modules", ".git", "__pycache__", ".next", "venv", ".venv", ".gstack"}

        for root, dirs, files in os.walk(self.folder):
            # Prune excluded directories
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            for fname in files:
                fpath = Path(root) / fname
                try:
                    stat = fpath.stat()
                    ext = fpath.suffix.lower() or "(no ext)"
                    file_counts[ext] = file_counts.get(ext, 0) + 1
                    total_size += stat.st_size
                    if stat.st_mtime > latest_modified:
                        latest_modified = stat.st_mtime
                        latest_file = str(fpath.relative_to(self.folder))
                except OSError:
                    continue

        total_files = sum(file_counts.values())

        return {
            "exists": True,
            "total_files": total_files,
            "total_size_mb": round(total_size / (1024 * 1024), 1),
            "file_types": dict(sorted(file_counts.items(), key=lambda x: x[1], reverse=True)[:8]),
            "latest_modified": latest_modified,
            "latest_modified_readable": datetime.fromtimestamp(latest_modified).strftime("%Y-%m-%d %H:%M") if latest_modified else "unknown",
            "latest_file": latest_file,
        }

    def _read_file_safe(self, relative_path: str, max_chars: int = 4000) -> str:
        """Read a file from the project folder. Returns empty string if not found."""
        path = self.folder / relative_path
        if path.exists() and path.is_file():
            try:
                return path.read_text(encoding="utf-8", errors="replace")[:max_chars]
            except Exception:
                return ""
        return ""
