# Architecture -- Universal Domain Expert System

> Source of truth for the system's structure.
> Read this before modifying any module. Update it when you add or change components.
> Last verified: April 5, 2026.

---

## System Overview

This is a knowledge operating system that turns Claude Code into a domain expert
across 74 professional disciplines. It combines prompt engineering, hybrid retrieval,
self-evaluating feedback, and external integrations into a single portable system.

Four capabilities, one sentence each:

1. **Expert routing.** Classify any request by domain and complexity, load only
   the expertise needed, execute through a structured pipeline.
2. **Knowledge retrieval.** Search 8,500+ enriched chunks across 340+ files using
   BM25, semantic search, and HyDE with token budget optimization.
3. **Self-improving retrieval.** The system generates ground-truth queries from chunk
   metadata, tests its own recall, and records automatic feedback to boost good
   chunks and demote poor ones. No manual interaction needed.
4. **Continuous learning.** Ingest knowledge from Reddit, Lark DMs, and manual
   input. Track difficulty by domain. Enrich chunks with contextual prefixes.

---

## Directory Map

```
ROOT/
  CLAUDE.md               Entry point. Claude Code reads this first.
  ARCHITECTURE.md         You are here. Source of truth for structure.
  .env                    API keys (Anthropic, Reddit, Lark, dashboard token)

  prompts/                THE KNOWLEDGE LAYER
    ROUTER.md             Request classifier (domain + tier + context needs)
    AGENTS.md             8-stage execution pipeline definition
    TEMPLATE.md           Template for creating new domain files
    domains/              73 domain expertise files (one per discipline)
    context/              Supporting knowledge chunks
      shared/             Cross-domain (writing style, mental models, comms)
      by-domain/          Domain-specific reference material + Reddit ingested
    workflows/
      tiers.md            Tier 1/2/3 depth definitions
      multi-domain.md     Cross-domain coordination protocol

  retrieval/              THE SEARCH ENGINE
    config.py             RetrievalConfig dataclass + YAML loader
    config.yaml           Tunable settings (weights, dirs, patterns)
    chunker.py            Multi-format fence-aware chunking (961 lines)
    indexer.py             Incremental index builder with dedup + external projects
    searcher.py           Hybrid BM25 + semantic + HyDE search with RRF fusion
    enricher.py           Contextual chunk enrichment (prefix metadata for retrieval)
    auto_feedback.py      Self-evaluating feedback (no manual UI needed)
    query_expander.py     Multi-query expansion (rule-based + LLM)
    domain_graph.py       Cross-domain relationship graph (280 links)
    optimizer.py           MMR token budget optimizer
    store.py              SQLite persistence (WAL mode, 8 tables)
    tokenizer.py          BM25 tokenizer (DO NOT CHANGE without full reindex)
    serve.py              Lightweight HTTP dashboard server (port 8600)
    mcp_server.py         MCP tools for Claude Code native access
    visualize.py          D3.js knowledge graph generator
    cli.py                12 CLI commands (+autofeedback, +hyde)
    test_quality.py       Quality benchmark suite
    ui/
      index.html          Dashboard frontend (search, feedback, domains, gaps, Reddit)
    store/                Generated indexes (SQLite + BM25 pickle + embeddings npy)

  scripts/                AUTOMATION
    setup.py              First-time install (--lite for BM25-only)
    reindex.py            Rebuild indexes after changes
    maintain.py           Full maintenance pass (index + graph + validation)
    bootstrap.py          Session startup context generator
    ingest.py             Unified ingestion (Reddit, Brain Feed, manual, pipeline)
    collect_reddit.py     Expanded Reddit collection (saves + upvotes + comments, composite scoring)
    extract_claims.py     Claude API claim extraction from Reddit posts (evidence, confidence, novelty)
    enrich_domains.py     Domain enrichment pipeline (compare claims to domains, propose additions)
    improve.py            Self-improvement pipeline (domain gaps, skill opportunities, action items)
    subreddit_config.py   Subreddit allowlist/denylist/scan targets (117 allowed, 60 denied, 38 scan)
    sync_brainfeed.py     D1 to local index sync
    send_to_lark.py       Push files/messages to Lark API
    lark_reader.py        Read messages from Lark chats
    lark_digest.py        Generate Lark message digests
    lark_sync.py          Sync state with Lark
    reconcile_memory.py   Sync Claude Code memory with project state
    test_all_systems.py   Integration test runner

  dashboard/              WEB APPLICATION (FastAPI)
    server.py             Main app (REST + WebSocket + static files)
    chat.py               Chat pipeline (context assembly + streaming)
    router.py             Keyword domain classifier (fallback for neural)
    neural_router.py      MLP domain classifier (DISABLED, needs 50+ samples)
    reranker.py           Learned reranker (DISABLED, needs 200+ samples)
    adapter.py            Embedding adapter (DISABLED, wrong training signal)
    trainer.py            Training orchestrator (auto-triggers on thresholds)
    db.py                 Dashboard SQLite layer
    models.py             Pydantic validation models
    projects_registry.py  Multi-project indexing config
    bootstrap_training.py Synthetic training data for cold start
    reddit_scanner.py     Reddit post scoring and digest
    agents/
      flipside_agent.py   The Flip Side briefing agent
      bloodline_agent.py  Data lineage agent

  workers/                CLOUDFLARE EDGE FUNCTIONS
    brainfeed-webhook/    Lark DM ingestion + knowledge storage
      src/index.ts        Webhook handler + REST API + Claude summarization
      wrangler.toml       D1: brainfeed-knowledge, domain: brainfeed.hanahaulers.com
    flipside-lark-bridge/ Briefing delivery + Feishu relay
      src/index.ts        Cron + webhook + REST + MCP
      wrangler.toml       D1: flipside-briefings, domain: feishu.hanahaulers.com
                          Cron: */5 * * * *

  state/                  SESSION PERSISTENCE
    HANDOFF.md            Current session state (save/resume between sessions)
    HANDOFF-PROTOCOL.md   Rules for state transfer
    SESSION_CONTEXT.md    Auto-generated session briefing (from bootstrap.py)
    lark_digest.md        Cached Lark message digest
    lark_sync_state.json  Lark sync watermark
    reddit_ingested.json  Tracks which Reddit posts have been ingested
    reddit_full_collection.json   Merged Reddit collection output (saves + upvotes + comments)
    reddit_extractions.json       Tracks which posts have been claim-extracted
    enrichment_proposals.json     Saved enrichment proposals from domain enrichment
    domain_enrichments.json       Tracks which domains have been enriched

  .claude/                CLAUDE CODE CONFIG
    launch.json           5 dev server configs (dashboard, finmodel, hana, ruleset, knowledge)
    settings.local.json   Permission allowlists
    skills/
      route/              Domain expert routing pipeline
      auto-domain/        Auto-create missing domain files
      quality-ratchet/    Post-engagement quality audit
      sync-brainfeed/     D1 to local index sync
```

