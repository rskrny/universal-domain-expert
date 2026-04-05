"""
Command-line interface for the retrieval system.

Usage:
    python -m retrieval index                  Build/rebuild the search index
    python -m retrieval index --full           Force full rebuild (ignore cache)
    python -m retrieval search "query"         Search the knowledge base
    python -m retrieval search "query" -k 5 --domain business-consulting
    python -m retrieval search "query" --bm25-only   Skip semantic search
    python -m retrieval context "query"        Get optimized context block
    python -m retrieval viz                    Generate knowledge graph
    python -m retrieval viz --open             Generate and open in browser
    python -m retrieval stats                  Show index statistics
"""

import argparse
import sys
import os
from pathlib import Path

# Fix Windows console encoding for Unicode characters
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

from .config import RetrievalConfig


def cmd_index(args):
    """Build or rebuild the search index."""
    config = _load_config(args)
    force = getattr(args, "full", False)
    print(f"Indexing knowledge base at: {config.knowledge_root}")
    print(f"Directories: {config.index_dirs}")
    print(f"Mode: {'full rebuild' if force else 'incremental'}")
    print()

    from .indexer import build_index
    stats = build_index(config, verbose=True, force_full=force)
    return stats


def cmd_search(args):
    """Search the knowledge base."""
    config = _load_config(args)

    from .searcher import Searcher
    searcher = Searcher(config)

    if args.bm25_only:
        results = searcher.search_bm25_only(args.query, top_k=args.top_k)
    else:
        results = searcher.search(
            query=args.query,
            top_k=args.top_k,
            domain_filter=args.domain,
            file_filter=args.file,
        )

    if not results:
        print("No results found.")
        return

    print(f"\n{'='*70}")
    print(f"  Results for: \"{args.query}\"")
    print(f"  ({len(results)} results)")
    print(f"{'='*70}\n")

    for i, r in enumerate(results, 1):
        rank_info = []
        if r.bm25_rank is not None:
            rank_info.append(f"BM25:#{r.bm25_rank+1}")
        if r.semantic_rank is not None:
            rank_info.append(f"Semantic:#{r.semantic_rank+1}")

        print(f"  [{i}] {r.context_label}")
        print(f"      Score: {r.score:.4f}  |  {' | '.join(rank_info)}")
        if r.domain:
            print(f"      Domain: {r.domain}")
        if r.tags:
            print(f"      Tags: {', '.join(r.tags)}")
        # Show preview (first 200 chars)
        preview = r.text[:200].replace("\n", " ")
        if len(r.text) > 200:
            preview += "..."
        print(f"      {preview}")
        print()

    searcher.close()


def cmd_stats(args):
    """Show index statistics."""
    config = _load_config(args)

    from .searcher import Searcher
    searcher = Searcher(config)
    stats = searcher.get_stats()

    print(f"\nIndex Statistics")
    print(f"{'='*40}")
    print(f"  Total chunks: {stats['total_chunks']}")
    print(f"  BM25 loaded:  {stats['bm25_loaded']}")
    print(f"  Semantic:     {stats['semantic_loaded']}")
    print(f"  Last indexed: {stats['last_indexed']}")
    print(f"\n  Domains: {', '.join(stats['domains']) if stats['domains'] else 'none'}")
    print(f"\n  Files indexed:")
    for f in stats["files"]:
        print(f"    - {f}")

    searcher.close()


def cmd_context(args):
    """Get an optimized context block for a query."""
    config = _load_config(args)

    from .searcher import Searcher
    from .optimizer import optimize_context, format_context_block

    searcher = Searcher(config)
    results = searcher.search(query=args.query, top_k=20, domain_filter=args.domain)
    searcher.close()

    optimized = optimize_context(
        results,
        token_budget=args.budget,
        compress=True,
    )

    if not optimized:
        print("No relevant context found.")
        return

    block = format_context_block(optimized)
    print(block)
    print(f"\n--- {len(optimized)} chunks, ~{sum(c['tokens'] for c in optimized)} tokens ---")


