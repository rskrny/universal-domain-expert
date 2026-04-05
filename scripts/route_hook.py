#!/usr/bin/env python3
"""
Route Hook — Hard-coded routing enforcement for Claude Code.

Called by the UserPromptSubmit hook on every prompt. Detects the @route
prefix, classifies the request by domain and tier, and injects a routing
decision into Claude's context via stdout JSON.

No @route prefix = complete silence (no stdout). Claude responds casually.
@route prefix = full routing decision injected. Claude MUST follow it.

Usage in .claude/settings.local.json:
  "command": "python scripts/route_hook.py"
"""

import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Domain Registry Parser
# ---------------------------------------------------------------------------

def parse_domain_registry(router_path: Path) -> dict:
    """
    Parse the ROUTER.md domain registry table into a dict of
    {domain_name: {"file": str, "keywords": list[str]}}.
    """
    if not router_path.exists():
        return {}

    text = router_path.read_text(encoding="utf-8")
    registry = {}

    # Match table rows: | Domain Name | `filename.md` | keyword1, keyword2, ... |
    pattern = re.compile(
        r"^\|\s*(.+?)\s*\|\s*`(.+?)`\s*\|\s*(.+?)\s*\|$",
        re.MULTILINE,
    )

    for match in pattern.finditer(text):
        domain_name = match.group(1).strip()
        file_name = match.group(2).strip()
        keywords_raw = match.group(3).strip()

        # Skip header row
        if domain_name in ("Domain", "--------", "-----"):
            continue
        if file_name.startswith("---"):
            continue

        # Parse keywords: split on comma, strip whitespace, lowercase
        keywords = [k.strip().lower() for k in keywords_raw.split(",") if k.strip()]

        registry[domain_name] = {
            "file": file_name,
            "keywords": keywords,
        }

    return registry


# ---------------------------------------------------------------------------
# Domain Classifier
# ---------------------------------------------------------------------------

# Extended keywords that aren't in ROUTER.md but should trigger domains.
# These handle common terms that the registry table misses.
EXTENDED_KEYWORDS = {
    "Software Development": [
        "rest", "graphql", "grpc", "api design", "endpoint", "microservice",
        "monolith", "orm", "sql", "nosql", "redis", "postgres", "mongodb",
        "git", "github", "refactor", "unit test", "integration test",
        "python", "javascript", "typescript", "rust", "go", "java", "c++",
        "database schema", "data model", "schema design", "migration",
        "backend", "frontend", "fullstack", "codebase", "repository",
    ],
    "Psychology & Persuasion": [
        "bias", "heuristic", "framing", "loss aversion", "prospect theory",
        "scarcity", "reciprocity", "commitment", "consistency", "authority",
        "liking", "consensus", "nudge", "behavioral",
    ],
    "SaaS Building": [
        "saas pricing", "freemium", "free trial", "mrr", "arr",
        "monthly recurring", "annual recurring", "churn rate",
        "subscription model", "usage-based", "per-seat", "tiered pricing",
    ],
    "AI & Machine Learning": [
        "chatgpt", "claude", "openai", "anthropic", "llama", "mistral",
        "rag", "embedding", "vector database", "pinecone", "weaviate",
        "hugging face", "model training", "gradient descent",
    ],
    "Data Analytics": [
        "tableau", "looker", "power bi", "pandas", "numpy",
        "data science", "correlation", "regression", "pivot table",
    ],
    "Cloud Infrastructure": [
        "lambda", "ecs", "fargate", "eks", "cloudfront",
        "route 53", "rds", "dynamodb", "sqs", "sns",
        "azure functions", "cloud run", "cloud functions",
    ],
    "Frontend Development": [
        "jsx", "tsx", "hook", "usestate", "useeffect", "redux",
        "zustand", "sass", "scss", "animation", "dom", "ssr", "ssg",
    ],
    "Social Distribution": [
        "linkedin api", "instagram api", "youtube api", "tiktok api",
        "twitter api", "facebook api", "graph api", "oauth posting",
        "content pipeline", "cross-platform posting", "social api",
        "ayrshare", "content distribution", "auto-post", "schedule post",
        "publish to", "post to", "distribute content",
    ],
}


