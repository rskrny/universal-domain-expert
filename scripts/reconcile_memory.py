"""
Memory Reconciliation Script
Checks for conflicts between memory files and project state files.
Run at session start or before producing deliverables.

Usage:
    python scripts/reconcile_memory.py
    python scripts/reconcile_memory.py --project "The Flip Side"
    python scripts/reconcile_memory.py --all
"""

import os
import sys
import re
from datetime import datetime

MEMORY_DIR = r"C:\Users\rskrn\.claude\projects\C--Users-rskrn-Desktop-universal-domain-expert---Copy\memory"

# Project directories to check
PROJECTS = {
    "The Flip Side": r"C:\Users\rskrn\Desktop\The Flip Side",
    "Isaac Habitat Homeostasis": r"C:\Users\rskrn\Desktop\Isaac Habitat Homeostasis",
    "Universal Domain Expert": r"C:\Users\rskrn\Desktop\universal-domain-expert - Copy",
}

# Known state files per project (files that contain critical state)
STATE_FILES = {
    "The Flip Side": ["CLAUDE.md", "docs/TEAM_TRACKER.md", "docs/ACCOUNT_AUDIT_FORM.md"],
    "Isaac Habitat Homeostasis": ["site_config.py"],
    "Universal Domain Expert": ["state/HANDOFF.md"],
}


def load_memory_files():
    """Load all memory files and return as dict."""
    memories = {}
    if not os.path.exists(MEMORY_DIR):
        return memories
    for fname in os.listdir(MEMORY_DIR):
        if fname.endswith(".md") and fname != "MEMORY.md":
            path = os.path.join(MEMORY_DIR, fname)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            memories[fname] = content
    return memories


def check_keyword_conflicts(memory_content, project_file_content, keywords):
    """Check if keywords in memory contradict project files."""
    conflicts = []
    for keyword, memory_val, bad_pattern in keywords:
        if memory_val.lower() in memory_content.lower():
            if bad_pattern.lower() in project_file_content.lower():
                conflicts.append(f"Memory says '{memory_val}' but project file contains '{bad_pattern}'")
    return conflicts


def reconcile_project(project_name, project_dir):
    """Check a project's state files against memory."""
    print(f"\n{'='*60}")
    print(f"  Reconciling: {project_name}")
    print(f"  Directory: {project_dir}")
    print(f"{'='*60}")

    if not os.path.exists(project_dir):
        print(f"  WARNING: Project directory not found!")
        return []

    memories = load_memory_files()
    issues = []

    # Check state files
    state_files = STATE_FILES.get(project_name, [])
    for rel_path in state_files:
        full_path = os.path.join(project_dir, rel_path)
        if not os.path.exists(full_path):
            print(f"  SKIP: {rel_path} (not found)")
            continue

        with open(full_path, "r", encoding="utf-8") as f:
            file_content = f.read()

        # Check file modification time
        mtime = os.path.getmtime(full_path)
        mtime_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
        print(f"\n  Checking: {rel_path} (modified: {mtime_str})")

        # Cross-reference against all memory files
        for mem_name, mem_content in memories.items():
            # Extract key claims from memory
            # Look for patterns like "X declined", "X not joining", status changes
            declined_matches = re.findall(r'(\w+)\s+(?:declined|not joining|cancelled|left|quit)', mem_content, re.IGNORECASE)
            for person in declined_matches:
                # Check if project file still references them positively
                positive_patterns = [
                    f"{person} starts",
                    f"{person} hired",
                    f"onboard {person}",
                    f"{person} (editor",
                    f"{person} (new hire",
                    f"approved {person}",
                ]
                for pattern in positive_patterns:
                    if pattern.lower() in file_content.lower():
                        issue = f"CONFLICT in {rel_path}: Memory ({mem_name}) says '{person} declined' but file still says '{pattern}'"
                        issues.append(issue)
                        print(f"  ** CONFLICT: {issue}")

    if not issues:
        print(f"\n  All clear. No conflicts detected.")
    else:
        print(f"\n  FOUND {len(issues)} CONFLICT(S)!")

    return issues


def main():
    print("Memory Reconciliation Check")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Memory dir: {MEMORY_DIR}")

    if "--project" in sys.argv:
        idx = sys.argv.index("--project")
        name = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else ""
        if name in PROJECTS:
            issues = reconcile_project(name, PROJECTS[name])
        else:
            print(f"Unknown project: {name}")
            print(f"Available: {', '.join(PROJECTS.keys())}")
            sys.exit(1)
    else:
        all_issues = []
        for name, path in PROJECTS.items():
            issues = reconcile_project(name, path)
            all_issues.extend(issues)

        print(f"\n{'='*60}")
        print(f"  SUMMARY")
        print(f"{'='*60}")
        if all_issues:
            print(f"  {len(all_issues)} conflict(s) found across all projects.")
            print(f"  Fix these before producing any deliverables.")
            for i, issue in enumerate(all_issues, 1):
                print(f"  {i}. {issue}")
        else:
            print(f"  No conflicts. Memory and project files are in sync.")


if __name__ == "__main__":
    main()
