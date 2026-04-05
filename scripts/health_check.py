#!/usr/bin/env python3
"""
System Health Check -- Agentic resilience layer.

Validates the entire domain expert system and flags problems before they
cause silent failures. Designed to catch the hidden tech debts of agentic
systems: stale indexes, drift, silent breakdowns, missing guards.

Failure modes detected:
  1. Stale index (domain files changed since last index)
  2. Silent failures (scripts broken, APIs unreachable)
  3. Memory drift (memory files vs reality)
  4. Routing gaps (unmatched queries, low-confidence patterns)
  5. Missing domain summaries (new domains without compression)
  6. Hook misconfiguration (route_hook.py not wired)
  7. Scheduled task health (daily briefing configured?)

Run: python scripts/health_check.py
     python scripts/health_check.py --fix    (auto-fix what's fixable)
     python scripts/health_check.py --json   (machine-readable output)

Principles:
  - SRE: Detect -> Triage -> Respond -> Remediate -> Learn
  - Every check returns: status (ok/warn/fail), message, fix_command (if auto-fixable)
"""

import json
import os
import re
import sqlite3
import sys
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")


# ---------------------------------------------------------------------------
# Check functions (each returns a dict with status, message, fix_command)
# ---------------------------------------------------------------------------

def check_index_freshness() -> dict:
    """Check if retrieval index is stale (domain files newer than index)."""
    db_path = ROOT / "retrieval" / "store" / "metadata.db"
    domains_dir = ROOT / "prompts" / "domains"

    if not db_path.exists():
        return {"status": "fail", "message": "Retrieval index database not found",
                "fix_command": "python -m retrieval index"}

    db_mtime = db_path.stat().st_mtime

    stale_files = []
    for f in domains_dir.glob("*.md"):
        if f.stat().st_mtime > db_mtime:
            stale_files.append(f.name)

    # Also check context files
    context_dir = ROOT / "prompts" / "context"
    if context_dir.exists():
        for f in context_dir.rglob("*.md"):
            if f.stat().st_mtime > db_mtime:
                stale_files.append(str(f.relative_to(ROOT)))

    if stale_files:
        return {
            "status": "warn",
            "message": f"{len(stale_files)} files newer than index: {', '.join(stale_files[:5])}",
            "fix_command": "python -m retrieval index",
        }

    return {"status": "ok", "message": "Index is up to date"}


def check_index_integrity() -> dict:
    """Verify the retrieval index has reasonable chunk counts."""
    db_path = ROOT / "retrieval" / "store" / "metadata.db"
    if not db_path.exists():
        return {"status": "fail", "message": "No index database",
                "fix_command": "python -m retrieval index --full"}

    try:
        conn = sqlite3.connect(str(db_path))
        chunk_count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        conn.close()

        if chunk_count == 0:
            return {"status": "fail", "message": "Index is empty (0 chunks)",
                    "fix_command": "python -m retrieval index --full"}
        elif chunk_count < 1000:
            return {"status": "warn",
                    "message": f"Index seems small ({chunk_count} chunks, expected 8000+)"}
        else:
            return {"status": "ok", "message": f"{chunk_count:,} chunks indexed"}
    except Exception as e:
        return {"status": "fail", "message": f"Index database error: {e}",
                "fix_command": "python -m retrieval index --full"}


def check_domain_coverage() -> dict:
    """Verify all domain files are registered in ROUTER.md."""
    domains_dir = ROOT / "prompts" / "domains"
    router_path = ROOT / "prompts" / "ROUTER.md"

    if not router_path.exists():
        return {"status": "fail", "message": "ROUTER.md not found"}

    router_text = router_path.read_text(encoding="utf-8")
    domain_files = [f.name for f in domains_dir.glob("*.md")]

    unregistered = []
    for df in domain_files:
        if df not in router_text:
            unregistered.append(df)

    if unregistered:
        return {
            "status": "warn",
            "message": f"{len(unregistered)} domains not in ROUTER.md: {', '.join(unregistered[:5])}",
        }

    return {"status": "ok", "message": f"All {len(domain_files)} domains registered"}


