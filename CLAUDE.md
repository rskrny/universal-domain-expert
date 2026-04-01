# Project Bootstrap -- Universal Domain Expert System

> This file is the entry point. When you open this project, read this file first.
> It tells you how the system works and where everything lives.
>
> **Everything is self-contained in this folder.** Clone the repo, run setup,
> and it works. The retrieval system requires Python 3.9+ for indexing and search.

---

## Writing Rules (Non-Negotiable)

All written output follows `prompts/context/shared/writing-style.md`. Three hard rejections:
1. **Semicolons.** Never. Two sentences instead.
2. **Em dashes.** Never. Restructure the sentence.
3. **"Not X, but Y" contrast.** Never. Say what something IS. Skip what it isn't.

Anything that reads like AI-generated filler gets rewritten. No banned phrases, no
hedging, no performative depth. Short sentences. Concrete language. Say it like a
human who values the reader's time.

---

## Quick Start

**If you're an LLM reading this, do these two things before anything else:**

1. **Check for session state.** Read `state/HANDOFF.md`. If it has real content
   (not just the empty template), you have a prior session to resume. Briefly
   acknowledge what you're picking up and ask if anything has changed. Follow
   the protocol in `state/HANDOFF-PROTOCOL.md`.

2. **Route the request.** Load `prompts/ROUTER.md` and classify the user's request.
   The Router tells you what domain file(s) and context to load.

**The flow:**
1. Check `state/HANDOFF.md` -> resume if active, otherwise fresh start
2. Route via `prompts/ROUTER.md` -> picks domain file + complexity tier
3. Execute via `prompts/AGENTS.md` -> 8-stage pipeline
4. Domain expertise from `prompts/domains/{domain}.md`
5. Context retrieved via `retrieval/` system or loaded from `prompts/context/`

---

## System Architecture

```
CLAUDE.md                              <- You are here (bootstrap / LLM entry point)
README.md                              <- Human user guide
state/
  HANDOFF.md                           <- Session state transfer (save/resume)
  HANDOFF-PROTOCOL.md                  <- Rules for how to save/load state
prompts/
  ROUTER.md                            <- ALWAYS load first. Classifies requests.
  AGENTS.md                            <- Universal 8-stage execution pipeline
  TEMPLATE.md                          <- Use this to create new domain files
  domains/                             <- Domain expertise files (one per domain)
    business-consulting.md             <- Strategy, ops, org design, growth
    context-engineering.md             <- Retrieval science, info theory, RAG
  context/                             <- Retrievable knowledge chunks
    INDEX.md                           <- Manifest of all context chunks
    shared/                            <- Cross-domain frameworks
      mental-models.md                 <- First principles, systems thinking, etc.
      communication-frameworks.md      <- Pyramid Principle, SCQA, storytelling
      writing-style.md                 <- Hard rules for all written output
    by-domain/                         <- Domain-specific reference material
  workflows/                           <- Execution protocols
    tiers.md                           <- Tier 1/2/3 depth definitions
    multi-domain.md                    <- Cross-domain coordination protocol
retrieval/                             <- Knowledge retrieval engine
  config.yaml                          <- Retrieval settings (editable)
  config.py                            <- Config dataclass
  chunker.py                           <- Multi-format, fence-aware chunking
  indexer.py                           <- Incremental index builder with dedup
  searcher.py                          <- Hybrid BM25 + semantic search
  optimizer.py                         <- Token budget optimizer (MMR + density)
  store.py                             <- SQLite with WAL mode + file tracking
  visualize.py                         <- D3.js knowledge graph + token dashboard
  test_quality.py                      <- 30-test quality and correctness suite
  cli.py                               <- CLI: index, search, context, viz, stats, test
  mcp_server.py                        <- MCP server for Claude Code
  requirements.txt                     <- Python dependencies
  knowledge-graph.html                 <- Generated interactive visualization
  store/                               <- Generated indexes (gitignored)
scripts/
  setup.py                             <- First-time install + index build
  reindex.py                           <- Rebuild indexes after changes
```

---

## How It Works

### Knowledge Retrieval System

The retrieval engine finds relevant context from the knowledge base using
hybrid search. Two modes of operation:

**BM25-only (lite mode):** Keyword search. Zero ML dependencies. Install with
`python scripts/setup.py --lite`. Works anywhere Python 3.9+ runs.

**Full hybrid (BM25 + semantic):** Keyword search combined with embedding-based
semantic search using reciprocal rank fusion. Install with `python scripts/setup.py`.
Downloads ~80MB embedding model on first run. Requires PyTorch.

**Commands:**
```bash
python scripts/setup.py                # First-time setup (full mode)
python scripts/setup.py --lite         # BM25-only setup (no ML deps)

python -m retrieval index              # Incremental reindex (fast)
python -m retrieval index --full       # Full rebuild from scratch

python -m retrieval search "query"     # Hybrid search
python -m retrieval search "query" --bm25-only  # Keyword-only search
python -m retrieval search "query" --domain context-engineering

python -m retrieval context "query"    # Token-optimized context block
python -m retrieval context "query" --budget 2000

python -m retrieval viz                # Generate knowledge graph HTML
python -m retrieval viz --open         # Generate and open in browser

python -m retrieval stats              # Index statistics

python -m retrieval test               # Run 30-test quality suite
python -m retrieval test --verbose     # Verbose test output
```

**Key features:**
- **Multi-format ingestion.** Markdown, Python, JS, TS, Go, Rust, Java, HTML,
  CSV, JSON, YAML, PDF (via pymupdf/pdfplumber), DOCX (via python-docx).
