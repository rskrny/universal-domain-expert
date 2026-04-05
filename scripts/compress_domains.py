#!/usr/bin/env python3
"""
Domain Compressor -- Generate compressed summaries of domain files.

For each domain in prompts/domains/, extracts the core frameworks, expertise
areas, and decision rules into a ~500 token summary. These summaries are
stored in state/domain_summaries.json and injected by route_hook.py for
Tier 1 queries, avoiding the need to load a full 15-80KB domain file.

First principles:
  - Shannon's Channel Capacity: maximize useful_tokens / total_tokens
  - Information Density: extract only decision-relevant content per token
  - Minimum Viable Context: load the minimum needed to answer well

Run: python scripts/compress_domains.py
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOMAINS_DIR = ROOT / "prompts" / "domains"
OUTPUT_PATH = ROOT / "state" / "domain_summaries.json"


def extract_summary(filepath: Path) -> dict:
    """Extract a compressed summary from a domain file."""
    text = filepath.read_text(encoding="utf-8", errors="replace")

    summary = {
        "file": filepath.name,
        "role": "",
        "expertise": [],
        "frameworks": [],
        "quality_rules": [],
    }

    # Extract role (first blockquote line with "Role:")
    role_match = re.search(r">\s*\*\*Role:\*\*\s*(.+?)(?:\n|$)", text)
    if role_match:
        summary["role"] = role_match.group(1).strip()[:200]

    # Extract core expertise areas (numbered list after "Core Expertise Areas")
    expertise_section = re.search(
        r"Core Expertise Areas\s*\n((?:\s*\d+\..*\n?)+)", text
    )
    if expertise_section:
        items = re.findall(r"\d+\.\s*\*\*(.+?)\*\*", expertise_section.group(1))
        summary["expertise"] = items[:8]

    # Extract framework names and one-liners
    framework_matches = re.finditer(
        r"###\s*Framework\s*\d+[:\s]*(.+?)(?:\n|$)(.*?)(?=###|\Z)",
        text, re.DOTALL
    )
    for fm in framework_matches:
        name = fm.group(1).strip()
        body = fm.group(2).strip()
        # Extract the "What:" line if it exists
        what_match = re.search(r"\*\*What:\*\*\s*(.+?)(?:\n|$)", body)
        what_line = what_match.group(1).strip()[:150] if what_match else ""
        summary["frameworks"].append({
            "name": name,
            "what": what_line,
        })

    # Limit to top 6 frameworks
    summary["frameworks"] = summary["frameworks"][:6]

    # Extract key quality rules (from "Must include" / "Must avoid" patterns)
    must_rules = re.findall(r"Must (?:include|avoid)[:\s]*(.+?)(?:\n|$)", text)
    summary["quality_rules"] = [r.strip()[:100] for r in must_rules[:4]]

    return summary


def format_compressed(summary: dict) -> str:
    """Format a summary into a compact text block for context injection."""
    lines = []
    lines.append(f"DOMAIN: {summary['file'].replace('.md', '').replace('-', ' ').title()}")

    if summary["role"]:
        lines.append(f"ROLE: {summary['role']}")

    if summary["expertise"]:
        lines.append("EXPERTISE: " + " | ".join(summary["expertise"]))

    if summary["frameworks"]:
        lines.append("FRAMEWORKS:")
        for fw in summary["frameworks"]:
            if fw["what"]:
                lines.append(f"  - {fw['name']}: {fw['what']}")
            else:
                lines.append(f"  - {fw['name']}")

    if summary["quality_rules"]:
        lines.append("QUALITY: " + " | ".join(summary["quality_rules"][:3]))

    return "\n".join(lines)


def main():
    if not DOMAINS_DIR.exists():
        print(f"Domain directory not found: {DOMAINS_DIR}")
        sys.exit(1)

    summaries = {}
    domain_files = sorted(DOMAINS_DIR.glob("*.md"))

    print(f"Compressing {len(domain_files)} domain files...")

    for filepath in domain_files:
        domain_key = filepath.stem  # e.g., "sales", "software-dev"
        summary = extract_summary(filepath)
        compressed = format_compressed(summary)
        summaries[domain_key] = {
            "summary": summary,
            "compressed": compressed,
            "tokens_approx": len(compressed.split()),
        }

    # Save to JSON
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(summaries, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    # Report
    total_files = len(summaries)
    avg_tokens = sum(s["tokens_approx"] for s in summaries.values()) / total_files if total_files else 0
    print(f"Compressed {total_files} domains")
    print(f"Average compressed size: ~{int(avg_tokens)} tokens per domain")
    print(f"Saved to {OUTPUT_PATH}")

    # Show a sample
    if summaries:
        sample_key = "sales" if "sales" in summaries else list(summaries.keys())[0]
        print(f"\n--- Sample: {sample_key} ---")
        print(summaries[sample_key]["compressed"])


if __name__ == "__main__":
    main()