---

## Data Flow

### Request Processing

```
User request
  -> CLAUDE.md (bootstrap)
    -> bootstrap.py generates SESSION_CONTEXT.md
    -> HANDOFF.md checked for prior state
  -> ROUTER.md classifies: domain + tier + context needs
    -> routing logged to routing_log table
  -> Domain file loaded from prompts/domains/{domain}.md
  -> Retrieval engine searches for relevant context
    -> BM25 + semantic search with RRF fusion
    -> Feedback scores applied (boost helpful chunks)
    -> Difficulty logged to difficulty_log table
  -> AGENTS.md 8-stage pipeline executes
  -> Output delivered with writing style verification
```

### Knowledge Ingestion

```
Sources:
  Reddit saves (u/slamjacket)    -> scripts/ingest.py reddit
  Lark DMs (Brain Feed bot)      -> scripts/ingest.py brainfeed
  Manual context files            -> direct write to prompts/context/

Simple pipeline:
  Collect -> Classify by domain -> Write .md to context/ -> Reindex
  Tracking files prevent duplicate ingestion.

Full self-improvement pipeline (scripts/ingest.py pipeline):
  1. Collect    (collect_reddit.py)   Pulls saves + upvotes + comments, merges
                                      with composite engagement scoring
                                      -> state/reddit_full_collection.json
  2. Extract    (extract_claims.py)   Claude API claim extraction from raw posts.
                                      Structured claims: evidence type, confidence,
                                      novelty, counterarguments
                                      -> state/reddit_extractions.json
  3. Enrich     (enrich_domains.py)   Compares claims against domain files. Proposes
                                      NEW_FRAMEWORK, EVIDENCE, COUNTER additions.
                                      Writes "Practitioner Insights" sections
                                      -> state/enrichment_proposals.json
                                      -> state/domain_enrichments.json
  4. Reindex    (retrieval index)     Rebuild search index with enriched domains
  5. Improve    (improve.py)          Analyzes pipeline output for domain gaps,
                                      skill opportunities, project intelligence,
                                      and recommended action items
```

### Feedback Loop

```
Search query
  -> Results returned with chunk IDs
  -> User rates via dashboard (+1/-1 per chunk)
  -> Stored in feedback table (chunk_id, query_hash, rating)
  -> Next search: feedback scores boost/penalize results
  -> Difficulty logged: identifies weak domains
  -> python -m retrieval gaps domains shows where to improve
```

---

## Module Connections

### Who Imports What

