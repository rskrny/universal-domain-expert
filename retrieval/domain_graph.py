"""
Domain Link Graph -- cross-domain relationship extraction and traversal.

Parses "Adjacent domains" sections from domain files to build a graph
of domain relationships. Used to expand search across domain boundaries
when a query touches concepts that span multiple domains.

Two modes:
  - build: Scan all domain files, extract links, store in SQLite
  - expand: Given a domain, return its first-hop neighbors for search expansion
"""

import re
from pathlib import Path
from typing import Optional

from .store import Store
from .config import RetrievalConfig


def _extract_domain_links(filepath: Path) -> list[tuple[str, str, str]]:
    """
    Parse a domain file and extract adjacent domain references.

    Returns list of (source_domain, target_domain, relationship_context).
    """
    text = filepath.read_text(encoding="utf-8")

    # Extract source domain from filename
    source = filepath.stem  # e.g., "business-consulting"

    # Find the "Adjacent domains" section
    pattern = re.compile(
        r"\*\*Adjacent domains.*?\*\*.*?\n((?:- .+\n?)+)",
        re.IGNORECASE,
    )
    match = pattern.search(text)
    if not match:
        return []

    links_block = match.group(1)
    links = []

    # Parse each bullet line: "- `domain.md` -- context about the relationship"
    line_pattern = re.compile(
        r"-\s+`([a-z0-9_-]+)\.md`\s*(?:--|—|--)\s*(.+)",
        re.IGNORECASE,
    )

    for line in links_block.split("\n"):
        line_match = line_pattern.match(line.strip())
        if line_match:
            target = line_match.group(1)
            context = line_match.group(2).strip()
            links.append((source, target, context))

    return links


def build_domain_graph(config: RetrievalConfig, verbose: bool = False) -> dict:
    """
    Scan all domain files and build the domain link graph.

    Returns stats about the graph.
    """
    store = Store(config.db_path, config.store_dir)

    # Ensure domain_links table exists
    store.conn.execute("""
        CREATE TABLE IF NOT EXISTS domain_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_domain TEXT NOT NULL,
            target_domain TEXT NOT NULL,
            context TEXT,
            UNIQUE(source_domain, target_domain)
        )
    """)
    store.conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_domain_links_source ON domain_links(source_domain)"
    )
    store.conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_domain_links_target ON domain_links(target_domain)"
    )
    store.conn.commit()

    # Clear existing links
    store.conn.execute("DELETE FROM domain_links")
    store.conn.commit()

    # Scan all domain files
    domains_dir = config.knowledge_root / "prompts" / "domains"
    if not domains_dir.exists():
        store.close()
        return {"domains_scanned": 0, "links_found": 0}

    all_links = []
    domains_scanned = 0

    for filepath in sorted(domains_dir.glob("*.md")):
        domains_scanned += 1
        links = _extract_domain_links(filepath)
        all_links.extend(links)
        if verbose and links:
            print(f"  {filepath.stem}: {len(links)} links")

    # Insert links
    for source, target, context in all_links:
        try:
            store.conn.execute(
                "INSERT OR IGNORE INTO domain_links (source_domain, target_domain, context) "
                "VALUES (?, ?, ?)",
                (source, target, context),
            )
        except Exception:
            pass

    store.conn.commit()

    stats = {
        "domains_scanned": domains_scanned,
        "links_found": len(all_links),
        "unique_sources": len({s for s, _, _ in all_links}),
        "unique_targets": len({t for _, t, _ in all_links}),
    }

    if verbose:
        print(f"\nDomain graph built:")
        print(f"  Domains scanned: {stats['domains_scanned']}")
        print(f"  Links found: {stats['links_found']}")
        print(f"  Source domains: {stats['unique_sources']}")
        print(f"  Target domains: {stats['unique_targets']}")

    store.close()
    return stats


def get_adjacent_domains(
    config: RetrievalConfig,
    domain: str,
    hops: int = 1,
) -> list[str]:
    """
    Get domains adjacent to the given domain (first-hop neighbors).

    Args:
        config: Retrieval config
        domain: The domain to expand from
        hops: Number of hops (1 = direct neighbors, 2 = neighbors of neighbors)

    Returns:
        List of adjacent domain names (excluding the input domain).
    """
    store = Store(config.db_path, config.store_dir)

    visited = {domain}
    frontier = [domain]

    for _ in range(hops):
        next_frontier = []
        for d in frontier:
            # Bidirectional: both outgoing and incoming links
            cursor = store.conn.execute(
                "SELECT target_domain FROM domain_links WHERE source_domain = ? "
                "UNION "
                "SELECT source_domain FROM domain_links WHERE target_domain = ?",
                (d, d),
            )
            for row in cursor:
                neighbor = row[0]
                if neighbor not in visited:
                    visited.add(neighbor)
                    next_frontier.append(neighbor)
        frontier = next_frontier

    store.close()
    visited.discard(domain)
    return sorted(visited)


def get_graph_summary(config: RetrievalConfig) -> dict:
    """Get summary of the domain link graph."""
    store = Store(config.db_path, config.store_dir)

    try:
        cursor = store.conn.execute("SELECT COUNT(*) as cnt FROM domain_links")
        total_links = cursor.fetchone()["cnt"]
    except Exception:
        store.close()
        return {"total_links": 0, "domains": []}

    cursor = store.conn.execute(
        "SELECT source_domain, COUNT(*) as out_degree "
        "FROM domain_links GROUP BY source_domain ORDER BY out_degree DESC"
    )
    domains = [{"domain": row["source_domain"], "out_links": row["out_degree"]} for row in cursor]

    # Find most connected domains (in + out)
    cursor = store.conn.execute("""
        SELECT domain, SUM(cnt) as total_connections FROM (
            SELECT source_domain as domain, COUNT(*) as cnt FROM domain_links GROUP BY source_domain
            UNION ALL
            SELECT target_domain as domain, COUNT(*) as cnt FROM domain_links GROUP BY target_domain
        ) GROUP BY domain ORDER BY total_connections DESC LIMIT 10
    """)
    hubs = [{"domain": row["domain"], "connections": row["total_connections"]} for row in cursor]

    store.close()
    return {
        "total_links": total_links,
        "domains_with_links": len(domains),
        "hubs": hubs,
    }
