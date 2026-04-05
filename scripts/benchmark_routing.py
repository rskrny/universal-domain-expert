#!/usr/bin/env python3
"""
Benchmark Routing — Compare routed vs unrouted query patterns.

Reads state/routing_log.jsonl and produces a report showing:
- Routed vs unrouted counts and ratios
- Domain distribution (which domains get routed most)
- Tier distribution
- Confidence scores (how decisive the classifier is)
- Timing (hook execution speed)

Usage:
    python scripts/benchmark_routing.py
    python scripts/benchmark_routing.py --json     # Machine-readable output
    python scripts/benchmark_routing.py --clear     # Reset the log
"""

import json
import sys
from collections import Counter
from pathlib import Path


def load_log(log_path: Path) -> list:
    """Load routing log entries from JSONL file."""
    if not log_path.exists():
        return []
    entries = []
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries


def generate_report(entries: list) -> dict:
    """Generate statistics from routing log entries."""
    if not entries:
        return {"error": "No routing data found. Use @route prefix to start logging."}

    total = len(entries)
    routed = [e for e in entries if e.get("routed")]
    unrouted = [e for e in entries if not e.get("routed")]

    # Domain distribution
    domain_counts = Counter(e.get("domain", "unknown") for e in routed)

    # Tier distribution
    tier_counts = Counter(e.get("tier", 0) for e in routed)

    # Confidence stats
    confidences = [e.get("confidence", 0) for e in routed if e.get("confidence")]
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0
    low_confidence = [e for e in routed if e.get("confidence", 10) < 1.5]

    # Timing stats
    timings = [e.get("elapsed_ms", 0) for e in entries if e.get("elapsed_ms")]
    avg_timing = sum(timings) / len(timings) if timings else 0
    max_timing = max(timings) if timings else 0

    return {
        "total_queries": total,
        "routed": len(routed),
        "unrouted": len(unrouted),
        "route_ratio": round(len(routed) / total * 100, 1) if total > 0 else 0,
        "domains": dict(domain_counts.most_common()),
        "tiers": {f"Tier {k}": v for k, v in sorted(tier_counts.items())},
        "confidence": {
            "average": round(avg_confidence, 2),
            "low_confidence_count": len(low_confidence),
            "low_confidence_queries": [
                e.get("prompt_preview", "")[:60] for e in low_confidence
            ],
        },
        "timing_ms": {
            "average": round(avg_timing, 1),
            "max": max_timing,
        },
    }


def print_report(report: dict):
    """Print a human-readable report."""
    if "error" in report:
        print(report["error"])
        return

    print("=" * 60)
    print("  ROUTING BENCHMARK REPORT")
    print("=" * 60)

    print(f"\n  Total queries:  {report['total_queries']}")
    print(f"  Routed (@route): {report['routed']}")
    print(f"  Unrouted:        {report['unrouted']}")
    print(f"  Route ratio:     {report['route_ratio']}%")

    print(f"\n  --- Domain Distribution ---")
    for domain, count in report["domains"].items():
        bar = "#" * min(count, 30)
        print(f"  {domain:<30} {count:>3}  {bar}")

    print(f"\n  --- Tier Distribution ---")
    for tier, count in report["tiers"].items():
        print(f"  {tier}: {count}")

    print(f"\n  --- Classification Confidence ---")
    print(f"  Average confidence: {report['confidence']['average']}")
    print(f"  Low confidence (<1.5): {report['confidence']['low_confidence_count']}")
    if report["confidence"]["low_confidence_queries"]:
        print("  Ambiguous queries:")
        for q in report["confidence"]["low_confidence_queries"][:5]:
            print(f"    - {q}")

    print(f"\n  --- Hook Performance ---")
    print(f"  Average: {report['timing_ms']['average']}ms")
    print(f"  Max:     {report['timing_ms']['max']}ms")
    print()


def main():
    project_root = Path(__file__).parent.parent
    log_path = project_root / "state" / "routing_log.jsonl"

    if "--clear" in sys.argv:
        if log_path.exists():
            log_path.unlink()
            print("Routing log cleared.")
        else:
            print("No routing log to clear.")
        return

    entries = load_log(log_path)
    report = generate_report(entries)

    if "--json" in sys.argv:
        print(json.dumps(report, indent=2))
    else:
        print_report(report)


if __name__ == "__main__":
    main()