| Module | Depends On |
|--------|-----------|
| `indexer.py` | chunker, store, tokenizer, projects_registry |
| `searcher.py` | config, store, tokenizer, (adapter) |
| `query_expander.py` | searcher (for search_with_expansion) |
| `domain_graph.py` | store, config |
| `optimizer.py` | (standalone, takes SearchResult list) |
| `cli.py` | all retrieval modules (dispatcher) |
| `serve.py` | config, store, searcher, query_expander, domain_graph |
| `mcp_server.py` | config, store, searcher, indexer |
| `dashboard/server.py` | retrieval.config, retrieval.store, retrieval.searcher, dashboard.* |
| `dashboard/chat.py` | retrieval.searcher, dashboard.router |
| `scripts/ingest.py` | retrieval.config, retrieval.store, collect_reddit, extract_claims, enrich_domains, improve |
| `scripts/collect_reddit.py` | subreddit_config, PRAW (Reddit API) |
| `scripts/extract_claims.py` | Anthropic API (Claude) |
| `scripts/enrich_domains.py` | extract_claims output, domain files |
| `scripts/improve.py` | pipeline output (extractions, enrichments, proposals) |
| `scripts/subreddit_config.py` | (standalone config, imported by collect_reddit) |
| `scripts/bootstrap.py` | retrieval.config, retrieval.store |

### Shared State (SQLite)

One database at `retrieval/store/metadata.db` with 7 tables:

| Table | Written By | Read By |
|-------|-----------|---------|
| `chunks` | indexer | searcher, optimizer, visualize, serve |
| `file_hashes` | indexer | indexer (change detection) |
| `index_meta` | indexer | searcher, cli |
| `feedback` | serve, mcp_server, cli | searcher (score boosting) |
| `difficulty_log` | searcher | serve, cli (gap analysis) |
| `domain_links` | domain_graph | serve, cli (neighbor search) |
| `routing_log` | mcp_server, route skill | bootstrap (status), trainer |

BM25 index stored as pickle. Embeddings stored as numpy array.
Both at `retrieval/store/`. Must be rebuilt together (never mix versions).

---

## Search Architecture

### Hybrid Retrieval

Two retrieval paths combined via Reciprocal Rank Fusion (RRF):

**BM25 (40% weight):** Keyword matching. Fast. Precise for exact terms.
Tokenizer: lowercase, strip punctuation, drop single-char. DO NOT change
tokenizer.py without a full reindex.

**Semantic (60% weight):** Embedding similarity using all-MiniLM-L6-v2 (384-dim).
Catches conceptual matches that miss keyword overlap.

**Fusion:** `score = sum(weight_i / (k + rank_i))` where k=60.
Higher k smooths rank differences.

### Search Enhancements

**Feedback scoring:** After RRF fusion, multiply each chunk's score by
`(1 + 0.1 * avg_feedback)` where avg_feedback is -1 to +1. Re-sort.

**Multi-query expansion:** Generate variant phrasings (acronym expansion,
perspective shift, or LLM-based). Search each variant. Merge via RRF.
Original query weighted 1.0, variants weighted 0.7.

**Domain graph expansion:** Given a domain filter, optionally expand to
include first-hop neighbors from the domain_links graph.

### Difficulty Logging

Every search auto-computes a difficulty score (0 = easy, 1 = hard):
- `score_confidence = min(top_score / 0.015, 1.0)`
- `gap_confidence = min(score_gap / 0.005, 1.0)`
- `difficulty = 1 - (0.6 * score_confidence + 0.4 * gap_confidence)`

High difficulty queries indicate knowledge gaps. View with:
`python -m retrieval gaps domains`

---

## Chunking Rules

Multi-format support with fence-aware splitting:

**Protected blocks (never split inside):**
- Code fences (triple backtick)
- Tables (pipe-delimited rows)
- Blockquotes (> prefix)

**Parameters:**
- Max chunk size: 512 tokens
- Overlap: 64 tokens
- Min chunk length: 50 characters
- Split on markdown headers when possible

**Supported formats:**
Markdown, Python, JavaScript, TypeScript, Go, Rust, Java,
HTML, CSV, JSON, YAML, PDF (pymupdf/pdfplumber), DOCX (python-docx)

**Content deduplication:** SHA-256 hash per chunk. Same content never stored twice.

**PII scrubbing:** Optional. Removes SSN, EIN, credit card patterns.
Replaces with `[REDACTED-*]`.

---

## External Services

### Cloudflare

| Resource | ID | Purpose |
|----------|------|---------|
| Zone | `91ea38f84d0a435f58c1fba19f3c0b4c` | hanahaulers.com |
| D1: brainfeed-knowledge | `f4711fcc-1d88-43a5-9e64-393207dcb964` | Lark DM chunks |
| D1: flipside-briefings | `961c5503-b1fc-4047-8a20-6885eb70265b` | Daily briefings |
| Worker: brainfeed-webhook | brainfeed.hanahaulers.com | Knowledge ingestion |
| Worker: flipside-lark-bridge | feishu.hanahaulers.com | Briefing delivery |

