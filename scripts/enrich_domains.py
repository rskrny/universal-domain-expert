"""
Domain Enrichment Pipeline.

Reads extracted Reddit claims for each domain, compares against the existing
domain file, and proposes additions. Closes the loop between ingested knowledge
and the domain expert actually learning from it.

Three modes:
  - report:  Show what claims exist per domain and what's novel
  - propose: Generate proposed additions to domain files (dry run)
  - apply:   Write the additions into domain files

Usage:
    python scripts/enrich_domains.py report                  # Overview
    python scripts/enrich_domains.py propose                 # Show proposals
    python scripts/enrich_domains.py propose --domain vibecoding  # Single domain
    python scripts/enrich_domains.py apply                   # Write changes
    python scripts/enrich_domains.py apply --domain vibecoding
"""

import json
import os
import re
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


# ── Gather Claims Per Domain ────────────────────────────────────────────────

def gather_domain_claims(domain: str = None) -> dict:
    """
    Scan context/by-domain/ for Reddit-sourced chunks that have extracted claims.
    Returns {domain: [list of claim dicts with metadata]}.
    """
    results = {}

    dirs_to_scan = []
    if domain:
        d = CONTEXT_DIR / domain
        if d.exists():
            dirs_to_scan.append((domain, d))
        else:
            print(f"No context directory for domain: {domain}")
            return {}
    else:
        for d in CONTEXT_DIR.iterdir():
            if d.is_dir():
                dirs_to_scan.append((d.name, d))

    for domain_name, domain_dir in dirs_to_scan:
        claims = []
        for f in domain_dir.glob("reddit-*.md"):
            text = f.read_text(encoding="utf-8", errors="replace")

            # Only process files with extracted claims
            if "## Extracted Claims" not in text:
                continue

            # Parse claims from the markdown
            claim_section = text.split("## Extracted Claims")[1].split("##")[0]
            claim_blocks = re.findall(
                r'\*\*Claim \d+:\*\*\s*(.+?)(?=\*\*Claim|\Z)',
                claim_section,
                re.DOTALL,
            )

            for block in claim_blocks:
                lines = block.strip().split("\n")
                claim_text = lines[0].strip() if lines else ""

                evidence = ""
                confidence = 0.0
                details = ""
                for line in lines[1:]:
                    line = line.strip("- ").strip()
                    if line.startswith("Evidence:"):
                        evidence = line.replace("Evidence:", "").strip()
                        # Extract confidence number
                        conf_match = re.search(r'confidence:\s*([\d.]+)', evidence)
                        if conf_match:
                            confidence = float(conf_match.group(1))
                    elif line.startswith("Details:"):
                        details = line.replace("Details:", "").strip()

                if claim_text:
                    # Extract engagement and practical value from file header
                    eng_match = re.search(r'Engagement:\s*([\d.]+)', text)
                    pv_match = re.search(r'Practical Value:\s*(\w+)', text)
                    novelty_match = re.search(r'\*\*Novelty:\*\*\s*(.+)', text)

                    claims.append({
                        "claim": claim_text,
                        "evidence": evidence,
                        "confidence": confidence,
                        "details": details,
                        "engagement": float(eng_match.group(1)) if eng_match else 0.0,
                        "practical_value": pv_match.group(1) if pv_match else "unknown",
                        "novelty": novelty_match.group(1).strip() if novelty_match else "",
                        "source_file": f.name,
                    })

        if claims:
            # Sort by confidence * engagement (best claims first)
            claims.sort(key=lambda c: c["confidence"] * c["engagement"], reverse=True)
            results[domain_name] = claims

    return results


# ── Domain File Analysis ────────────────────────────────────────────────────

def read_domain_file(domain: str) -> str:
    """Read a domain expertise file. Returns empty string if not found."""
    filepath = DOMAINS_DIR / f"{domain}.md"
    if filepath.exists():
        return filepath.read_text(encoding="utf-8", errors="replace")
    return ""


