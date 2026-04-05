"""
Self-Improvement Pipeline.

Takes the output of the knowledge pipeline (extracted claims, domain enrichments,
gap analysis) and produces actionable improvements to the system:

1. DOMAIN GAPS    -> Create new domain files for uncovered topics
2. SKILL GAPS     -> Propose new Claude Code skills based on emerging patterns
3. PROJECT INTEL  -> Surface Reddit knowledge relevant to active projects
4. PERSONAL GROWTH -> Extract actionable insights for Ryan's development areas

This is the "so what" layer. The pipeline collects and extracts knowledge.
This script answers: "now what do we DO with it?"

Usage:
    python scripts/improve.py report          # Full improvement report
    python scripts/improve.py gaps            # Show domain and skill gaps
    python scripts/improve.py projects        # Project-relevant intelligence
    python scripts/improve.py actions         # Generate action items
"""

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env", override=True)

if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

DOMAINS_DIR = ROOT / "prompts" / "domains"
CONTEXT_DIR = ROOT / "prompts" / "context" / "by-domain"
STATE_DIR = ROOT / "state"


# ── Load Pipeline State ─────────────────────────────────────────────────────

def load_extractions() -> dict:
    """Load extraction tracking state."""
    path = STATE_DIR / "reddit_extractions.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def load_enrichment_proposals() -> dict:
    """Load enrichment proposals."""
    path = STATE_DIR / "enrichment_proposals.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def load_enrichment_state() -> dict:
    """Load enrichment tracking."""
    path = STATE_DIR / "domain_enrichments.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def get_existing_domains() -> set:
    """Get set of all existing domain file names (without .md)."""
    return {f.stem for f in DOMAINS_DIR.glob("*.md")}


def get_existing_skills() -> list:
    """Get list of existing Claude Code skills."""
    skills_dir = ROOT / ".claude" / "skills"
    if not skills_dir.exists():
        return []
    return [d.name for d in skills_dir.iterdir() if d.is_dir()]


# ── Gap Analysis ────────────────────────────────────────────────────────────

def analyze_domain_gaps() -> dict:
    """
    Find topics that appear in extracted claims but have no domain file.
    Also find domains with very few practitioner insights (underfed).
    """
    extractions = load_extractions()
    proposals = load_enrichment_proposals()
    existing = get_existing_domains()

    # Collect all domain tags from extractions
    domain_mentions = {}
    for pid, data in extractions.items():
        domain = data.get("domain", "")
        if domain and domain != "general":
            domain_mentions[domain] = domain_mentions.get(domain, 0) + 1

    # Find mentioned domains with no file
    gaps = {}
    for domain, count in domain_mentions.items():
        if domain not in existing:
            gaps[domain] = {
                "type": "missing_domain_file",
                "mentions": count,
                "action": f"Create prompts/domains/{domain}.md using TEMPLATE.md",
            }

    # Find domains mentioned in enrichment gap analysis
    for domain, prop in proposals.items():
        for gap in prop.get("domain_gaps", []):
            gap_key = gap[:50].lower().replace(" ", "-")
            if gap_key not in gaps:
                gaps[gap_key] = {
                    "type": "enrichment_gap",
                    "source_domain": domain,
                    "description": gap,
                    "action": "Consider creating a new domain or adding a section to existing domain",
                }

    # Find domains with zero practitioner insights (could benefit from pipeline)
    enrichment_state = load_enrichment_state()
    underfed = []
    for domain_file in DOMAINS_DIR.glob("*.md"):
        domain = domain_file.stem
        if domain not in enrichment_state:
            # Check if there are any reddit chunks for this domain
            context_dir = CONTEXT_DIR / domain
            reddit_chunks = list(context_dir.glob("reddit-*.md")) if context_dir.exists() else []
            if not reddit_chunks:
                underfed.append(domain)

    return {
        "missing_domains": gaps,
        "underfed_domains": underfed[:20],  # Top 20
    }


def analyze_skill_gaps() -> list:
    """
    Look at extracted claims to identify patterns that suggest new skills
    or tools should be created.
    """
    existing_skills = get_existing_skills()
    extractions = load_extractions()

    # Count claim patterns that suggest tooling opportunities
    patterns = {}
    for pid, data in extractions.items():
        if data.get("status") != "extracted":
            continue
        domain = data.get("domain", "")
        pv = data.get("practical_value", "")
        if pv in ("high", "medium"):
            patterns[domain] = patterns.get(domain, 0) + 1

    # Suggest skills based on high-concentration domains
    suggestions = []

    # Check for common skill patterns from claim content
    claim_topics = []
    for domain_dir in CONTEXT_DIR.iterdir():
        if not domain_dir.is_dir():
            continue
        for f in domain_dir.glob("reddit-*.md"):
            text = f.read_text(encoding="utf-8", errors="replace")
            if "## Extracted Claims" in text:
                claim_topics.append({
                    "domain": domain_dir.name,
                    "file": f.name,
                    "text": text[:2000],
                })

    # Pattern: Multiple claims about the same tool or technique
    tool_mentions = {}
    import re
    for ct in claim_topics:
        # Look for tool/framework names
        tools = re.findall(r'\b(ComfyUI|n8n|Runway|Kling|Minimax|MCP|CLAUDE\.md|Cursor|Vercel|Railway|Cloudflare Workers)\b', ct["text"], re.IGNORECASE)
        for tool in tools:
            tool_lower = tool.lower()
            tool_mentions[tool_lower] = tool_mentions.get(tool_lower, 0) + 1

    for tool, count in sorted(tool_mentions.items(), key=lambda x: -x[1]):
        if count >= 2:
            suggestions.append({
                "type": "tool_skill",
                "tool": tool,
                "mentions": count,
                "suggestion": f"Practitioners mention '{tool}' repeatedly. Consider creating a skill or workflow for it.",
            })

    return suggestions


