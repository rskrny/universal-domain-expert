"""
Bootstrap neural network training data from existing knowledge base.

Generates synthetic routing samples from indexed chunks. Each chunk's
text is used to create a representative query, paired with its known
domain. This gives the neural router enough data to train without
requiring 50+ real conversations.

Also seeds chunk effectiveness data from structural signals (domain
match, content type, token count) to bootstrap the reranker.

Run: python -m dashboard.bootstrap_training
"""

import logging
import random
import time
from pathlib import Path

import numpy as np

logger = logging.getLogger("dashboard.bootstrap")


def extract_query_from_chunk(text: str, max_words: int = 15) -> str:
    """Extract a representative query from chunk text.

    Strategy: take the first meaningful sentence or header as a
    natural query someone would ask to find this content.
    """
    lines = text.strip().split("\n")
    for line in lines:
        line = line.strip()
        # Skip empty lines, frontmatter markers, short lines
        if not line or line.startswith("---") or len(line) < 10:
            continue
        # Headers become good queries
        if line.startswith("#"):
            query = line.lstrip("#").strip()
            if len(query.split()) >= 3:
                return " ".join(query.split()[:max_words])
        # First substantive line
        if len(line.split()) >= 5:
            words = line.split()[:max_words]
            return " ".join(words)
    # Fallback: first max_words of the text
    return " ".join(text.split()[:max_words])


def bootstrap_routing_data(db, searcher, sample_per_domain: int = 5) -> dict:
    """Generate synthetic routing training samples from indexed chunks.

    For each domain, picks representative chunks and generates
    (query_embedding, domain) pairs for the neural router.
    """
    if searcher is None or searcher.model is None:
        logger.warning("Semantic model not loaded. Cannot generate embeddings for bootstrap.")
        return {"status": "no_model", "samples": 0}

    chunks = searcher.chunks
    if not chunks:
        return {"status": "no_chunks", "samples": 0}

    # Group chunks by domain
    domain_chunks = {}
    for c in chunks:
        d = c.get("domain") or c.get("project")
        if d:
            domain_chunks.setdefault(d, []).append(c)

    # Also group by project
    for c in chunks:
        p = c.get("project")
        if p:
            key = f"project-{p}" if not p.startswith("project-") else p
            domain_chunks.setdefault(key, []).append(c)

    total_samples = 0
    domains_processed = 0

    for domain, chunks_list in domain_chunks.items():
        # Sample representative chunks
        sample_size = min(sample_per_domain, len(chunks_list))
        sampled = random.sample(chunks_list, sample_size)

        queries = []
        for c in sampled:
            query = extract_query_from_chunk(c["text"])
            if query and len(query.split()) >= 3:
                queries.append(query)

        if not queries:
            continue

        # Batch encode queries
        try:
            embeddings = searcher.model.encode(
                queries, normalize_embeddings=True, show_progress_bar=False
            )
        except Exception as e:
            logger.warning("Failed to encode queries for %s: %s", domain, e)
            continue

        # Insert into routing_log
        for query_text, emb in zip(queries, embeddings):
            query_emb = emb.astype(np.float32).tobytes()
            db.log_routing(
                query_text=query_text,
                query_embedding=query_emb,
                predicted_domain=domain,
                tier=2,
                chunk_ids=[],
                method="bootstrap",
            )
            total_samples += 1

        domains_processed += 1

    return {
        "status": "ok",
        "samples": total_samples,
        "domains": domains_processed,
    }


