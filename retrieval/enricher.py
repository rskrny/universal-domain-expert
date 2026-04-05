"""
Contextual chunk enrichment.

Prepends each chunk with structural metadata so that search engines
(both BM25 and semantic) understand what a chunk is about even when
the raw text is ambiguous.

Based on Anthropic research showing 49% fewer retrieval failures
when chunks carry contextual prefixes.

Two modes:
1. Structural (default) -- uses headers, domain, file path, content type.
   Zero LLM calls. Fast. Good enough for most cases.
2. Neighbor-aware -- also incorporates surrounding chunk context.
   Still zero LLM calls but slightly slower.
"""

import logging
from typing import Optional

logger = logging.getLogger("retrieval.enricher")


def enrich_chunk(
    chunk: dict,
    neighbors: Optional[list[dict]] = None,
) -> str:
    """
    Generate enriched text for a chunk.

    The enriched text is used for indexing (BM25 tokenization and
    embedding generation) while the original text is preserved
    for display. This separation means enrichment improves retrieval
    accuracy without polluting the user-facing output.

    Args:
        chunk: Chunk dict with text, domain, header_path, source_file, etc.
        neighbors: Adjacent chunks from the same file (for broader context).

    Returns:
        Enriched text string with contextual prefix prepended.
    """
    parts = []

    # Domain context
    domain = chunk.get("domain")
    if domain:
        # Convert slug to readable: "business-consulting" -> "Business Consulting"
        readable_domain = domain.replace("-", " ").title()
        parts.append(f"Domain: {readable_domain}")

    # Source file context
    source = chunk.get("source_file", "")
    if source:
        name = _clean_filename(source)
        if name:
            parts.append(f"Topic: {name}")

    # Header hierarchy (the most informative structural signal)
    headers = chunk.get("header_path") or []
    if headers:
        parts.append(f"Section: {' > '.join(headers)}")

    # Content type (helps distinguish code, tables, prose)
    ctype = chunk.get("content_type", "prose")
    if ctype and ctype != "prose":
        type_labels = {
            "code": "Code example",
            "table": "Data table",
            "list": "List",
            "blockquote": "Quote",
        }
        label = type_labels.get(ctype, ctype)
        parts.append(f"Format: {label}")

    # Tags
    tags = chunk.get("tags") or []
    if tags:
        parts.append(f"Tags: {', '.join(tags[:5])}")

    # Neighbor context (optional, for broader understanding)
    if neighbors:
        neighbor_topics = _extract_neighbor_context(neighbors, chunk)
        if neighbor_topics:
            parts.append(f"Context: {neighbor_topics}")

    # Build the enriched text
    if not parts:
        return chunk.get("text", "")

    prefix = " | ".join(parts)
    original_text = chunk.get("text", "")
    return f"[{prefix}]\n{original_text}"


def enrich_chunks_batch(
    chunks: list[dict],
    use_neighbors: bool = True,
) -> list[str]:
    """
    Enrich a batch of chunks, optionally using neighbor context.

    Args:
        chunks: List of chunk dicts (must be ordered by source_file, chunk_index).
        use_neighbors: Whether to pass adjacent chunks as context.

    Returns:
        List of enriched text strings (same order as input chunks).
    """
    enriched = []

    # Group by source file for neighbor context
    file_groups: dict[str, list[int]] = {}
    for i, c in enumerate(chunks):
        sf = c.get("source_file", "")
        file_groups.setdefault(sf, []).append(i)

    # Build neighbor lookup
    neighbors_map: dict[int, list[dict]] = {}
    if use_neighbors:
        for sf, indices in file_groups.items():
            for pos, idx in enumerate(indices):
                nbrs = []
                if pos > 0:
                    nbrs.append(chunks[indices[pos - 1]])
                if pos < len(indices) - 1:
                    nbrs.append(chunks[indices[pos + 1]])
                neighbors_map[idx] = nbrs

    for i, chunk in enumerate(chunks):
        neighbors = neighbors_map.get(i) if use_neighbors else None
        enriched.append(enrich_chunk(chunk, neighbors))

    return enriched


def _clean_filename(source: str) -> str:
    """Extract a readable topic name from a file path."""
    # Get just the filename
    name = source.split("/")[-1]

    # Remove extension
    for ext in (".md", ".txt", ".py", ".js", ".ts", ".html"):
        if name.endswith(ext):
            name = name[:-len(ext)]
            break

    # Skip generic names
    generic = {"index", "readme", "template", "init", "__init__", "main", "utils"}
    if name.lower() in generic:
        return ""

    # Convert hyphens/underscores to spaces, title case
    name = name.replace("-", " ").replace("_", " ")

    # Truncate Reddit-style long names
    if len(name) > 60:
        name = name[:57] + "..."

    return name


def _extract_neighbor_context(neighbors: list[dict], current: dict) -> str:
    """
    Extract useful context from neighboring chunks.

    Pulls unique header information from adjacent chunks that differs
    from the current chunk's headers. This tells the search engine
    what broader section this chunk sits within.
    """
    current_headers = set(current.get("header_path") or [])
    neighbor_headers = set()

    for n in neighbors:
        for h in (n.get("header_path") or []):
            if h not in current_headers:
                neighbor_headers.add(h)

    if not neighbor_headers:
        return ""

    # Return at most 3 neighboring section names
    return ", ".join(sorted(neighbor_headers)[:3])