# ── Project Intelligence ────────────────────────────────────────────────────

# Map project names to relevant domain keywords
PROJECT_DOMAIN_MAP = {
    "Goldie Group": ["email", "triage", "automation", "ai", "classification", "msp", "consulting"],
    "Bloodline Charters": ["next.js", "booking", "fishing", "seo", "web"],
    "The Flip Side": ["video", "podcast", "content", "china", "media", "editing"],
    "Sullivan Auctioneers": ["auction", "real estate", "seo", "tax deed", "website"],
    "ShopMyRoom": ["video", "automation", "pipeline", "short-form", "ai video"],
    "AI Course": ["course", "teaching", "ai", "beginner", "curriculum", "youtube"],
    "Domain Expert System": ["rag", "retrieval", "context", "chunking", "embedding", "mcp", "claude code"],
    "Pepper Crypto": ["crypto", "usdt", "rmb", "exchange", "wallet"],
    "GES Business": ["consulting", "freelance", "client", "proposal", "pricing"],
    "Personal Finance": ["fire", "investing", "portfolio", "tax", "expat", "international"],
    "Personal Health": ["nootropics", "biohacking", "fitness", "sleep", "cognition"],
}


def find_project_intel() -> dict:
    """
    Scan extracted claims for content relevant to specific active projects.
    Returns {project: [relevant claims]}.
    """
    intel = {}

    for domain_dir in CONTEXT_DIR.iterdir():
        if not domain_dir.is_dir():
            continue
        for f in domain_dir.glob("reddit-*.md"):
            text = f.read_text(encoding="utf-8", errors="replace").lower()

            for project, keywords in PROJECT_DOMAIN_MAP.items():
                matches = sum(1 for kw in keywords if kw in text)
                if matches >= 2:  # At least 2 keyword matches
                    # Extract the claim lines
                    claims = []
                    for line in f.read_text(encoding="utf-8", errors="replace").split("\n"):
                        if line.startswith("**Claim"):
                            claims.append(line.replace("**Claim ", "").replace(":**", ":").strip())

                    if claims:
                        if project not in intel:
                            intel[project] = []
                        intel[project].append({
                            "source": f.name,
                            "domain": domain_dir.name,
                            "claims": claims,
                            "relevance": matches,
                        })

    # Sort each project's intel by relevance
    for project in intel:
        intel[project].sort(key=lambda x: x["relevance"], reverse=True)

    return intel


# ── Action Item Generation ──────────────────────────────────────────────────

def generate_actions() -> list:
    """
    Synthesize all pipeline outputs into concrete action items.
    Sorted by priority.
    """
    actions = []
    gaps = analyze_domain_gaps()
    skill_gaps = analyze_skill_gaps()
    intel = find_project_intel()
    enrichment = load_enrichment_state()
    extractions = load_extractions()

    # Action: Missing domains
    for domain, info in gaps.get("missing_domains", {}).items():
        actions.append({
            "priority": "high" if info.get("mentions", 0) >= 3 else "medium",
            "category": "domain_creation",
            "action": f"Create domain file: {domain}.md",
            "detail": info.get("action", ""),
            "source": f"{info.get('mentions', 0)} Reddit claims tagged to this domain with no file",
        })

    # Action: Tool skills
    for sg in skill_gaps[:5]:
        actions.append({
            "priority": "medium",
            "category": "skill_creation",
            "action": f"Consider creating skill for: {sg['tool']}",
            "detail": sg["suggestion"],
            "source": f"Mentioned in {sg['mentions']} extracted claims",
        })

    # Action: Project intelligence worth acting on
    for project, items in intel.items():
        if items:
            top = items[0]
            actions.append({
                "priority": "medium",
                "category": "project_intel",
                "action": f"Review new intelligence for: {project}",
                "detail": f"{len(items)} relevant Reddit claims found. Top: {top['claims'][0][:80] if top['claims'] else 'N/A'}",
                "source": f"From r/{top.get('domain', 'unknown')}",
            })

    # Action: Run enrichment on domains with claims but no enrichment yet
    extracted_domains = set()
    for pid, data in extractions.items():
        if data.get("status") == "extracted":
            extracted_domains.add(data.get("domain", ""))
    enriched_domains = set(enrichment.keys())
    unenriched = extracted_domains - enriched_domains - {"", "general"}
    if unenriched:
        actions.append({
            "priority": "high",
            "category": "enrichment",
            "action": f"Run enrichment for {len(unenriched)} domains with unprocessed claims",
            "detail": f"Domains: {', '.join(sorted(unenriched))}",
            "source": "Claims extracted but not yet compared against domain files",
        })

    # Action: Reindex if there are new context files
    extraction_count = sum(1 for d in extractions.values() if d.get("status") == "extracted")
    if extraction_count > 0:
        actions.append({
            "priority": "low",
            "category": "maintenance",
            "action": "Reindex after pipeline run",
            "detail": "python -m retrieval index",
            "source": f"{extraction_count} new chunks to index",
        })

    # Sort by priority
    priority_order = {"high": 0, "medium": 1, "low": 2}
    actions.sort(key=lambda a: priority_order.get(a["priority"], 3))

    return actions


