"""
Multi-query expansion for improved retrieval coverage.

Generates variant phrasings of a query from different angles,
runs each against the searcher, and merges results via RRF.
This catches relevant chunks that a single query phrasing would miss.

Two modes:
  - LLM expansion: Uses Claude to generate smart reformulations
  - Rule-based expansion: Zero-cost synonym and structure transforms
"""

import re
import hashlib
from typing import Optional


def expand_query_rules(query: str) -> list[str]:
    """
    Generate query variants using rule-based transforms.
    Zero API cost. Always available.

    Strategies:
    1. Acronym expansion (RAG -> retrieval augmented generation)
    2. Synonym injection (build -> create, implement, develop)
    3. Perspective shift (how to X -> X best practices, X frameworks)
    """
    variants = [query]

    # Acronym expansions (common in this knowledge base)
    acronyms = {
        "RAG": "retrieval augmented generation",
        "LLM": "large language model",
        "API": "application programming interface",
        "SaaS": "software as a service",
        "PLG": "product led growth",
        "GTM": "go to market",
        "OKR": "objectives key results",
        "KPI": "key performance indicator",
        "MRR": "monthly recurring revenue",
        "ARR": "annual recurring revenue",
        "CI/CD": "continuous integration continuous deployment",
        "UX": "user experience",
        "UI": "user interface",
        "SEO": "search engine optimization",
        "CRM": "customer relationship management",
        "MVP": "minimum viable product",
        "ETL": "extract transform load",
        "ML": "machine learning",
        "NLP": "natural language processing",
        "DeFi": "decentralized finance",
        "IaC": "infrastructure as code",
    }

    expanded = query
    for abbr, full in acronyms.items():
        if abbr.lower() in query.lower():
            pattern = re.compile(re.escape(abbr), re.IGNORECASE)
            expanded = pattern.sub(full, expanded, count=1)
    if expanded != query:
        variants.append(expanded)

    # Perspective shift for "how to" questions
    how_to_match = re.match(r"(?:how\s+(?:to|do\s+I|can\s+I))\s+(.+)", query, re.IGNORECASE)
    if how_to_match:
        topic = how_to_match.group(1)
        variants.append(f"{topic} best practices")
        variants.append(f"{topic} frameworks strategies")

    # "What is" -> include related concepts
    what_is_match = re.match(r"(?:what\s+is|define|explain)\s+(.+)", query, re.IGNORECASE)
    if what_is_match:
        topic = what_is_match.group(1)
        variants.append(f"{topic} concepts principles")
        variants.append(f"{topic} overview fundamentals")

    return variants[:4]  # Cap at 4 variants


def expand_query_llm(query: str, num_variants: int = 3) -> list[str]:
    """
    Generate query variants using Claude.
    Adds ~1-2s latency per query. Much higher quality than rules.

    Returns the original query plus num_variants reformulations.
    """
    try:
        import anthropic
    except ImportError:
        return expand_query_rules(query)

    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{
                "role": "user",
                "content": (
                    f"Generate {num_variants} alternative search queries for: \"{query}\"\n\n"
                    "Each variant should approach the topic from a different angle "
                    "(synonyms, related concepts, broader/narrower framing).\n"
                    "Return ONLY the queries, one per line, no numbering or explanation."
                ),
            }],
        )
        text = response.content[0].text.strip()
        variants = [query] + [line.strip() for line in text.split("\n") if line.strip()]
        return variants[:num_variants + 1]
    except Exception:
        return expand_query_rules(query)


def search_with_expansion(
    searcher,
    query: str,
    top_k: int = 10,
    domain_filter: Optional[str] = None,
    file_filter: Optional[str] = None,
    use_llm: bool = False,
) -> list:
    """
    Run expanded search: generate query variants, search each, merge via RRF.

    Args:
        searcher: A Searcher instance
        query: The original query
        top_k: Number of results to return
        domain_filter: Optional domain filter
        file_filter: Optional file filter
        use_llm: Use LLM for expansion (slower, better quality)

    Returns:
        List of SearchResult sorted by merged relevance
    """
    from .searcher import _reciprocal_rank_fusion, SearchResult

    # Generate query variants
    if use_llm:
        variants = expand_query_llm(query)
    else:
        variants = expand_query_rules(query)

    if len(variants) <= 1:
        # No expansion possible, fall back to normal search
        return searcher.search(query, top_k=top_k, domain_filter=domain_filter,
                               file_filter=file_filter)

    # Search each variant
    all_ranked_lists = []
    all_weights = []
    chunk_cache = {}

    for i, variant in enumerate(variants):
        results = searcher.search(
            variant, top_k=top_k * 2,
            domain_filter=domain_filter, file_filter=file_filter,
        )
        ranked_ids = [r.chunk_id for r in results]
        all_ranked_lists.append(ranked_ids)
        # Original query gets highest weight, variants get diminishing weight
        weight = 1.0 if i == 0 else 0.7
        all_weights.append(weight)

        # Cache chunk data for building final results
        for r in results:
            if r.chunk_id not in chunk_cache:
                chunk_cache[r.chunk_id] = r

    # Merge via RRF
    fused = _reciprocal_rank_fusion(all_ranked_lists, all_weights)

    # Build final results
    results = []
    for chunk_id, score in fused[:top_k]:
        if chunk_id in chunk_cache:
            original = chunk_cache[chunk_id]
            results.append(SearchResult(
                chunk_id=original.chunk_id,
                text=original.text,
                source_file=original.source_file,
                header_path=original.header_path,
                domain=original.domain,
                tags=original.tags,
                score=score,
                bm25_rank=original.bm25_rank,
                semantic_rank=original.semantic_rank,
            ))

    return results
