# Context Knowledge Base -- Index

> This file is a manifest of all available context chunks. The Router loads this
> file to determine which chunks to pull into a session. Context chunks are
> loaded on-demand, never all at once.
>
> **For large knowledge bases (100+ files),** use the retrieval system instead
> of scanning this index manually:
> `python -m retrieval search "your query"` or the `search_knowledge` MCP tool.
>
> **Format:** Each entry lists the chunk file, its domain scope, and a one-line
> description of what it contains.

---

## Shared Context (cross-domain)

These chunks contain frameworks and knowledge applicable across multiple domains.
Load when the domain file references them or when working across domains.

| File | Description | Load When |
|------|-------------|-----------|
| `shared/writing-style.md` | Hard rules: no semicolons, no em dashes, no AI slop, banned phrases list | ALWAYS. Referenced by AGENTS.md at Stage 4 and Stage 5. Non-negotiable. |
| `shared/mental-models.md` | First principles, systems thinking, inversion, second-order effects | Complex strategic decisions in any domain |
| `shared/communication-frameworks.md` | Pyramid Principle detail, SCQA, Minto, storytelling structures | Any deliverable requiring structured communication |

---

## Domain-Specific Context

These chunks contain deep reference material for specific domains.
Load only when working within that domain AND the depth requires it.

**Current state:** Domain files are self-sufficient for Tier 1-2 work. Context
chunks below will be created as Tier 3 engagements demand deeper reference material.

### Business Consulting
| File | Description | Load When |
|------|-------------|-----------|
| (create as needed) | Industry benchmarks, M&A data, operational metrics | Industry-specific Tier 3 engagements |

### Context Engineering
| File | Description | Load When |
|------|-------------|-----------|
| (create as needed) | Embedding model benchmarks, retrieval evaluation datasets | Deep retrieval system tuning |

### GTM Strategy
| File | Description | Load When |
|------|-------------|-----------|
| (create as needed) | Channel benchmarks, CAC by industry, launch case studies | Tier 3 launch planning |

### Software Development
| File | Description | Load When |
|------|-------------|-----------|
| (create as needed) | Architecture decision records, technology benchmarks | System design engagements |

### Business Law
| File | Description | Load When |
|------|-------------|-----------|
| (create as needed) | Contract templates, regulatory checklists by jurisdiction | Contract review or compliance work |

### Accounting & Tax
| File | Description | Load When |
|------|-------------|-----------|
| (create as needed) | Tax brackets, GAAP standards reference, SaaS metrics benchmarks | Financial modeling or tax planning |

### Course Creation
| File | Description | Load When |
|------|-------------|-----------|
| (create as needed) | Platform comparison data, completion rate benchmarks | Course design Tier 3 |

### Research & Authorship
| File | Description | Load When |
|------|-------------|-----------|
| (create as needed) | Journal databases, citation style guides, statistical test selection | Academic writing Tier 3 |

### Product Design & UX
| File | Description | Load When |
|------|-------------|-----------|
| (create as needed) | Heuristic evaluation templates, accessibility checklists, component libraries | Design audit Tier 3 |

### Data Analytics
| File | Description | Load When |
|------|-------------|-----------|
| (create as needed) | SQL patterns, statistical test reference, dashboard design templates | Analytics Tier 3 |

### Marketing & Content
| File | Description | Load When |
|------|-------------|-----------|
| (create as needed) | SEO keyword research data, email sequence templates, content calendars | Marketing execution Tier 3 |

### Psychology & Persuasion
| File | Description | Load When |
|------|-------------|-----------|
| (create as needed) | Bias catalog, pricing experiment case studies, conversion benchmarks | Conversion optimization Tier 3 |

### Operations & Automation
| File | Description | Load When |
|------|-------------|-----------|
| (create as needed) | SOP templates, tool comparison matrices, automation cost calculators | Operations design Tier 3 |

---

## Context Lifecycle

1. **Creation:** Context chunks are created when a domain file needs deeper reference
   material than what fits in the domain file itself. The domain file should be
   self-sufficient for Tier 1-2 work. Context chunks enable Tier 3 depth.

2. **Loading:** The Router decides which chunks to load based on the request classification.
   For small knowledge bases, load manually from this index.
   For large knowledge bases (100+ files), use the retrieval engine:
   - CLI: `python -m retrieval context "query" --budget 2000`
   - MCP: `get_context` tool with query and max_tokens
   Rule: never load more than 3 context chunks per request.

3. **Indexing:** After creating or modifying context files, run
   `python scripts/maintain.py` to update the search index and knowledge graph.

4. **Updating:** Context chunks should be updated when the information they contain
   becomes outdated. Date-stamp all data-heavy chunks.

5. **Archiving:** Move outdated chunks to `context/archive/` rather than deleting them.