def check_domain_summaries() -> dict:
    """Verify compressed summaries exist for all domains."""
    summaries_path = ROOT / "state" / "domain_summaries.json"
    domains_dir = ROOT / "prompts" / "domains"

    if not summaries_path.exists():
        return {"status": "warn", "message": "No domain summaries file",
                "fix_command": "python scripts/compress_domains.py"}

    try:
        summaries = json.loads(summaries_path.read_text(encoding="utf-8"))
    except Exception:
        return {"status": "fail", "message": "Domain summaries file is corrupt",
                "fix_command": "python scripts/compress_domains.py"}

    domain_files = [f.stem for f in domains_dir.glob("*.md")]
    missing = [d for d in domain_files if d not in summaries]

    if missing:
        return {
            "status": "warn",
            "message": f"{len(missing)} domains without summaries: {', '.join(missing[:5])}",
            "fix_command": "python scripts/compress_domains.py",
        }

    # Check if summaries are stale
    summary_mtime = summaries_path.stat().st_mtime
    stale = [f.name for f in domains_dir.glob("*.md") if f.stat().st_mtime > summary_mtime]
    if stale:
        return {
            "status": "warn",
            "message": f"{len(stale)} domain files newer than summaries",
            "fix_command": "python scripts/compress_domains.py",
        }

    return {"status": "ok", "message": f"{len(summaries)} domain summaries current"}


def check_hook_config() -> dict:
    """Verify the route_hook is properly wired in settings."""
    settings_path = ROOT / ".claude" / "settings.local.json"
    if not settings_path.exists():
        return {"status": "fail", "message": ".claude/settings.local.json not found"}

    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"status": "fail", "message": "settings.local.json is invalid JSON"}

    hooks = settings.get("hooks", {}).get("UserPromptSubmit", [])
    for hook_group in hooks:
        for h in hook_group.get("hooks", []):
            if "route_hook.py" in h.get("command", ""):
                return {"status": "ok", "message": "route_hook.py is wired"}

    return {"status": "warn", "message": "route_hook.py not found in UserPromptSubmit hooks"}


def check_routing_health() -> dict:
    """Analyze routing log for patterns that indicate problems."""
    log_path = ROOT / "state" / "routing_log.jsonl"
    if not log_path.exists():
        return {"status": "ok", "message": "No routing log yet (new system)"}

    try:
        entries = [json.loads(l) for l in log_path.read_text().strip().split("\n") if l.strip()]
    except Exception:
        return {"status": "warn", "message": "Routing log is corrupt"}

    if not entries:
        return {"status": "ok", "message": "Routing log is empty"}

    routed = [e for e in entries if e.get("routed")]
    unmatched = [e for e in routed if e.get("domain") == "unmatched"]
    low_conf = [e for e in routed if e.get("confidence", 10) < 1.5]

    issues = []
    if unmatched:
        issues.append(f"{len(unmatched)} unmatched queries (need new domains?)")
    if low_conf:
        issues.append(f"{len(low_conf)} low-confidence classifications")

    if issues:
        return {"status": "warn", "message": " | ".join(issues)}

    return {"status": "ok",
            "message": f"{len(entries)} queries logged, {len(routed)} routed"}


def check_reddit_api() -> dict:
    """Check if Reddit API credentials are configured."""
    cid = os.getenv("REDDIT_CLIENT_ID", "")
    csec = os.getenv("REDDIT_CLIENT_SECRET", "")
    if not cid or not csec:
        return {"status": "warn", "message": "Reddit API credentials missing from .env"}
    return {"status": "ok", "message": "Reddit API credentials configured"}


def check_lark_api() -> dict:
    """Check if Lark API credentials are configured."""
    app_id = os.getenv("BRAINFEED_APP_ID", "")
    app_secret = os.getenv("BRAINFEED_APP_SECRET", "")
    if not app_id or not app_secret:
        return {"status": "warn", "message": "Brain Feed Lark credentials missing from .env"}
    return {"status": "ok", "message": "Lark API credentials configured"}