def bootstrap_chunk_effectiveness(db, store) -> dict:
    """Seed chunk effectiveness from structural quality signals.

    Chunks with headers, reasonable length, and domain tags get
    a baseline effectiveness score. This gives the reranker
    something to train on before real feedback arrives.
    """
    chunks = store.get_all_chunks()
    if not chunks:
        return {"status": "no_chunks", "seeded": 0}

    seeded = 0
    now = time.time()

    # Build batch of statements
    stmts = []
    for c in chunks:
        # Score based on structural quality
        score = 0.5  # baseline

        # Has headers (well-structured content)
        if c.get("header_path") and len(c["header_path"]) > 0:
            score += 0.1

        # Has domain tag (properly classified)
        if c.get("domain"):
            score += 0.1

        # Reasonable length (not too short, not too long)
        tokens = c.get("token_estimate", 0)
        if 50 < tokens < 400:
            score += 0.1

        # Content type bonus
        ct = c.get("content_type", "")
        if ct in ("prose", "code"):
            score += 0.05

        score = min(score, 1.0)

        stmts.append((
            "INSERT OR IGNORE INTO chunk_effectiveness "
            "(chunk_id, times_retrieved, times_helpful, effectiveness, updated_at) "
            "VALUES (?, 1, ?, ?, ?)",
            (c["id"], 1 if score > 0.6 else 0, round(score, 3), now),
        ))
        seeded += 1

    # Execute in batches
    if stmts:
        db._write(stmts)

    return {"status": "ok", "seeded": seeded}


def run_bootstrap(verbose: bool = True) -> dict:
    """Run the full bootstrap pipeline."""
    from retrieval.config import RetrievalConfig
    from retrieval.searcher import Searcher
    from dashboard.db import DashboardDB

    config = RetrievalConfig.from_yaml(Path("retrieval/config.yaml"))
    config.knowledge_root = Path(".")
    config.store_dir = Path("retrieval/store")
    config.db_path = config.store_dir / "metadata.db"

    db = DashboardDB(db_path=config.db_path)

    # Check if already bootstrapped
    status = db.get_neural_status()
    if status["routing_samples"] >= 50:
        if verbose:
            print(f"Already have {status['routing_samples']} routing samples. Skipping bootstrap.")
        return {"status": "already_bootstrapped", "existing_samples": status["routing_samples"]}

    if verbose:
        print("Loading searcher with semantic model...")
    searcher = Searcher(config)
    # Force-load the semantic model (it's lazy-loaded by default)
    if config.use_semantic:
        searcher._get_semantic_model()
        if verbose:
            print(f"  Semantic model loaded: {searcher.model is not None}")

    if verbose:
        print(f"Loaded {len(searcher.chunks)} chunks")

    # 1. Bootstrap routing data
    if verbose:
        print("Generating synthetic routing samples...")
    routing_result = bootstrap_routing_data(db, searcher, sample_per_domain=5)
    if verbose:
        print(f"  Routing: {routing_result['samples']} samples across {routing_result.get('domains', 0)} domains")

    # 2. Bootstrap chunk effectiveness
    if verbose:
        print("Seeding chunk effectiveness scores...")
    effectiveness_result = bootstrap_chunk_effectiveness(db, searcher.store)
    if verbose:
        print(f"  Effectiveness: {effectiveness_result['seeded']} chunks seeded")

    # 3. Now train the neural components
    if verbose:
        print("Training neural components...")

    from dashboard.neural_router import NeuralRouter
    from dashboard.reranker import LearnedReranker

    router = NeuralRouter(model_dir=config.store_dir, db=db)
    router_result = router.train()
    if verbose:
        if router_result:
            print(f"  Router: {router_result['accuracy']:.1%} accuracy on {router_result['samples']} samples")
        else:
            print("  Router: not enough data yet")

    reranker = LearnedReranker(model_dir=config.store_dir, db=db)
    reranker_result = reranker.train()
    if verbose:
        if reranker_result:
            print(f"  Reranker: {reranker_result['accuracy']:.1%} accuracy on {reranker_result['samples']} samples")
        else:
            print("  Reranker: not enough data yet")

    db.close()
    searcher.close()

    return {
        "routing": routing_result,
        "effectiveness": effectiveness_result,
        "router_training": router_result,
        "reranker_training": reranker_result,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run_bootstrap(verbose=True)
    print(f"\nBootstrap complete: {result}")