def classify_domain(prompt: str, registry: dict) -> list:
    """
    Score each domain by keyword overlap with the prompt.
    Returns list of (domain_name, file, score, keywords_matched) sorted by score desc.

    Scoring:
    - Multi-word keyword match: 3.0 points (high specificity)
    - Single keyword match (exact word): 1.0 point
    - Single keyword substring match: 0.5 points
    - Domain name in prompt: 1.5 bonus (e.g. "psychology" in prompt boosts Psychology)
    - Keyword density bonus: extra 0.5 per match beyond the first (rewards multiple hits)
    """
    prompt_lower = prompt.lower()
    # Tokenize prompt into words for exact matching
    prompt_words = set(re.findall(r"[a-z0-9]+(?:[.-][a-z0-9]+)*", prompt_lower))

    scores = []
    for domain_name, info in registry.items():
        matched = []
        score = 0.0
        for kw in info["keywords"]:
            kw_lower = kw.lower()
            # Multi-word keywords: check substring (high specificity)
            if " " in kw_lower:
                if kw_lower in prompt_lower:
                    matched.append(kw)
                    score += 3.0
            else:
                # Single word: check exact word match
                if kw_lower in prompt_words:
                    matched.append(kw)
                    score += 1.0
                # Also check substring for compound words (e.g., "SaaS" in "saas-building")
                elif kw_lower in prompt_lower:
                    matched.append(kw)
                    score += 0.5

        # Keyword density bonus: reward domains with multiple matches
        if len(matched) > 1:
            score += (len(matched) - 1) * 0.5

        # Extended keywords: check supplementary keyword list
        ext_keywords = EXTENDED_KEYWORDS.get(domain_name, [])
        for ekw in ext_keywords:
            ekw_lower = ekw.lower()
            if " " in ekw_lower:
                if ekw_lower in prompt_lower:
                    matched.append(f"+{ekw}")
                    score += 2.5
            else:
                if ekw_lower in prompt_words:
                    matched.append(f"+{ekw}")
                    score += 0.8

        # Domain name bonus: if the domain name itself appears in the prompt
        # Split domain name into words and check each
        domain_words = [w.lower() for w in re.findall(r"[a-z]+", domain_name.lower())]
        for dw in domain_words:
            if len(dw) > 3 and dw in prompt_words:
                score += 1.5
                matched.append(f"[domain:{dw}]")

        if score > 0:
            scores.append((domain_name, info["file"], score, matched))

    scores.sort(key=lambda x: x[2], reverse=True)
    return scores


# ---------------------------------------------------------------------------
# Tier Classifier
# ---------------------------------------------------------------------------

TIER_1_PATTERNS = [
    r"\bwhat\s+is\b",
    r"\bwhat\s+are\b",
    r"\bdefine\b",
    r"\bexplain\b",
    r"\bhow\s+does\b",
    r"\bwhat\s+does\b",
    r"\bdifference\s+between\b",
    r"\bmeaning\s+of\b",
]

TIER_3_PATTERNS = [
    r"\bdesign\s+a\s+system\b",
    r"\bfull\s+strategy\b",
    r"\bcomprehensive\s+plan\b",
    r"\bmulti[- ]part\b",
    r"\bend[- ]to[- ]end\b",
    r"\barchitecture\s+for\b",
    r"\bbuild\s+a\s+complete\b",
    r"\bcreate\s+a\s+full\b",
]

TIER_2_SIGNALS = [
    "help me", "create", "build", "write", "analyze", "recommend",
    "draft", "review", "compare", "evaluate", "design", "plan",
    "how should", "how do i", "how can i", "what should",
]


