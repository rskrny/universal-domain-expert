"""
MCP Server for the Context Engineering Retrieval System.

Exposes search, index, domain expertise, and stats as MCP tools
that Claude Code can call natively from ANY working directory.

Run with:
    python -m retrieval.mcp_server

Or add to your Claude Code global settings.json under mcpServers.

Path resolution order:
  1. KNOWLEDGE_ROOT environment variable (set in MCP config)
  2. cwd (if it contains retrieval/config.yaml)
  3. Script's parent directory (fallback)
"""

import json
import os
import sys
from pathlib import Path

from .config import RetrievalConfig


def _resolve_root() -> Path:
    """Find the knowledge base root directory.

    Checks in order:
      1. KNOWLEDGE_ROOT env var (explicit, always wins)
      2. Current working directory (if it has retrieval/config.yaml)
      3. This file's parent parent (retrieval/ -> project root)
    """
    env_root = os.environ.get("KNOWLEDGE_ROOT")
    if env_root:
        p = Path(env_root)
        if p.exists():
            return p

    cwd = Path.cwd()
    if (cwd / "retrieval" / "config.yaml").exists():
        return cwd

    return Path(__file__).resolve().parent.parent


def _get_config() -> RetrievalConfig:
    """Load config from the resolved knowledge root."""
    root = _resolve_root()
    config_path = root / "retrieval" / "config.yaml"
    if config_path.exists():
        config = RetrievalConfig.from_yaml(config_path)
    else:
        config = RetrievalConfig()
    config.knowledge_root = root
    config.store_dir = root / "retrieval" / "store"
    config.db_path = config.store_dir / "metadata.db"
    return config


def handle_search(params: dict) -> dict:
    """Search the knowledge base."""
    from .searcher import Searcher

    config = _get_config()
    searcher = Searcher(config)

    query = params.get("query", "")
    top_k = params.get("top_k", 10)
    domain = params.get("domain")
    bm25_only = params.get("bm25_only", False)

    if bm25_only:
        results = searcher.search_bm25_only(query, top_k=top_k)
    else:
        results = searcher.search(query=query, top_k=top_k, domain_filter=domain)

    searcher.close()

    return {
        "results": [
            {
                "text": r.text,
                "source_file": r.source_file,
                "header_path": r.header_path,
                "domain": r.domain,
                "tags": r.tags,
                "score": round(r.score, 4),
                "context_label": r.context_label,
            }
            for r in results
        ],
        "count": len(results),
        "query": query,
    }


def handle_index(params: dict) -> dict:
    """Rebuild the search index."""
    from .indexer import build_index

    config = _get_config()
    stats = build_index(config, verbose=False)
    return stats


def handle_stats(params: dict) -> dict:
    """Get index statistics."""
    from .searcher import Searcher

    config = _get_config()
    searcher = Searcher(config)
    stats = searcher.get_stats()
    searcher.close()
    return stats


def handle_get_context(params: dict) -> dict:
    """
    Retrieve context for a given query.

    Returns the top results formatted as a context block
    ready to inject into an LLM prompt.
    """
    from .searcher import Searcher

    config = _get_config()
    searcher = Searcher(config)

    query = params.get("query", "")
    max_tokens = params.get("max_tokens", 2000)
    domain = params.get("domain")

    results = searcher.search(query=query, top_k=20, domain_filter=domain)
    searcher.close()

    # Build context block within token budget
    context_parts = []
    token_count = 0

    for r in results:
        chunk_tokens = len(r.text) // 4
        if token_count + chunk_tokens > max_tokens:
            break

        context_parts.append(
            f"--- {r.context_label} (score: {r.score:.3f}) ---\n{r.text}"
        )
        token_count += chunk_tokens

    return {
        "context": "\n\n".join(context_parts),
        "sources": [r.source_file for r in results[:len(context_parts)]],
        "token_estimate": token_count,
        "chunks_used": len(context_parts),
    }


def handle_feedback(params: dict) -> dict:
    """Record feedback for a chunk."""
    from .store import Store

    config = _get_config()
    store = Store(config.db_path, config.store_dir)

    chunk_id = params.get("chunk_id")
    query = params.get("query", "")
    rating = params.get("rating", 0)

    if not chunk_id or rating not in (-1, 1):
        store.close()
        return {"error": "chunk_id and rating (+1 or -1) required"}

    store.add_feedback(chunk_id, query, rating)
    count = store.feedback_count()
    store.close()

    return {
        "recorded": True,
        "chunk_id": chunk_id,
        "rating": rating,
        "total_feedback_entries": count,
    }


