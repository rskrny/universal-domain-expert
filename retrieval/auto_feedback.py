"""
Self-evaluating feedback system.

The system trains itself by generating ground-truth queries for each chunk,
running those queries through search, and scoring whether the right chunks
surface. No human interaction required.

Three modes:
1. generate  -- create ground-truth queries from chunk metadata and content
2. evaluate  -- run those queries and record +1/-1 feedback automatically
3. report    -- show how well the system retrieves its own knowledge
"""

import random
import hashlib
import logging
import time
from typing import Optional
from pathlib import Path

from .config import RetrievalConfig
from .store import Store
from .tokenizer import tokenize

logger = logging.getLogger("retrieval.auto_feedback")


def generate_ground_truth_queries(chunk: dict) -> list[str]:
    """
    Generate queries that SHOULD retrieve this chunk.

    Uses structural metadata (headers, domain, source file) and
    content analysis (distinctive terms) to create realistic queries.
    No LLM needed. Pure heuristics.
    """
    queries = []
    domain = chunk.get("domain") or ""
    headers = chunk.get("header_path") or []
    source = chunk.get("source_file", "")
    text = chunk.get("text", "")

    # Strategy 1: Header-based queries
    # Headers are the most reliable signal for what a chunk is about
    if headers:
        # Last header is most specific
        queries.append(headers[-1])

        # Domain + last header
        if domain:
            queries.append(f"{domain.replace('-', ' ')} {headers[-1]}")

        # Full header path as a natural question
        if len(headers) >= 2:
            queries.append(f"{headers[-2]} {headers[-1]}")

    # Strategy 2: Source file name as query
    # File names often describe the topic well
    if source:
        name = source.split("/")[-1].replace(".md", "").replace("-", " ")
        # Skip generic names
        if name not in ("index", "readme", "template", "writing style"):
            queries.append(name)

    # Strategy 3: Distinctive term extraction
    # Find words that appear in this chunk but are unusual (high TF, low expected DF)
    distinctive = _extract_distinctive_terms(text, top_n=6)
    if distinctive and domain:
        # Create a query from domain + distinctive terms
        term_query = f"{domain.replace('-', ' ')} {' '.join(distinctive[:3])}"
        queries.append(term_query)
    if len(distinctive) >= 4:
        queries.append(" ".join(distinctive[:4]))

    # Strategy 4: Content type specific queries
    ctype = chunk.get("content_type", "prose")
    if ctype == "code" and headers:
        queries.append(f"code example {headers[-1]}")
    elif ctype == "table" and headers:
        queries.append(f"table {headers[-1]}")

    # Deduplicate and limit
    seen = set()
    unique = []
    for q in queries:
        q = q.strip()
        if not q or len(q) < 5:
            continue
        key = q.lower()
        if key not in seen:
            seen.add(key)
            unique.append(q)

    return unique[:5]


# Common English words to skip during distinctive term extraction
_STOP_WORDS = frozenset("""
the and for are but not you all any can had her was one our out day get has him
his how its may new now old see way who did got let say she too use with from
that this will your they been have make like long look many over such take than
them very what when which also back been come each give most some tell than
these want well just only come know take work call name over first into year
after could made find here more need time down said would about other their
there been their those some what when which where
""".split())


def _extract_distinctive_terms(text: str, top_n: int = 6) -> list[str]:
    """
    Extract distinctive terms from text using term frequency.

    Filters out common English words and single characters.
    Returns terms ordered by frequency (most frequent first).
    """
    tokens = tokenize(text)
    if not tokens:
        return []

    # Count frequencies
    freq: dict[str, int] = {}
    for t in tokens:
        if t in _STOP_WORDS or len(t) <= 2:
            continue
        # Skip pure numbers
        if t.isdigit():
            continue
        freq[t] = freq.get(t, 0) + 1

    # Sort by frequency, take top N
    sorted_terms = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    return [term for term, count in sorted_terms[:top_n]]


def self_evaluate(
    config: RetrievalConfig,
    sample_size: int = 300,
    verbose: bool = True,
) -> dict:
    """
    Run a self-evaluation sweep across the knowledge base.

    For each sampled chunk:
    1. Generate ground-truth queries
    2. Run each query through BM25 search (fast, no GPU)
    3. Score: +1 if chunk in top 5, -1 if chunk not in top 20
    4. Record feedback in the database

    Returns evaluation statistics.
    """
    store = Store(config.db_path, config.store_dir)

    # Use BM25-only searcher to avoid loading embeddings (saves RAM)
    from .searcher import Searcher
    searcher_config = RetrievalConfig(
        knowledge_root=config.knowledge_root,
        store_dir=config.store_dir,
        db_path=config.db_path,
        use_semantic=False,  # BM25 only for speed
    )
    searcher = Searcher(searcher_config)

    chunks = store.get_all_chunks()
    if not chunks:
        if verbose:
            print("No chunks to evaluate.")
        return {"positive": 0, "negative": 0, "neutral": 0, "sampled": 0}

    # Sample chunks (stratified by domain if possible)
    sample = _stratified_sample(chunks, sample_size)
    if verbose:
        print(f"Self-evaluating {len(sample)} chunks (of {len(chunks)} total)...")

    positive = 0
    negative = 0
    neutral = 0
    total_queries = 0
    start = time.time()

    for i, chunk in enumerate(sample):
        queries = generate_ground_truth_queries(chunk)
        if not queries:
            continue

        for query in queries:
            total_queries += 1
            results = searcher.search_bm25_only(query, top_k=20)
            result_ids = [r.chunk_id for r in results]

            if chunk["id"] in result_ids[:5]:
                # Chunk is in top 5: positive signal
                store.add_feedback(chunk["id"], f"[auto] {query}", +1)
                positive += 1
            elif chunk["id"] not in result_ids:
                # Chunk not in top 20 at all: negative signal
                store.add_feedback(chunk["id"], f"[auto] {query}", -1)
                negative += 1
            else:
                # Chunk in top 6-20: neutral, skip
                neutral += 1

        if verbose and (i + 1) % 50 == 0:
            elapsed = time.time() - start
            print(f"  {i+1}/{len(sample)} chunks evaluated ({elapsed:.1f}s)")

    elapsed = time.time() - start
    searcher.close()
    store.close()

    stats = {
        "sampled_chunks": len(sample),
        "total_queries": total_queries,
        "positive": positive,
        "negative": negative,
        "neutral": neutral,
        "recall_at_5": round(positive / max(total_queries, 1), 3),
        "recall_at_20": round((positive + neutral) / max(total_queries, 1), 3),
        "elapsed_seconds": round(elapsed, 2),
    }

    if verbose:
        print(f"\nSelf-Evaluation Results")
        print(f"{'='*50}")
        print(f"  Chunks sampled:  {stats['sampled_chunks']}")
        print(f"  Queries tested:  {stats['total_queries']}")
        print(f"  Recall@5:        {stats['recall_at_5']:.1%}")
        print(f"  Recall@20:       {stats['recall_at_20']:.1%}")
        print(f"  Positive (+1):   {stats['positive']}")
        print(f"  Negative (-1):   {stats['negative']}")
        print(f"  Neutral (skip):  {stats['neutral']}")
        print(f"  Time:            {stats['elapsed_seconds']}s")

    return stats