def find_insertion_point(domain_text: str) -> int:
    """
    Find the best place to insert new content in a domain file.
    Looks for the Anti-Patterns section (insert before it) or
    the end of Core Frameworks section.
    """
    # Try to insert before Anti-Patterns
    anti_idx = domain_text.find("## Anti-Patterns")
    if anti_idx > 0:
        return anti_idx

    # Try before Decision Frameworks
    dec_idx = domain_text.find("## Decision Frameworks")
    if dec_idx > 0:
        return dec_idx

    # Try before Quality Standards
    qual_idx = domain_text.find("## Quality Standards")
    if qual_idx > 0:
        return qual_idx

    # Fallback: end of file
    return len(domain_text)


# ── Claude API Enrichment ───────��───────────────────────────────────────────

ENRICHMENT_PROMPT = """You are a domain expertise curator. You maintain domain expertise files that guide an AI system.

CURRENT DOMAIN FILE (first 3000 chars):
{domain_excerpt}

REDDIT-SOURCED CLAIMS for this domain (sorted by quality):
{claims_text}

---

Your task: determine which claims should be added to the domain file as new knowledge.

For each claim, decide:
1. SKIP: Already covered by existing frameworks. Nothing new.
2. EVIDENCE: Supports an existing framework with new real-world data. Worth noting.
3. NEW_FRAMEWORK: Introduces a pattern or approach not in the file. Should be added.
4. COUNTER: Contradicts conventional wisdom in the file. Important to capture.

Return valid JSON (no markdown fences):

{{
  "additions": [
    {{
      "type": "NEW_FRAMEWORK|EVIDENCE|COUNTER",
      "title": "Short name for the insight",
      "content": "2-4 sentences describing the insight in the style of the domain file. Write it ready to paste into the frameworks section. Include the source claim for attribution.",
      "source_claim": "The original claim text",
      "confidence": 0.0-1.0,
      "priority": "high|medium|low"
    }}
  ],
  "skipped": [
    {{
      "claim": "The claim text",
      "reason": "Why it was skipped (already covered, too vague, etc.)"
    }}
  ],
  "domain_gaps": ["Any topics the claims touch that the domain file doesn't cover at all"]
}}

Rules:
- Be selective. 1-3 additions maximum. Only add genuine new knowledge.
- Write additions in the same voice and style as the existing domain file.
- A claim from a Reddit post with 50 upvotes is not gospel. Note the evidence quality.
- NEW_FRAMEWORK additions should follow the existing format: What, When to use, How to apply.
- COUNTER additions are the most valuable. If practitioners are finding that textbook advice fails, that's critical.
- If no claims deserve addition, return an empty additions array. That's fine."""


def generate_proposals(domain: str, claims: list, api_key: str) -> dict:
    """
    Use Claude to compare claims against domain file and propose additions.
    """
    import anthropic

    domain_text = read_domain_file(domain)
    if not domain_text:
        return {"additions": [], "skipped": [], "domain_gaps": [],
                "_error": f"No domain file found: {domain}.md"}

    # Format claims for the prompt
    claims_text = ""
    for i, c in enumerate(claims[:10], 1):  # Cap at 10 claims
        claims_text += f"{i}. [{c['practical_value']}] {c['claim']}\n"
        claims_text += f"   Evidence: {c['evidence']}\n"
        if c['details']:
            claims_text += f"   Details: {c['details']}\n"
        if c['novelty']:
            claims_text += f"   Novelty: {c['novelty']}\n"
        claims_text += f"   Engagement: {c['engagement']}\n\n"

    prompt = ENRICHMENT_PROMPT.format(
        domain_excerpt=domain_text[:3000],
        claims_text=claims_text,
    )

    client = anthropic.Anthropic(api_key=api_key)

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        result = json.loads(raw)
        result["_tokens_used"] = response.usage.input_tokens + response.usage.output_tokens
        return result

    except json.JSONDecodeError as e:
        return {"additions": [], "_error": f"JSON parse: {e}", "_raw": raw[:500] if 'raw' in dir() else ""}
    except Exception as e:
        return {"additions": [], "_error": str(e)}