- **Fence-aware chunking.** Never splits code blocks, tables, or blockquotes.
- **Incremental indexing.** Tracks file hashes. Only re-indexes changed files.
- **Content deduplication.** SHA-256 hash per chunk. Same content never stored twice.
- **Token budget optimization.** MMR-based selection maximizes information density
  per token using information-theoretic scoring.
- **SQLite with WAL mode.** Safe concurrent reads during MCP server operation.
- **Interactive knowledge graph.** D3.js force-directed visualization with clickable
  nodes, detail panel, domain/type filters, token sparkline, and minimap. Includes
  a token budget dashboard with bar charts, treemap, and donut chart.
- **Quality test suite.** 30 tests covering chunking, incremental indexing,
  deduplication, search relevance, token optimization, and visualization.
  Run with `python -m retrieval test`.

---

### MCP Server Setup (Claude Code)

To give Claude Code native access to the retrieval system, add this to your
`.claude/settings.json` under `mcpServers`:

```json
{
  "mcpServers": {
    "context-retrieval": {
      "command": "python",
      "args": ["-m", "retrieval.mcp_server"],
      "cwd": "/path/to/architecturecontextengineering"
    }
  }
}
```

This exposes four tools:
- `search_knowledge` -- hybrid search with optional domain filter
- `get_context` -- retrieve a token-budgeted context block for a query
- `rebuild_index` -- re-index after adding knowledge files
- `index_stats` -- check what's indexed

---

### The Three-Layer Architecture

**Layer 1 -- Router (lightweight, always loaded)**
`ROUTER.md` reads every request and classifies it by:
- Which domain(s) it belongs to
- How complex it is (Tier 1 = quick answer, Tier 2 = standard, Tier 3 = full engagement)
- What context chunks are needed

This layer is small by design. It decides what gets loaded so you never waste
context on irrelevant domain files.

**Layer 2 -- Domain Experts (loaded on-demand)**
Each file in `domains/` is a self-contained domain expertise prompt. It defines:
- Role and expertise level
- Core frameworks and mental models
- Quality standards and validation methods
- Communication norms
- Anti-patterns to avoid
- How to plug into each pipeline stage

Only the relevant domain file(s) get loaded per request.

**Layer 3 -- Context Chunks (retrieved selectively)**
Files in `context/` provide deeper reference material. For small knowledge bases
the LLM loads these on-demand from INDEX.md. For large knowledge bases (100+
files), the retrieval system searches and retrieves the most relevant chunks
programmatically.

### The Pipeline

Every piece of work flows through 8 stages defined in `AGENTS.md`:

1. **Define the Challenge** -- precise problem statement
2. **Design the Approach** -- select solution using domain frameworks
3. **Structure the Engagement** -- decompose into tasks
4. **Create Deliverables** -- build the work product
5. **Quality Assurance** -- review against domain standards
6. **Validate & Stress-Test** -- pressure-test the work
7. **Plan Delivery** -- determine how to deliver
8. **Deliver** -- execute delivery and confirm

The pipeline scales with complexity. Tier 1 runs implicitly in seconds.
Tier 3 runs explicitly with full rigor.

---

## Available Domains

| Domain | File | Expertise |
|--------|------|-----------|
| Business Consulting | `business-consulting.md` | Strategy, ops, org design, growth, M&A. McKinsey/BCG caliber. |
| Context Engineering | `context-engineering.md` | Retrieval science, information theory, RAG architecture, token optimization. |

---

## Creating New Domains

1. Read `prompts/TEMPLATE.md`
2. Research the domain deeply (theories, frameworks, quality standards, failure modes)
3. Create a new file in `prompts/domains/{domain-name}.md` following the template
4. Register the domain in `prompts/ROUTER.md` Domain Registry table
5. Create a context directory in `prompts/context/by-domain/{domain-name}/` if needed
6. Run `python -m retrieval index` to add the new domain to the search index
7. Test with Tier 1, 2, and 3 requests

---

## For Different LLM Platforms

This system is LLM-agnostic. The .md files are instruction sets that work with any
model that can read markdown. Integration varies by platform:

- **Claude Code:** This CLAUDE.md file is auto-loaded. Everything just works.
  Add the MCP server config above for native retrieval access.
- **Claude API / Other APIs:** Load ROUTER.md as a system prompt. Load domain files
  based on routing decisions. Use the retrieval CLI to get context blocks.
- **ChatGPT / Custom GPTs:** Use ROUTER.md + relevant domain file as custom instructions.
- **Other tools:** Load the relevant .md files into whatever context mechanism the
  tool provides. Use `python -m retrieval context "query"` to get pre-optimized
  context blocks for any platform.

The key insight: you don't need to load everything. Load ROUTER.md, let it classify,
then load only what's needed.

---

## Session Continuity

**Saving state:** When the user says "save state", "update handoff", or "save progress",
write current session context to `state/HANDOFF.md` following the protocol in
`state/HANDOFF-PROTOCOL.md`. For Tier 3 engagements, prompt the user to save at
major milestones.

**Resuming:** At session start, if `state/HANDOFF.md` has real content, briefly
acknowledge what you're resuming and ask if anything has changed before diving in.

---

## Project Knowledge Base

All persistent knowledge for this project lives within this folder:

- `prompts/context/shared/` -- Cross-domain knowledge (mental models, communication frameworks)
- `prompts/context/by-domain/` -- Domain-specific reference material
- `prompts/context/INDEX.md` -- Manifest of all available knowledge chunks
- `retrieval/` -- Programmatic search and retrieval engine
- `state/` -- Session state for cross-session continuity

No external file dependencies. No hidden state. Clone the repo and you have everything.