def clear_auto_feedback(config: RetrievalConfig, verbose: bool = True) -> int:
    """Remove all auto-generated feedback entries (prefix: [auto])."""
    store = Store(config.db_path, config.store_dir)
    cursor = store.conn.execute(
        "DELETE FROM feedback WHERE query_text LIKE '[auto]%'"
    )
    count = cursor.rowcount
    store.conn.commit()
    store.close()
    if verbose:
        print(f"Cleared {count} auto-feedback entries.")
    return count


def domain_recall_report(
    config: RetrievalConfig,
    sample_per_domain: int = 20,
    verbose: bool = True,
) -> list[dict]:
    """
    Per-domain recall report. Shows which domains the system
    retrieves well and which it struggles with.

    Returns list of {domain, recall_at_5, recall_at_20, queries_tested}.
    """
    store = Store(config.db_path, config.store_dir)
    from .searcher import Searcher

    searcher_config = RetrievalConfig(
        knowledge_root=config.knowledge_root,
        store_dir=config.store_dir,
        db_path=config.db_path,
        use_semantic=False,
    )
    searcher = Searcher(searcher_config)

    chunks = store.get_all_chunks()

    # Group by domain
    by_domain: dict[str, list[dict]] = {}
    for c in chunks:
        d = c.get("domain") or "shared"
        by_domain.setdefault(d, []).append(c)

    results = []

    for domain, domain_chunks in sorted(by_domain.items()):
        sample = random.sample(domain_chunks, min(sample_per_domain, len(domain_chunks)))
        hits_5 = 0
        hits_20 = 0
        total = 0

        for chunk in sample:
            queries = generate_ground_truth_queries(chunk)
            for query in queries:
                total += 1
                search_results = searcher.search_bm25_only(query, top_k=20)
                result_ids = [r.chunk_id for r in search_results]

                if chunk["id"] in result_ids[:5]:
                    hits_5 += 1
                    hits_20 += 1
                elif chunk["id"] in result_ids:
                    hits_20 += 1

        r5 = round(hits_5 / max(total, 1), 3)
        r20 = round(hits_20 / max(total, 1), 3)
        results.append({
            "domain": domain,
            "recall_at_5": r5,
            "recall_at_20": r20,
            "queries_tested": total,
            "chunks_sampled": len(sample),
        })

    searcher.close()
    store.close()

    if verbose:
        print(f"\nDomain Recall Report")
        print(f"{'='*70}")
        print(f"  {'Domain':<30s} {'R@5':>6s} {'R@20':>6s} {'Queries':>8s}")
        print(f"  {'-'*30} {'-'*6} {'-'*6} {'-'*8}")
        for r in sorted(results, key=lambda x: x["recall_at_5"]):
            r5_pct = f"{r['recall_at_5']:.0%}"
            r20_pct = f"{r['recall_at_20']:.0%}"
            print(f"  {r['domain']:<30s} {r5_pct:>6s} {r20_pct:>6s} {r['queries_tested']:>8d}")

    return results


def _stratified_sample(chunks: list[dict], n: int) -> list[dict]:
    """Sample chunks with proportional representation from each domain."""
    by_domain: dict[str, list[dict]] = {}
    for c in chunks:
        d = c.get("domain") or "shared"
        by_domain.setdefault(d, []).append(c)

    total = len(chunks)
    sample = []

    for domain, domain_chunks in by_domain.items():
        # Proportional allocation, minimum 1
        domain_n = max(1, round(n * len(domain_chunks) / total))
        domain_n = min(domain_n, len(domain_chunks))
        sample.extend(random.sample(domain_chunks, domain_n))

    # If we overshot, trim. If we undershot, add more.
    if len(sample) > n:
        sample = random.sample(sample, n)
    elif len(sample) < n:
        remaining = [c for c in chunks if c not in sample]
        extra = min(n - len(sample), len(remaining))
        if extra > 0:
            sample.extend(random.sample(remaining, extra))

    return sample