# ── Apply Additions ─────────────────────────────────────────────────────────

def apply_additions(domain: str, additions: list) -> bool:
    """
    Write approved additions into the domain file.

    Adds a "## Practitioner Insights (Reddit-Sourced)" section if it doesn't
    exist, or appends to it.
    """
    filepath = DOMAINS_DIR / f"{domain}.md"
    if not filepath.exists():
        print(f"  Domain file not found: {filepath}")
        return False

    text = filepath.read_text(encoding="utf-8")
    section_header = "## Practitioner Insights (Reddit-Sourced)"

    if section_header in text:
        # Append to existing section
        insert_idx = text.index(section_header) + len(section_header)
        # Find end of section (next ## or end of file)
        next_section = text.find("\n## ", insert_idx + 1)
        if next_section == -1:
            next_section = len(text)
        insert_at = next_section
    else:
        # Create section before Anti-Patterns or at insertion point
        insert_at = find_insertion_point(text)
        # Add section header
        header_block = f"\n{section_header}\n\n"
        header_block += "> These insights come from Reddit practitioner communities. They represent\n"
        header_block += "> emerging patterns and real-world experiences that may not appear in textbooks.\n"
        header_block += "> Confidence levels reflect evidence quality. Updated automatically by the\n"
        header_block += "> knowledge enrichment pipeline.\n\n"
        text = text[:insert_at] + header_block + text[insert_at:]
        insert_at = insert_at + len(header_block)

    # Format additions
    addition_text = ""
    for a in additions:
        atype = a.get("type", "NEW_FRAMEWORK")
        title = a.get("title", "Untitled")
        content = a.get("content", "")
        confidence = a.get("confidence", 0.5)
        source = a.get("source_claim", "")

        type_label = {"NEW_FRAMEWORK": "Pattern", "EVIDENCE": "Evidence", "COUNTER": "Counter-Signal"}.get(atype, atype)

        addition_text += f"### [{type_label}] {title}\n"
        addition_text += f"**Confidence:** {confidence} | **Source:** Reddit practitioner community\n"
        addition_text += f"{content}\n"
        if source:
            addition_text += f"*Original claim: \"{source[:150]}\"*\n"
        addition_text += f"*Added: {time.strftime('%Y-%m-%d')}*\n\n"

    # Insert
    text = text[:insert_at] + addition_text + text[insert_at:]
    filepath.write_text(text, encoding="utf-8")
    return True


# ── State Tracking ──────���───────────────────────────────────────────────────

def load_enrichment_state() -> dict:
    state_path = STATE_DIR / "domain_enrichments.json"
    if state_path.exists():
        return json.loads(state_path.read_text(encoding="utf-8"))
    return {}


def save_enrichment_state(state: dict):
    state_path = STATE_DIR / "domain_enrichments.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")


# ── Commands ────────────────────────────────────���───────────────────────────

def cmd_report(domain: str = None):
    """Show overview of claims per domain."""
    claims_by_domain = gather_domain_claims(domain)

    if not claims_by_domain:
        print("No extracted claims found. Run extract_claims.py first.")
        return

    print("Domain Enrichment Report")
    print("=" * 60)

    total_claims = 0
    for d, claims in sorted(claims_by_domain.items()):
        domain_file = DOMAINS_DIR / f"{d}.md"
        has_file = domain_file.exists()
        high_conf = sum(1 for c in claims if c["confidence"] >= 0.7)
        total_claims += len(claims)

        status = "OK" if has_file else "NO FILE"
        print(f"\n  {d} [{status}]")
        print(f"    Claims: {len(claims)} ({high_conf} high-confidence)")
        for c in claims[:3]:
            conf = c["confidence"]
            eng = c["engagement"]
            print(f"    [{conf:.1f}/{eng:.2f}] {c['claim'][:70]}")
        if len(claims) > 3:
            print(f"    ... +{len(claims) - 3} more")

    print(f"\nTotal: {total_claims} claims across {len(claims_by_domain)} domains")


