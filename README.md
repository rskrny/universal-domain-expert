# Universal Domain Expert System

A modular prompt architecture that turns any LLM into a domain expert with
hybrid knowledge retrieval, token-optimized context delivery, and an
interactive knowledge graph.

One system. Unlimited domains. Expert-level output.

---

## Quick Start (5 minutes)

### With Claude Code (easiest)

1. Clone this repo
2. `python scripts/setup.py` (installs retrieval engine, builds search index)
3. Open the folder in Claude Code
4. Talk to it

Claude Code auto-reads `CLAUDE.md`, which bootstraps the entire system.
Ask it anything and the router automatically loads the right domain expertise.

### Lite mode (no ML dependencies)

```bash
python scripts/setup.py --lite
```

This installs only BM25 keyword search (250KB). Skips PyTorch and the
embedding model. Good for quick starts or constrained environments.

### With ChatGPT / Other LLMs

1. Copy the contents of `prompts/ROUTER.md` into your system prompt
2. When the router identifies a domain, paste the relevant file from `prompts/domains/`
3. For complex work, also paste `prompts/AGENTS.md` for the execution pipeline
4. Use `python -m retrieval context "your query"` to get pre-optimized context blocks

### With Claude API / OpenAI API

```python
# Load the router as your system prompt
with open("prompts/ROUTER.md") as f:
    system_prompt = f.read()

# Load domain files based on routing decisions
with open("prompts/domains/business-consulting.md") as f:
    domain_prompt = f.read()

# Combine for the API call
messages = [
    {"role": "system", "content": system_prompt + "\n\n" + domain_prompt},
    {"role": "user", "content": user_request}
]
```

---

## What This System Does

### Prompt Architecture

1. **A universal execution pipeline** (`AGENTS.md`). 8 stages that apply to any
   domain: define the problem, design the approach, scope the work, create
   deliverables, review, validate, plan delivery, deliver.

2. **Domain expertise files** (`domains/`). Deep, framework-rich instruction files
   that make the LLM operate at the level of a senior professional. Real frameworks,
   real quality standards, real anti-patterns.

3. **A routing layer** (`ROUTER.md`). Automatically classifies your request by
   domain and complexity, loads only what's needed, prevents wasting tokens.

4. **Session continuity** (`state/HANDOFF.md`). Save your progress and resume
   in a new session without losing context.

5. **A template for creating new domains** (`TEMPLATE.md`). Deep research and
   structured creation for any professional domain.

### Knowledge Retrieval Engine

6. **Hybrid search** (BM25 + semantic). Reciprocal rank fusion combines keyword
   precision with conceptual understanding.

7. **Multi-format ingestion**. Markdown, Python, JavaScript, TypeScript, Go, Rust,
   Java, HTML, CSV, JSON, YAML, PDF, DOCX. Fence-aware chunking that never
   splits code blocks or tables.

8. **Token budget optimization**. MMR-based selection with information density
   scoring. Maximizes signal-to-noise ratio within fixed context windows.
   Based on Shannon's channel capacity applied to LLM context.

9. **Incremental indexing with deduplication**. File hash tracking means only
   changed files get re-indexed. SHA-256 content hashing prevents duplicate chunks.

10. **Interactive knowledge graph**. D3.js force-directed visualization showing
    chunks, domains, and relationships. Search, zoom, hover for previews.

11. **MCP server**. Native Claude Code integration via `search_knowledge`,
    `get_context`, `rebuild_index`, and `index_stats` tools.

---

## Retrieval Commands

```bash
# Setup
python scripts/setup.py                # Full install (BM25 + semantic)
python scripts/setup.py --lite         # BM25 only (no ML dependencies)

# Index management
python -m retrieval index              # Incremental reindex
python -m retrieval index --full       # Full rebuild

# Search
python -m retrieval search "query"     # Hybrid search
python -m retrieval search "q" -k 5 --domain business-consulting
python -m retrieval search "q" --bm25-only

# Optimized context for LLM injection
python -m retrieval context "query"    # Default 4000 token budget
python -m retrieval context "query" --budget 2000

# Visualization
python -m retrieval viz                # Generate knowledge graph HTML
python -m retrieval viz --open         # Generate and open in browser

# Statistics
python -m retrieval stats
```

---

## Available Domains

| Domain | File | Expertise |
|--------|------|-----------|
| Business Consulting | `business-consulting.md` | McKinsey/BCG-caliber strategy, operations, org design, growth, M&A |
| Context Engineering | `context-engineering.md` | Information theory, RAG architecture, retrieval science, token optimization |

---

## How It Works

### The Three-Layer Architecture

```
Layer 1: Router (lightweight, always loaded)
    classifies request by domain + complexity
Layer 2: Domain Expert (loaded on-demand)
    provides frameworks, quality standards, expertise
Layer 3: Context Chunks (retrieved by search engine or loaded manually)
    deep reference material for complex engagements
```

This layered approach means you're never burning tokens loading irrelevant domains.
A quick tax question doesn't load the consulting file. A complex strategy
engagement doesn't load accounting frameworks it doesn't need.

### Complexity Tiers

| Tier | When | What Loads | Effort |
|------|------|-----------|--------|
| Tier 1 | Quick questions, definitions | Router only | Seconds |
| Tier 2 | Analysis, single deliverable | Router + domain file | Minutes |
| Tier 3 | Complex multi-part projects | Router + domain + retrieved context | 15-60+ min |

### The Pipeline

Every piece of work flows through 8 stages:

1. **Define the Challenge**. What exactly needs to be solved?
2. **Design the Approach**. How will we solve it? Which frameworks?
3. **Structure the Engagement**. Break into tasks, assign execution methods.
4. **Create Deliverables**. Build the actual work product.
5. **Quality Assurance**. Review against domain quality standards.
6. **Validate & Stress-Test**. Pressure-test assumptions and edge cases.
7. **Plan Delivery**. How does this get to the stakeholder?
8. **Deliver**. Execute delivery, confirm, identify follow-ups.

---

## Session Continuity

Work that spans multiple sessions doesn't lose context.

**To save:** Tell the AI "save state" or "update handoff" at any point. It writes
a structured snapshot to `state/HANDOFF.md`.

**To resume:** In a new session, @ reference `state/HANDOFF.md` or say "pick up
where we left off." The AI reads the snapshot and resumes with full context.

---

## Creating New Domain Files

1. Read `prompts/TEMPLATE.md`
2. Research the domain deeply:
   - Foundational theory and first principles
   - Core frameworks that top practitioners actually use
   - Quality standards that separate expert from amateur work
   - Common failure modes and anti-patterns
   - Ethical and legal boundaries
3. Create a new file in `prompts/domains/{domain-name}.md`
4. Register it in `prompts/ROUTER.md` (add to the Domain Registry table)
5. Run `python -m retrieval index` to add it to the search index
6. Test with a quick question (Tier 1), a standard analysis (Tier 2), and a
   complex engagement (Tier 3)

---

## Project Structure

```
.
CLAUDE.md                          # LLM bootstrap (auto-loaded by Claude Code)
README.md                          # You are here
state/
  HANDOFF.md                       # Session state (save/resume)
  HANDOFF-PROTOCOL.md              # Rules for saving/loading state
prompts/
  ROUTER.md                        # Request classifier + routing
  AGENTS.md                        # Universal 8-stage execution pipeline
  TEMPLATE.md                      # Template for creating new domain files
  domains/                         # One file per domain
    business-consulting.md         # Strategy, ops, org design
    context-engineering.md         # Retrieval science, info theory
  context/                         # Knowledge base (loaded on-demand)
    INDEX.md                       # Manifest of all knowledge chunks
    shared/                        # Cross-domain frameworks
    by-domain/                     # Domain-specific reference material
  workflows/                       # Execution protocols
    tiers.md                       # Complexity tier definitions
    multi-domain.md                # Cross-domain coordination
retrieval/                         # Knowledge retrieval engine
  config.yaml                      # Settings (editable)
  chunker.py                       # Multi-format, fence-aware chunking
  indexer.py                       # Incremental index builder with dedup
  searcher.py                      # Hybrid BM25 + semantic search
  optimizer.py                     # Token budget optimizer (MMR + density)
  store.py                         # SQLite with WAL + file hash tracking
  visualize.py                     # D3.js knowledge graph generator
  cli.py                           # CLI interface
  mcp_server.py                    # MCP server for Claude Code
  requirements.txt                 # Python dependencies
  knowledge-graph.html             # Generated interactive visualization
  store/                           # Generated indexes (gitignored)
scripts/
  setup.py                         # First-time install + index build
  reindex.py                       # Rebuild indexes
```

---

## Architecture Deep Dive

### Why This Architecture?

**Problem:** Most AI prompt systems are monolithic. One giant system prompt tries
to cover everything. This wastes tokens, creates confused outputs when domains
conflict, and makes it impossible to maintain quality as the system grows.

**Solution:** Separation of concerns.
- The **pipeline** (AGENTS.md) provides structure. It never changes per domain.
- The **domain files** provide substance. Deep expertise for one field.
- The **router** decides what to load. Preventing token waste.
- The **retrieval system** finds relevant context. Scales to thousands of files.
- The **handoff system** provides continuity. State that survives sessions.

### Design Principles

1. **Load only what you need.** The router exists so you never load all domain
   files for a single request. Token efficiency is a first-class concern.

2. **Domain files are self-contained.** Each domain file works independently.
   You can use `business-consulting.md` without any other file if you want.

3. **The pipeline is domain-agnostic.** "Write code" and "write a market analysis"
   are both instances of "create deliverables." The pipeline doesn't care what
   domain it's operating in.

4. **Context is retrieved, not dumped.** The retrieval system finds the minimum
   information needed to maximally reduce uncertainty. Information density per
   token matters more than total volume.

5. **Everything is portable.** Plain markdown files plus a Python retrieval engine.
   Works with any LLM that can read text. The retrieval system is optional.
   The prompt architecture works standalone.

### Extending the System

**Adding a new domain:** Follow `TEMPLATE.md`. Register in `ROUTER.md`. Run
`python -m retrieval index`. Done.

**Adding shared knowledge:** Create a new file in `prompts/context/shared/`.
Register in `prompts/context/INDEX.md`. Run `python -m retrieval index`.

**Adding domain-specific reference material:** Create files in
`prompts/context/by-domain/{domain}/`. Register in INDEX.md. Reindex.

**Modifying the pipeline:** Edit `AGENTS.md`. Changes apply to all domains
automatically. Be careful. This is the most load-bearing file in the system.

---

## Contributing

1. **New domain files** are the highest-impact contribution. Pick a professional
   domain, research it deeply using TEMPLATE.md, and submit a PR.

2. **Quality standards matter.** Domain files should be at the level of a senior
   professional with 20+ years of experience. Real frameworks, real anti-patterns,
   real quality standards.

3. **Test your domain file** against Tier 1, 2, and 3 requests before submitting.

4. **Keep it self-contained.** The prompt architecture has zero dependencies.
   The retrieval system requires Python 3.9+ and pip.

---

## License

[TBD]