def cmd_viz(args):
    """Generate knowledge graph visualization."""
    config = _load_config(args)

    from .visualize import generate_visualization
    path = generate_visualization(config, open_browser=args.open)
    print(f"Knowledge graph generated: {path}")
    if not args.open:
        print("Run with --open to view in browser")


def cmd_test(args):
    """Run quality tests."""
    from .test_quality import run_tests
    verbose = getattr(args, "verbose", False)
    report = run_tests(verbose=verbose)
    if not report["success"]:
        sys.exit(1)


def cmd_feedback(args):
    """Record feedback for a chunk."""
    config = _load_config(args)
    from .store import Store
    store = Store(config.db_path, config.store_dir)

    if args.action == "add":
        store.add_feedback(args.chunk_id, args.query, args.rating)
        print(f"Feedback recorded: chunk {args.chunk_id} = {'+1' if args.rating > 0 else '-1'}")
    elif args.action == "stats":
        count = store.feedback_count()
        scores = store.get_chunk_feedback_scores()
        print(f"\nFeedback Statistics")
        print(f"{'='*40}")
        print(f"  Total feedback entries: {count}")
        print(f"  Chunks with feedback: {len(scores)}")
        if scores:
            positive = sum(1 for v in scores.values() if v > 0)
            negative = sum(1 for v in scores.values() if v < 0)
            print(f"  Net positive chunks: {positive}")
            print(f"  Net negative chunks: {negative}")
    store.close()


def cmd_gaps(args):
    """Show knowledge gaps based on query difficulty."""
    config = _load_config(args)
    from .store import Store
    store = Store(config.db_path, config.store_dir)

    if args.action == "queries":
        hard = store.get_hard_queries(min_difficulty=args.threshold, limit=args.limit)
        if not hard:
            print("No high-difficulty queries logged yet. Use the system more to accumulate data.")
            store.close()
            return
        print(f"\nHard Queries (difficulty >= {args.threshold})")
        print(f"{'='*60}")
        for q in hard:
            print(f"  [{q['difficulty_score']:.2f}] {q['query_text'][:80]}")
            print(f"         Domain: {q['domain']}")
            print()
    elif args.action == "domains":
        stats = store.get_domain_difficulty_stats()
        if not stats:
            print("No difficulty data yet. Use the system more to accumulate data.")
            store.close()
            return
        print(f"\nDomain Difficulty Ranking")
        print(f"{'='*60}")
        for d in stats:
            bar = "#" * int(d["avg_difficulty"] * 20)
            print(f"  {d['domain']:<30s} {d['avg_difficulty']:.2f} {bar} ({d['query_count']} queries)")
    store.close()


def cmd_expand(args):
    """Search with multi-query expansion."""
    config = _load_config(args)
    from .searcher import Searcher
    from .query_expander import search_with_expansion, expand_query_rules, expand_query_llm

    searcher = Searcher(config)

    # Show expansion variants
    if args.llm:
        variants = expand_query_llm(args.query)
    else:
        variants = expand_query_rules(args.query)

    print(f"\nQuery variants ({len(variants)}):")
    for i, v in enumerate(variants):
        label = "original" if i == 0 else f"variant {i}"
        print(f"  [{label}] {v}")
    print()

    results = search_with_expansion(
        searcher, args.query, top_k=args.top_k,
        domain_filter=args.domain, use_llm=args.llm,
    )

    if not results:
        print("No results found.")
        searcher.close()
        return

    print(f"{'='*70}")
    print(f"  Expanded results for: \"{args.query}\"")
    print(f"  ({len(results)} results)")
    print(f"{'='*70}\n")

    for i, r in enumerate(results, 1):
        print(f"  [{i}] {r.context_label}")
        print(f"      Score: {r.score:.4f}")
        if r.domain:
            print(f"      Domain: {r.domain}")
        preview = r.text[:200].replace("\n", " ")
        if len(r.text) > 200:
            preview += "..."
        print(f"      {preview}")
        print()

    searcher.close()