### Lark / Feishu

| Bot | App ID | API Base | Org |
|-----|--------|----------|-----|
| Brain Feed | cli_a94474233238de18 | open.larksuite.com | ShopMyRoom |
| FlipBot | cli_a93199ca91b8dcce | open.feishu.cn | BrandPal |

Brain Feed chat: `oc_ab26f9abaea8f93912614f7e7284abd6`

### Reddit

Account: u/slamjacket. PRAW configured. 253 saved posts accessible.
Credentials in `.env` (REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, etc.)
Pipeline at `C:\Users\rskrn\Desktop\reddit api\`.

---

## Disabled Components

Three neural learning components exist but are disabled:

| Component | File | Activation Threshold | Current State |
|-----------|------|---------------------|---------------|
| Neural Router | `dashboard/neural_router.py` | 50 routing log entries | Collecting data |
| Learned Reranker | `dashboard/reranker.py` | 200 feedback entries | Needs quality data |
| Embedding Adapter | `dashboard/adapter.py` | 50 feedback pairs | Wrong training signal |

**Neural Router:** MLP classifier (384-dim input, 128 hidden, N output classes).
Trains on routing_log table. Falls back to keyword router when confidence < 75%.

**Reranker:** Logistic regression on 6 features per chunk. Blends 70% learned
score with 30% original. Trains on chunk_effectiveness data.

**Adapter:** 384 -> 64 -> 384 bottleneck with residual. Contrastive loss on
(query, helpful_chunk, unhelpful_chunk) triples. Currently trains on domain
clustering signal instead of relevance. Needs fix.

All three auto-activate when their thresholds are met via TrainingOrchestrator.

---

## CLI Reference

```bash
# Session startup
python scripts/bootstrap.py [--quick]       # Generate SESSION_CONTEXT.md

# Knowledge ingestion
python scripts/ingest.py reddit [--dry-run] # Process Reddit saves to chunks
python scripts/ingest.py brainfeed          # Sync Brain Feed D1 chunks
python scripts/ingest.py all                # All sources
python scripts/ingest.py status             # Pending ingestion stats
python scripts/ingest.py pipeline           # Full 5-stage: collect -> extract -> enrich -> reindex -> improve

# Self-improvement pipeline (individual stages)
python scripts/collect_reddit.py            # Expanded Reddit collection (saves + upvotes + comments)
python scripts/extract_claims.py            # Claude API claim extraction from collected posts
python scripts/enrich_domains.py            # Compare claims to domains, propose additions
python scripts/improve.py                   # Analyze pipeline output, find gaps and actions

# Search and retrieval
python -m retrieval search "query" [-k 10] [--domain X] [--bm25-only]
python -m retrieval expand "query" [--llm]  # Multi-query expansion
python -m retrieval context "query" [--budget 4000]

# Index management
python -m retrieval index [--full]          # Build/rebuild
python -m retrieval stats                   # Index statistics
python -m retrieval graph build             # Domain relationship graph
python -m retrieval graph show              # View graph hubs
python -m retrieval graph neighbors --domain X [--hops 2]

# Feedback and gaps
python -m retrieval feedback add --chunk-id X --query "Y" --rating 1
python -m retrieval feedback stats
python -m retrieval gaps domains            # Domain difficulty ranking
python -m retrieval gaps queries            # Hardest recent queries

# Visualization
python -m retrieval viz [--open]            # Knowledge graph HTML

# Dashboard
python -m retrieval.serve [--port 8600]     # Launch web dashboard

# Maintenance
python scripts/maintain.py [--full]         # Index + graph + validation
python scripts/reindex.py                   # Force reindex
```

---

## Deployment

**Local (primary):** Claude Code reads CLAUDE.md on session start. Dashboard
at port 8600. No server required for core functionality.

**Fly.io (optional):** Dashboard deployable via `fly deploy`. App name
`neural-net-dashboard`, region sjc. BM25-only in production (no PyTorch).
256MB RAM, auto-scale to zero.

**Cloudflare Workers:** Two workers deployed via `npx wrangler deploy`.
Custom domains bypass workers.dev blocking from China.

---

## Constraints

**Hardware:** HP OMEN, 16GB RAM, ~4GB free. No parallel heavy processes.
Prefer sequential over concurrent for compute tasks. Canvas over SVG for
rendering. Static layouts over force simulations.

**Network:** China-based. workers.dev domains blocked. All external APIs
must use custom domains or proxy bypass. Set `trust_env=False` on HTTP
clients. Set `HF_HUB_OFFLINE=1` to prevent model downloads at runtime.

**Token budget:** Tier 1 loads ROUTER.md only. Tier 2 adds one domain file.
Tier 3 adds context chunks, AGENTS.md, and supporting domains. Minimum
viable context, always.