# ── Commands ────────────────────────────────────────────────────────────────

def cmd_report():
    """Full improvement report."""
    print("=" * 60)
    print("  SYSTEM IMPROVEMENT REPORT")
    print(f"  Generated: {time.strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # Pipeline stats
    extractions = load_extractions()
    extracted = sum(1 for d in extractions.values() if d.get("status") == "extracted")
    skipped = sum(1 for d in extractions.values() if d.get("status") == "skipped")
    print(f"\n  Pipeline: {extracted} posts extracted, {skipped} skipped")

    enrichment = load_enrichment_state()
    enriched_count = sum(d.get("additions_count", 0) for d in enrichment.values())
    print(f"  Enrichment: {len(enrichment)} domains enriched, {enriched_count} total additions")

    # Gaps
    print("\n--- Domain Gaps ---")
    gaps = analyze_domain_gaps()
    if gaps["missing_domains"]:
        for domain, info in gaps["missing_domains"].items():
            print(f"  MISSING: {domain} ({info.get('mentions', 0)} mentions)")
    else:
        print("  No missing domains detected.")

    if gaps["underfed_domains"]:
        print(f"\n  Underfed domains (no Reddit knowledge yet): {len(gaps['underfed_domains'])}")
        for d in gaps["underfed_domains"][:10]:
            print(f"    - {d}")

    # Skills
    print("\n--- Skill Opportunities ---")
    skills = analyze_skill_gaps()
    if skills:
        for sg in skills[:5]:
            print(f"  {sg['tool']}: {sg['mentions']} mentions. {sg['suggestion']}")
    else:
        print("  No skill patterns detected yet. Run more extractions.")

    # Project intel
    print("\n--- Project Intelligence ---")
    intel = find_project_intel()
    if intel:
        for project, items in intel.items():
            print(f"\n  {project}: {len(items)} relevant claims")
            for item in items[:2]:
                for claim in item["claims"][:1]:
                    print(f"    > {claim[:80]}")
    else:
        print("  No project-relevant claims found yet.")

    # Actions
    print("\n--- Recommended Actions ---")
    actions = generate_actions()
    for i, action in enumerate(actions[:10], 1):
        print(f"\n  [{action['priority'].upper()}] {i}. {action['action']}")
        print(f"     {action['detail']}")


def cmd_gaps():
    """Show gaps only."""
    gaps = analyze_domain_gaps()
    skills = analyze_skill_gaps()

    print("Domain Gaps:")
    for domain, info in gaps.get("missing_domains", {}).items():
        print(f"  {domain}: {info}")

    print(f"\nUnderfed domains: {len(gaps.get('underfed_domains', []))}")
    for d in gaps.get("underfed_domains", [])[:15]:
        print(f"  - {d}")

    print(f"\nSkill opportunities:")
    for sg in skills[:5]:
        print(f"  {sg['tool']}: {sg['suggestion']}")


def cmd_projects():
    """Project intelligence only."""
    intel = find_project_intel()
    if not intel:
        print("No project-relevant claims found. Run the extraction pipeline first.")
        return

    for project, items in intel.items():
        print(f"\n{'='*50}")
        print(f"  {project}: {len(items)} relevant Reddit claims")
        print(f"{'='*50}")
        for item in items:
            print(f"\n  Source: {item['source']} (domain: {item['domain']})")
            for claim in item["claims"]:
                print(f"    > {claim[:100]}")


def cmd_actions():
    """Action items only."""
    actions = generate_actions()
    if not actions:
        print("No actions to take. Run the pipeline first.")
        return

    print("Action Items (sorted by priority):")
    for i, action in enumerate(actions, 1):
        pri = action["priority"].upper()
        cat = action["category"]
        print(f"\n  [{pri}] {i}. [{cat}] {action['action']}")
        print(f"     {action['detail']}")
        print(f"     Source: {action['source']}")


# ── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "report"

    if cmd == "report":
        cmd_report()
    elif cmd == "gaps":
        cmd_gaps()
    elif cmd == "projects":
        cmd_projects()
    elif cmd == "actions":
        cmd_actions()
    else:
        print(f"Unknown command: {cmd}")
        print("Usage: python scripts/improve.py [report|gaps|projects|actions]")