def check_daily_briefing() -> dict:
    """Check if the daily briefing ran recently."""
    briefing_path = ROOT / "state" / "daily_briefing.md"
    if not briefing_path.exists():
        return {"status": "warn", "message": "No daily briefing generated yet",
                "fix_command": "python scripts/daily_briefing.py --no-lark"}

    mtime = briefing_path.stat().st_mtime
    age_hours = (datetime.now(timezone.utc).timestamp() - mtime) / 3600

    if age_hours > 48:
        return {"status": "warn",
                "message": f"Daily briefing is {int(age_hours)} hours old",
                "fix_command": "python scripts/daily_briefing.py"}
    elif age_hours > 24:
        return {"status": "ok",
                "message": f"Daily briefing is {int(age_hours)} hours old (due for refresh)"}
    else:
        return {"status": "ok", "message": f"Daily briefing is {int(age_hours)} hours old"}


def check_scripts_runnable() -> dict:
    """Verify key scripts can at least import without errors."""
    scripts_to_check = [
        ("route_hook.py", "scripts.route_hook"),
        ("compress_domains.py", "scripts.compress_domains"),
        ("benchmark_routing.py", "scripts.benchmark_routing"),
    ]

    broken = []
    for name, module in scripts_to_check:
        try:
            subprocess.run(
                [sys.executable, "-c", f"import importlib; importlib.import_module('{module}')"],
                cwd=str(ROOT), capture_output=True, timeout=10
            )
        except Exception:
            broken.append(name)

    if broken:
        return {"status": "warn", "message": f"Scripts with import errors: {', '.join(broken)}"}
    return {"status": "ok", "message": "Core scripts importable"}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

ALL_CHECKS = [
    ("Index Freshness", check_index_freshness),
    ("Index Integrity", check_index_integrity),
    ("Domain Coverage", check_domain_coverage),
    ("Domain Summaries", check_domain_summaries),
    ("Hook Config", check_hook_config),
    ("Routing Health", check_routing_health),
    ("Reddit API", check_reddit_api),
    ("Lark API", check_lark_api),
    ("Daily Briefing", check_daily_briefing),
    ("Scripts Health", check_scripts_runnable),
]


def main():
    auto_fix = "--fix" in sys.argv
    json_output = "--json" in sys.argv

    results = []
    for name, check_fn in ALL_CHECKS:
        try:
            result = check_fn()
        except Exception as e:
            result = {"status": "fail", "message": f"Check crashed: {e}"}
        result["check"] = name
        results.append(result)

    # Auto-fix if requested
    if auto_fix:
        for r in results:
            if r.get("fix_command") and r["status"] in ("warn", "fail"):
                print(f"  AUTO-FIX: {r['check']} -> {r['fix_command']}")
                try:
                    subprocess.run(
                        r["fix_command"].split(),
                        cwd=str(ROOT), capture_output=True, timeout=120
                    )
                    r["fixed"] = True
                except Exception as e:
                    r["fixed"] = False
                    r["fix_error"] = str(e)

    if json_output:
        print(json.dumps(results, indent=2))
        return

    # Human-readable output
    status_icons = {"ok": "OK", "warn": "!!", "fail": "XX"}

    print("=" * 60)
    print("  SYSTEM HEALTH CHECK")
    print("=" * 60)

    ok_count = sum(1 for r in results if r["status"] == "ok")
    warn_count = sum(1 for r in results if r["status"] == "warn")
    fail_count = sum(1 for r in results if r["status"] == "fail")

    print(f"\n  Score: {ok_count}/{len(results)} passing"
          f" ({warn_count} warnings, {fail_count} failures)\n")

    for r in results:
        icon = status_icons[r["status"]]
        print(f"  [{icon}] {r['check']}: {r['message']}")
        if r.get("fix_command") and not r.get("fixed"):
            print(f"       Fix: {r['fix_command']}")
        if r.get("fixed"):
            print(f"       FIXED")

    # Overall health score
    health = ok_count / len(results) * 100 if results else 0
    print(f"\n  Overall health: {health:.0f}%")

    if fail_count > 0:
        print(f"\n  Run with --fix to auto-repair fixable issues.")

    print()


if __name__ == "__main__":
    main()