def handle_log_routing(params: dict) -> dict:
    """Log a routing decision for neural router training."""
    from .store import Store

    config = _get_config()
    store = Store(config.db_path, config.store_dir)

    query = params.get("query", "")
    domain = params.get("domain", "")
    confidence = params.get("confidence", 0.0)

    if not query or not domain:
        store.close()
        return {"error": "query and domain required"}

    store.log_routing(query, domain, confidence)
    count = store.routing_log_count()
    store.close()

    return {
        "logged": True,
        "domain": domain,
        "total_routing_entries": count,
        "neural_router_threshold": 50,
        "ready_to_train": count >= 50,
    }


def handle_list_domains(params: dict) -> dict:
    """List all available domain expertise files."""
    root = _resolve_root()
    domains_dir = root / "prompts" / "domains"

    if not domains_dir.exists():
        return {"error": "domains directory not found", "root": str(root)}

    domains = []
    for f in sorted(domains_dir.glob("*.md")):
        name = f.stem
        first_line = ""
        try:
            with open(f, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line.startswith("# "):
                        first_line = line[2:].strip()
                        break
        except Exception:
            pass
        domains.append({"name": name, "title": first_line, "path": str(f)})

    return {"domains": domains, "count": len(domains)}


def handle_get_domain(params: dict) -> dict:
    """Load a domain expertise file by name."""
    root = _resolve_root()
    domain_name = params.get("domain", "").strip()

    if not domain_name:
        return {"error": "domain name required"}

    if not domain_name.endswith(".md"):
        domain_name += ".md"

    domain_path = root / "prompts" / "domains" / domain_name

    if not domain_path.exists():
        available = [f.stem for f in (root / "prompts" / "domains").glob("*.md")]
        return {
            "error": f"Domain file not found: {domain_name}",
            "available": available,
        }

    try:
        content = domain_path.read_text(encoding="utf-8")
        return {
            "domain": domain_path.stem,
            "content": content,
            "path": str(domain_path),
            "size_chars": len(content),
        }
    except Exception as e:
        return {"error": f"Failed to read domain file: {e}"}


def handle_route(params: dict) -> dict:
    """Classify a query by domain and complexity tier.

    Returns the recommended domain file(s) to load and the tier level.
    Uses keyword matching against the ROUTER.md domain registry.
    """
    root = _resolve_root()
    query = params.get("query", "").lower()

    if not query:
        return {"error": "query required"}

    router_path = root / "prompts" / "ROUTER.md"
    domains_dir = root / "prompts" / "domains"

    available_domains = [f.stem for f in domains_dir.glob("*.md")] if domains_dir.exists() else []

    scores = {}
    for domain in available_domains:
        keywords = domain.replace("-", " ").split()
        score = sum(1 for kw in keywords if kw in query)
        if score > 0:
            scores[domain] = score

    if not scores:
        return {
            "domain": None,
            "tier": 1,
            "confidence": 0.0,
            "message": "No domain match found. Consider creating a new domain file.",
            "available_domains": available_domains,
        }

    best_domain = max(scores, key=scores.get)
    confidence = min(scores[best_domain] / 3.0, 1.0)

    word_count = len(query.split())
    if word_count <= 15:
        tier = 1
    elif word_count <= 50:
        tier = 2
    else:
        tier = 3

    return {
        "domain": best_domain,
        "tier": tier,
        "confidence": round(confidence, 2),
        "domain_file": f"prompts/domains/{best_domain}.md",
        "all_matches": dict(sorted(scores.items(), key=lambda x: -x[1])[:5]),
    }


def handle_knowledge_gaps(params: dict) -> dict:
    """Get knowledge gap analysis."""
    from .store import Store

    config = _get_config()
    store = Store(config.db_path, config.store_dir)

    domain_stats = store.get_domain_difficulty_stats()
    hard_queries = store.get_hard_queries(min_difficulty=0.7, limit=10)
    store.close()

    return {
        "domain_difficulty": domain_stats,
        "hard_queries": hard_queries,
    }


# MCP protocol implementation (stdio JSON-RPC)

TOOLS = {
    "search_knowledge": {
        "description": (
            "Search the knowledge base using hybrid BM25 + semantic retrieval. "
            "Returns ranked chunks from the context engineering system."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language search query",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of results to return (default: 10)",
                    "default": 10,
                },
                "domain": {
                    "type": "string",
                    "description": "Filter results to a specific domain",
                },
                "bm25_only": {
                    "type": "boolean",
                    "description": "Use BM25 only (faster, no ML)",
                    "default": False,
                },
            },
            "required": ["query"],
        },
        "handler": handle_search,
    },
    "get_context": {
        "description": (
            "Retrieve relevant context for a query, formatted as a context block "
            "ready for LLM consumption. Respects a token budget."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What context do you need?",
                },
                "max_tokens": {
                    "type": "integer",
                    "description": "Maximum tokens in the context block (default: 2000)",
                    "default": 2000,
                },
                "domain": {
                    "type": "string",
                    "description": "Filter to a specific domain",
                },
            },
            "required": ["query"],
        },
        "handler": handle_get_context,
    },
    "rebuild_index": {
        "description": (
            "Rebuild the search index. Run this after adding new knowledge files."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
        "handler": handle_index,
    },
    "index_stats": {
        "description": "Get statistics about the current search index.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
        "handler": handle_stats,
    },
    "submit_feedback": {
        "description": (
            "Record positive (+1) or negative (-1) feedback for a retrieved chunk. "
            "Feedback trains the retrieval scoring system over time."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "chunk_id": {
                    "type": "integer",
                    "description": "The chunk ID to rate",
                },
                "query": {
                    "type": "string",
                    "description": "The query this chunk was retrieved for",
                },
                "rating": {
                    "type": "integer",
                    "description": "+1 for helpful, -1 for unhelpful",
                    "enum": [-1, 1],
                },
            },
            "required": ["chunk_id", "rating"],
        },
        "handler": handle_feedback,
    },
    "log_routing": {
        "description": (
            "Log a routing decision. Call this after classifying a request "
            "to accumulate training data for the neural router."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The user's query",
                },
                "domain": {
                    "type": "string",
                    "description": "The assigned domain",
                },
                "confidence": {
                    "type": "number",
                    "description": "Routing confidence (0.0-1.0)",
                },
            },
            "required": ["query", "domain"],
        },
        "handler": handle_log_routing,
    },
    "knowledge_gaps": {
        "description": (
            "Get knowledge gap analysis: which domains the system struggles with "
            "and which queries were hardest to answer."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
        "handler": handle_knowledge_gaps,
    },
    "list_domains": {
        "description": (
            "List all available domain expertise files in the knowledge system. "
            "Returns domain names, titles, and file paths."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
        "handler": handle_list_domains,
    },
    "get_domain_expertise": {
        "description": (
            "Load a domain expertise file by name. Returns the full content of "
            "the domain file including frameworks, quality standards, and anti-patterns. "
            "Use list_domains first to see available domains."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "description": (
                        "Domain name (e.g. 'software-dev', 'business-consulting'). "
                        "Use list_domains to see available names."
                    ),
                },
            },
            "required": ["domain"],
        },
        "handler": handle_get_domain,
    },
    "route_request": {
        "description": (
            "Classify a query by domain and complexity tier. Returns the recommended "
            "domain file to load and whether it needs Tier 1 (quick), Tier 2 (standard), "
            "or Tier 3 (full pipeline) treatment."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The user's request to classify",
                },
            },
            "required": ["query"],
        },
        "handler": handle_route,
    },
}