def cmd_propose(domain: str = None):
    """Generate and display proposals without applying them."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set")
        return

    claims_by_domain = gather_domain_claims(domain)
    if not claims_by_domain:
        print("No extracted claims found.")
        return

    print("Generating Enrichment Proposals")
    print("=" * 60)

    all_proposals = {}
    total_tokens = 0

    for d, claims in sorted(claims_by_domain.items()):
        if not (DOMAINS_DIR / f"{d}.md").exists():
            print(f"\n  {d}: SKIPPED (no domain file)")
            continue

        print(f"\n  Analyzing {d} ({len(claims)} claims)...")
        proposals = generate_proposals(d, claims, api_key)
        total_tokens += proposals.get("_tokens_used", 0)

        if proposals.get("_error"):
            print(f"    ERROR: {proposals['_error']}")
            continue

        additions = proposals.get("additions", [])
        skipped = proposals.get("skipped", [])
        gaps = proposals.get("domain_gaps", [])

        all_proposals[d] = proposals

        if additions:
            print(f"    PROPOSED ADDITIONS ({len(additions)}):")
            for a in additions:
                print(f"      [{a['type']}] {a['title']} (confidence: {a.get('confidence', '?')}, priority: {a.get('priority', '?')})")
                print(f"        {a['content'][:120]}...")
        else:
            print(f"    No additions proposed. {len(skipped)} claims skipped.")

        if gaps:
            print(f"    DOMAIN GAPS: {', '.join(gaps)}")

        time.sleep(0.3)

    # Save proposals for apply step
    proposals_path = STATE_DIR / "enrichment_proposals.json"
    proposals_path.write_text(json.dumps(all_proposals, indent=2), encoding="utf-8")

    print(f"\nTotal tokens used: {total_tokens:,}")
    print(f"Proposals saved to: {proposals_path}")
    print("Run 'python scripts/enrich_domains.py apply' to write changes.")


def cmd_apply(domain: str = None):
    """Apply saved proposals to domain files."""
    proposals_path = STATE_DIR / "enrichment_proposals.json"
    if not proposals_path.exists():
        print("No proposals found. Run 'propose' first.")
        return

    all_proposals = json.loads(proposals_path.read_text(encoding="utf-8"))
    enrichment_state = load_enrichment_state()

    applied = 0
    for d, proposals in all_proposals.items():
        if domain and d != domain:
            continue

        additions = proposals.get("additions", [])
        if not additions:
            continue

        # Filter to high/medium priority
        worthy = [a for a in additions if a.get("priority") in ("high", "medium")]
        if not worthy:
            print(f"  {d}: No high/medium priority additions. Skipping.")
            continue

        print(f"  Applying {len(worthy)} additions to {d}.md...")
        success = apply_additions(d, worthy)
        if success:
            applied += len(worthy)
            enrichment_state[d] = {
                "last_enriched": time.strftime("%Y-%m-%d %H:%M"),
                "additions_count": enrichment_state.get(d, {}).get("additions_count", 0) + len(worthy),
            }

    save_enrichment_state(enrichment_state)
    print(f"\nApplied {applied} additions.")

    if applied > 0:
        print("Run 'python -m retrieval index' to update the search index.")


# ── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Enrich domain files from Reddit claims")
    parser.add_argument("command", choices=["report", "propose", "apply"],
                        help="report=overview, propose=generate proposals, apply=write changes")
    parser.add_argument("--domain", type=str, help="Target a single domain")
    args = parser.parse_args()

    if args.command == "report":
        cmd_report(args.domain)
    elif args.command == "propose":
        cmd_propose(args.domain)
    elif args.command == "apply":
        cmd_apply(args.domain)