def cmd_autofeedback(args):
    """Run self-evaluation to generate automatic feedback."""
    config = _load_config(args)
    from .auto_feedback import self_evaluate, clear_auto_feedback, domain_recall_report

    if args.action == "run":
        if args.clear_first:
            clear_auto_feedback(config, verbose=True)
        self_evaluate(config, sample_size=args.sample_size, verbose=True)
    elif args.action == "clear":
        clear_auto_feedback(config, verbose=True)
    elif args.action == "report":
        domain_recall_report(config, sample_per_domain=args.sample_size, verbose=True)


def cmd_hyde(args):
    """Search using Hypothetical Document Embedding."""
    config = _load_config(args)
    from .searcher import Searcher

    searcher = Searcher(config)
    results = searcher.search_hyde(
        query=args.query,
        top_k=args.top_k,
        domain_filter=args.domain,
    )

    if not results:
        print("No results found.")
        searcher.close()
        return

    print(f"\n{'='*70}")
    print(f"  HyDE results for: \"{args.query}\"")
    print(f"  ({len(results)} results)")
    print(f"{'='*70}\n")

    for i, r in enumerate(results, 1):
        print(f"  [{i}] {r.context_label}")
        print(f"      Score: {r.score:.4f}")
        if r.domain:
            print(f"      Domain: {r.domain}")
        preview = r.text[:200].replace("\n", " ")
        if len(r.text) > 200:
            preview += "..."
        print(f"      {preview}")
        print()

    searcher.close()


def cmd_graph(args):
    """Build or inspect the domain link graph."""
    config = _load_config(args)

    if args.action == "build":
        from .domain_graph import build_domain_graph
        print("Building domain link graph...")
        stats = build_domain_graph(config, verbose=True)
        print(f"\nGraph built: {stats['links_found']} links across {stats['unique_sources']} domains")

    elif args.action == "show":
        from .domain_graph import get_graph_summary
        summary = get_graph_summary(config)
        if summary["total_links"] == 0:
            print("No graph data. Run: python -m retrieval graph build")
            return
        print(f"\nDomain Link Graph Summary")
        print(f"{'='*50}")
        print(f"  Total links: {summary['total_links']}")
        print(f"  Domains with links: {summary['domains_with_links']}")
        print(f"\n  Top 10 most-connected domains:")
        for h in summary.get("hubs", []):
            bar = "#" * h["connections"]
            print(f"    {h['domain']:<30s} {bar} ({h['connections']})")

    elif args.action == "neighbors":
        if not args.domain:
            print("Error: --domain required for neighbors action")
            return
        from .domain_graph import get_adjacent_domains
        neighbors = get_adjacent_domains(config, args.domain, hops=args.hops)
        if not neighbors:
            print(f"No neighbors found for '{args.domain}'. Run: python -m retrieval graph build")
            return
        print(f"\nNeighbors of '{args.domain}' ({args.hops}-hop):")
        for n in neighbors:
            print(f"  - {n}")


def _load_config(args) -> RetrievalConfig:
    """Build config from CLI args."""
    root = Path(args.root).resolve()
    config_path = root / "retrieval" / "config.yaml"

    if config_path.exists():
        config = RetrievalConfig.from_yaml(config_path)
    else:
        config = RetrievalConfig()

    config.knowledge_root = root
    config.store_dir = root / "retrieval" / "store"
    config.db_path = config.store_dir / "metadata.db"
    return config