def _send(msg: dict):
    """Send a JSON-RPC message to stdout."""
    data = json.dumps(msg)
    sys.stdout.write(f"Content-Length: {len(data)}\r\n\r\n{data}")
    sys.stdout.flush()


def _read() -> dict:
    """Read a JSON-RPC message from stdin."""
    headers = {}
    while True:
        line = sys.stdin.readline()
        if line == "\r\n" or line == "\n":
            break
        if ":" in line:
            key, val = line.split(":", 1)
            headers[key.strip()] = val.strip()

    length = int(headers.get("Content-Length", 0))
    if length == 0:
        return {}
    body = sys.stdin.read(length)
    return json.loads(body)


def run_server():
    """Run the MCP server using stdio transport."""
    while True:
        try:
            msg = _read()
        except (EOFError, KeyboardInterrupt):
            break

        if not msg:
            break

        method = msg.get("method")
        msg_id = msg.get("id")
        params = msg.get("params", {})

        if method == "initialize":
            _send({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": "context-retrieval",
                        "version": "0.1.0",
                    },
                },
            })

        elif method == "notifications/initialized":
            pass  # no response needed

        elif method == "tools/list":
            tools_list = []
            for name, tool in TOOLS.items():
                tools_list.append({
                    "name": name,
                    "description": tool["description"],
                    "inputSchema": tool["inputSchema"],
                })
            _send({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"tools": tools_list},
            })

        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})

            if tool_name in TOOLS:
                try:
                    result = TOOLS[tool_name]["handler"](tool_args)
                    _send({
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {
                            "content": [{
                                "type": "text",
                                "text": json.dumps(result, indent=2),
                            }],
                        },
                    })
                except Exception as e:
                    _send({
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {
                            "content": [{
                                "type": "text",
                                "text": f"Error: {str(e)}",
                            }],
                            "isError": True,
                        },
                    })
            else:
                _send({
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {
                        "code": -32601,
                        "message": f"Unknown tool: {tool_name}",
                    },
                })


if __name__ == "__main__":
    run_server()
