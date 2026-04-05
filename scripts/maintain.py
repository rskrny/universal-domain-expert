"""
System maintenance script.
Run after creating or modifying domain files, context chunks, or any knowledge base content.

Usage:
    python scripts/maintain.py           # Incremental index + regenerate knowledge graph
    python scripts/maintain.py --full    # Full rebuild from scratch
    python scripts/maintain.py --stats   # Just show current stats
"""

import subprocess
import sys
import os

def run(cmd, label):
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.returncode != 0 and result.stderr:
        print(f"  ERROR: {result.stderr}")
    return result.returncode == 0

def main():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(project_root)

    if "--stats" in sys.argv:
        run("python -m retrieval stats", "Current Index Statistics")
        return

    full = "--full" in sys.argv
    index_flag = " --full" if full else ""

    print("\nUniversal Domain Expert System -- Maintenance")
    print("=" * 60)

    # Count domain files
    domain_dir = os.path.join("prompts", "domains")
    domains = [f for f in os.listdir(domain_dir) if f.endswith(".md")]
    print(f"\n  Domain files found: {len(domains)}")
    for d in sorted(domains):
        print(f"    - {d}")

    # Count context files
    context_dir = os.path.join("prompts", "context")
    context_count = 0
    for root, dirs, files in os.walk(context_dir):
        context_count += sum(1 for f in files if f.endswith(".md"))
    print(f"  Context files found: {context_count}")

    # Step 1: Index
    mode = "Full rebuild" if full else "Incremental update"
    success = run(f"python -m retrieval index{index_flag}", f"Step 1: Index ({mode})")
    if not success:
        print("\n  Index failed. Check retrieval system setup.")
        print("  Run: python scripts/setup.py --lite")
        return

    # Step 2: Knowledge Graph
    run("python -m retrieval viz", "Step 2: Regenerate Knowledge Graph")

    # Step 3: Stats
    run("python -m retrieval stats", "Step 3: Verify")

    print("\n" + "=" * 60)
    print("  Maintenance complete.")
    print("=" * 60)

if __name__ == "__main__":
    main()