def main():
    parser = argparse.ArgumentParser(
        description="Context Engineering Retrieval System"
    )
    parser.add_argument(
        "--root", default=".",
        help="Path to the knowledge base root directory"
    )
    subparsers = parser.add_subparsers(dest="command")

    # index
    sub_index = subparsers.add_parser("index", help="Build/rebuild the search index")
    sub_index.add_argument("--full", action="store_true", help="Force full rebuild")

    # search
    sub_search = subparsers.add_parser("search", help="Search the knowledge base")
    sub_search.add_argument("query", help="Search query")
    sub_search.add_argument("-k", "--top-k", type=int, default=10)
    sub_search.add_argument("--domain", help="Filter by domain")
    sub_search.add_argument("--file", help="Filter by file path substring")
    sub_search.add_argument(
        "--bm25-only", action="store_true",
        help="Use BM25 only (no semantic search, no ML dependencies)"
    )

    # context
    sub_ctx = subparsers.add_parser("context", help="Get optimized context block")
    sub_ctx.add_argument("query", help="What context do you need?")
    sub_ctx.add_argument("--budget", type=int, default=4000, help="Token budget")
    sub_ctx.add_argument("--domain", help="Filter by domain")

    # viz
    sub_viz = subparsers.add_parser("viz", help="Generate knowledge graph visualization")
    sub_viz.add_argument("--open", action="store_true", help="Open in browser")

    # stats
    sub_stats = subparsers.add_parser("stats", help="Show index statistics")

    # test
    sub_test = subparsers.add_parser("test", help="Run quality tests")
    sub_test.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    # feedback
    sub_fb = subparsers.add_parser("feedback", help="Record or view retrieval feedback")
    sub_fb.add_argument("action", choices=["add", "stats"], help="add feedback or view stats")
    sub_fb.add_argument("--chunk-id", type=int, help="Chunk ID (for add)")
    sub_fb.add_argument("--query", help="Query text (for add)")
    sub_fb.add_argument("--rating", type=int, choices=[-1, 1], help="+1 or -1 (for add)")

    # gaps
    sub_gaps = subparsers.add_parser("gaps", help="Show knowledge gaps from query difficulty")
    sub_gaps.add_argument("action", choices=["queries", "domains"], help="View hard queries or domain stats")
    sub_gaps.add_argument("--threshold", type=float, default=0.7, help="Min difficulty score")
    sub_gaps.add_argument("--limit", type=int, default=20, help="Max results")

    # expand (multi-query search)
    sub_expand = subparsers.add_parser("expand", help="Search with multi-query expansion")
    sub_expand.add_argument("query", help="Search query")
    sub_expand.add_argument("-k", "--top-k", type=int, default=10)
    sub_expand.add_argument("--domain", help="Filter by domain")
    sub_expand.add_argument("--llm", action="store_true", help="Use LLM for query expansion")

    # autofeedback
    sub_af = subparsers.add_parser("autofeedback", help="Self-evaluation feedback system")
    sub_af.add_argument("action", choices=["run", "clear", "report"],
                        help="run evaluation, clear auto-feedback, or show domain report")
    sub_af.add_argument("--sample-size", type=int, default=300,
                        help="Number of chunks to sample (run) or per-domain (report)")
    sub_af.add_argument("--clear-first", action="store_true",
                        help="Clear existing auto-feedback before running")

    # hyde
    sub_hyde = subparsers.add_parser("hyde", help="Search with Hypothetical Document Embedding")
    sub_hyde.add_argument("query", help="Search query")
    sub_hyde.add_argument("-k", "--top-k", type=int, default=10)
    sub_hyde.add_argument("--domain", help="Filter by domain")

    # graph
    sub_graph = subparsers.add_parser("graph", help="Build or inspect the domain link graph")
    sub_graph.add_argument("action", choices=["build", "show", "neighbors"],
                           help="build graph, show summary, or find neighbors")
    sub_graph.add_argument("--domain", help="Domain to find neighbors for (neighbors action)")
    sub_graph.add_argument("--hops", type=int, default=1, help="Number of hops for neighbor search")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    commands = {
        "index": cmd_index,
        "search": cmd_search,
        "context": cmd_context,
        "viz": cmd_viz,
        "stats": cmd_stats,
        "test": cmd_test,
        "feedback": cmd_feedback,
        "gaps": cmd_gaps,
        "expand": cmd_expand,
        "graph": cmd_graph,
        "autofeedback": cmd_autofeedback,
        "hyde": cmd_hyde,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