def classify_tier(prompt: str) -> int:
    """Classify prompt complexity into Tier 1, 2, or 3."""
    prompt_lower = prompt.lower()
    word_count = len(prompt.split())

    # Check Tier 1 patterns (short, factual)
    for pattern in TIER_1_PATTERNS:
        if re.search(pattern, prompt_lower) and word_count < 20:
            return 1

    # Check Tier 3 patterns (complex, multi-part)
    for pattern in TIER_3_PATTERNS:
        if re.search(pattern, prompt_lower):
            return 3

    # Long prompts with multiple sentences tend toward Tier 3
    sentence_count = len(re.split(r"[.!?]+", prompt.strip()))
    if sentence_count >= 4 and word_count > 50:
        return 3

    # Multiple deliverables listed (commas or "and" connecting nouns) signal Tier 3
    # Look for patterns like "X, Y, Z, and W" or "include X, Y, and Z"
    list_pattern = re.findall(r",\s*(?:and\s+)?[a-z]", prompt_lower)
    if len(list_pattern) >= 3 and word_count > 30:
        return 3

    # "Complete" or "comprehensive" + action verb -> Tier 3
    if re.search(r"\bcomplete\b.*\b(strategy|plan|system|design|architecture)\b", prompt_lower):
        return 3

    # Check Tier 2 signals
    for signal in TIER_2_SIGNALS:
        if signal in prompt_lower:
            return 2

    # Default: if it has domain keywords, Tier 2. Otherwise Tier 1.
    if word_count > 15:
        return 2

    return 1


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def log_routing(log_path: Path, entry: dict):
    """Append a routing decision to the JSONL log."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Main Hook
# ---------------------------------------------------------------------------

def main():
    start_time = time.monotonic()

    # Read hook input from stdin
    try:
        raw = sys.stdin.read()
        hook_input = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, Exception):
        # If we can't parse input, exit silently
        sys.exit(0)

    prompt = hook_input.get("prompt", "")
    if not prompt.strip():
        sys.exit(0)

    # Determine project root (cwd from hook context, or fallback)
    cwd = hook_input.get("cwd", "")
    if cwd:
        project_root = Path(cwd)
    else:
        project_root = Path(__file__).parent.parent

    router_path = project_root / "prompts" / "ROUTER.md"
    log_path = project_root / "state" / "routing_log.jsonl"
    summaries_path = project_root / "state" / "domain_summaries.json"

    # Load compressed domain summaries (for Tier 1 inline injection)
    domain_summaries = {}
    if summaries_path.exists():
        try:
            domain_summaries = json.loads(summaries_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Check for @route prefix (case-insensitive)
    route_match = re.match(r"^@route\s+", prompt, re.IGNORECASE)

    if not route_match:
        # No @route prefix: log as unrouted, complete silence (no stdout)
        log_routing(log_path, {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "routed": False,
            "prompt_preview": prompt[:100],
            "elapsed_ms": round((time.monotonic() - start_time) * 1000),
        })
        sys.exit(0)

    # --- @route prefix detected: run classification ---

    # Extract the actual query (after @route)
    query = prompt[route_match.end():].strip()

    # Parse domain registry
    registry = parse_domain_registry(router_path)
    if not registry:
        # Registry not found or empty, output a warning
        print(f"ROUTING WARNING: Could not parse domain registry at {router_path}")
        sys.exit(0)

    # Classify domain
    domain_scores = classify_domain(query, registry)
    tier = classify_tier(query)

    # Build routing decision
    if domain_scores:
        primary = domain_scores[0]
        primary_domain = primary[0]
        primary_file = primary[1]
        primary_score = primary[2]
        primary_keywords = primary[3]

        # Check for multi-domain (second domain within 60% of primary score)
        supporting = []
        if len(domain_scores) > 1:
            second = domain_scores[1]
            ratio = primary_score / second[2] if second[2] > 0 else 999
            if ratio < 1.6:
                supporting.append({"domain": second[0], "file": second[1]})

        # Calculate confidence
        if len(domain_scores) > 1 and domain_scores[1][2] > 0:
            confidence = round(primary_score / domain_scores[1][2], 2)
        else:
            confidence = 9.99  # Only one domain matched

        confidence = min(confidence, 9.99)

        # Build the routing decision text
        lines = [
            "ROUTING DECISION (auto-classified by route_hook.py):",
            f"  Domain:     {primary_domain}",
            f"  File:       prompts/domains/{primary_file}",
        ]
        if supporting:
            sup_str = ", ".join(f"{s['domain']} ({s['file']})" for s in supporting)
            lines.append(f"  Supporting: {sup_str}")
        else:
            lines.append("  Supporting: none")

        lines.extend([
            f"  Tier:       {tier}",
            f"  Confidence: {confidence}",
            f"  Matched:    {', '.join(primary_keywords)}",
        ])

        if tier == 1:
            # Tier 1: Inject compressed summary inline (no file read needed)
            domain_key = primary_file.replace(".md", "")
            compressed = domain_summaries.get(domain_key, {}).get("compressed", "")
            if compressed:
                lines.extend([
                    "",
                    "COMPRESSED DOMAIN CONTEXT (use this directly, no file read needed):",
                    compressed,
                    "",
                    "INSTRUCTIONS (mandatory):",
                    "  1. Use the compressed domain context above to inform your answer",
                    "  2. Only read the full domain file if the compressed context is insufficient",
                    "  3. Verify writing style (no semicolons, no em dashes, no AI slop)",
                ])
            else:
                lines.extend([
                    "",
                    "INSTRUCTIONS (mandatory):",
                    f"  1. Read prompts/domains/{primary_file} and apply its frameworks",
                    "  2. Apply domain frameworks to the response",
                    "  3. Verify writing style (no semicolons, no em dashes, no AI slop)",
                ])
        else:
            # Tier 2+: Load full domain file + retrieval search
            lines.extend([
                "",
                "INSTRUCTIONS (mandatory):",
                f"  1. Read prompts/domains/{primary_file} and apply its frameworks",
                f'  2. Run: python -m retrieval context "{query[:80]}" --budget 2000',
                "  3. Apply domain frameworks to structure the response",
                "  4. Verify writing style (no semicolons, no em dashes, no AI slop)",
            ])

        routing_text = "\n".join(lines)

    else:
        # No domain matched
        primary_domain = "unmatched"
        primary_file = None
        confidence = 0
        primary_keywords = []
        routing_text = (
            "ROUTING DECISION (auto-classified by route_hook.py):\n"
            "  Domain:     UNMATCHED (no domain keywords found)\n"
            "  Tier:       " + str(tier) + "\n"
            "\n"
            "  No domain file matched. Either create a new domain file using\n"
            "  prompts/TEMPLATE.md, or respond with general knowledge.\n"
            "  Consider if this request needs a new domain."
        )

    # Log the routing decision
    elapsed_ms = round((time.monotonic() - start_time) * 1000)
    log_routing(log_path, {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "routed": True,
        "domain": primary_domain,
        "file": primary_file,
        "tier": tier,
        "confidence": confidence,
        "keywords_matched": primary_keywords,
        "prompt_preview": query[:100],
        "elapsed_ms": elapsed_ms,
    })

    # Output the routing decision as plain text (injected into Claude's context)
    print(routing_text)
    sys.exit(0)


if __name__ == "__main__":
    main()
