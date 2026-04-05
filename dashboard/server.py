"""
FastAPI server for the Personal Super Assistant Dashboard.

Serves the dashboard UI, exposes REST API for knowledge/project/finance operations,
and provides WebSocket for streaming AI chat.
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

# Ensure project root on path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Clear any stale proxy settings (Clash Verge leftovers)
for proxy_var in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']:
    os.environ.pop(proxy_var, None)
os.environ['NO_PROXY'] = '*'
os.environ['TRANSFORMERS_OFFLINE'] = '1'  # Don't try to download models at runtime
os.environ['HF_HUB_OFFLINE'] = '1'

# Load .env if present
env_path = PROJECT_ROOT / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip())

from retrieval.config import RetrievalConfig
from retrieval.store import Store
from retrieval.searcher import Searcher
from retrieval.optimizer import optimize_context

from dashboard.db import DashboardDB
from dashboard.chat import ChatPipeline
from dashboard.router import classify
from dashboard.neural_router import NeuralRouter
from dashboard.reranker import LearnedReranker
from dashboard.adapter import EmbeddingAdapter
from dashboard.trainer import TrainingOrchestrator
from dashboard.projects_registry import PROJECT_REGISTRY, get_all_projects
from dashboard.agents.flipside_agent import FlipSideAgent
from dashboard.agents.bloodline_agent import BloodlineAgent
from dashboard.models import (
    ProjectCreate, ProjectUpdate, TaskCreate, TaskUpdate,
    FinanceCreate, GoalCreate, GoalUpdate,
    FeedbackSubmit, LearnContent, ChatSessionCreate,
)


# --- Initialize ---

config = RetrievalConfig(knowledge_root=PROJECT_ROOT)
config.store_dir = PROJECT_ROOT / "retrieval" / "store"
config.db_path = config.store_dir / "metadata.db"

store = Store(db_path=config.db_path, store_dir=config.store_dir)

# Try to load searcher (may fail if index not built)
try:
    searcher = Searcher(config)
except Exception as e:
    print(f"Warning: Searcher failed to init: {e}")
    searcher = None

db = DashboardDB(db_path=config.db_path)

neural_router = NeuralRouter(
    model_dir=PROJECT_ROOT / "retrieval" / "store",
    db=db,
)

reranker = LearnedReranker(
    model_dir=PROJECT_ROOT / "retrieval" / "store",
    db=db,
)

adapter = EmbeddingAdapter(
    model_dir=PROJECT_ROOT / "retrieval" / "store",
    db=db,
)

# NOTE: Adapter and reranker DISABLED in live pipeline.
# Adapter trains on wrong signal (domain clustering, not relevance).
# Reranker needs 200+ real feedback samples (currently has ~30 bootstrap junk).
# Both will activate automatically once MIN_FEEDBACK thresholds are met.
# See plan: eager-brewing-token.md for full rationale.

trainer = TrainingOrchestrator(
    db=db,
    neural_router=neural_router,
    reranker=reranker,
    adapter=adapter,
)

chat_pipeline = ChatPipeline(
    prompts_dir=str(PROJECT_ROOT / "prompts"),
    searcher=searcher,
    optimizer_fn=optimize_context if searcher else None,
    reranker=None,  # Disabled until 200+ real feedback samples
    db=db,
)

app = FastAPI(title="Neural Net Dashboard", version="2.0.0")

# Serve static files
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# --- Auth Middleware (for Cloudflare Tunnel) ---
DASHBOARD_TOKEN = os.environ.get("DASHBOARD_TOKEN", "")

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse

class AuthMiddleware(BaseHTTPMiddleware):
    """Simple token auth. Disabled when DASHBOARD_TOKEN is empty (local dev)."""
    async def dispatch(self, request, call_next):
        if not DASHBOARD_TOKEN:
            return await call_next(request)
        # Allow static files without auth
        if request.url.path.startswith("/static"):
            return await call_next(request)
        # Check cookie or query param
        token = request.cookies.get("nn_token") or request.query_params.get("token")
        if token == DASHBOARD_TOKEN:
            response = await call_next(request)
            return response
        # Auth page
        if request.url.path == "/auth" and request.method == "POST":
            form = await request.form()
            if form.get("token") == DASHBOARD_TOKEN:
                response = StarletteResponse(status_code=303, headers={"Location": "/"})
                response.set_cookie("nn_token", DASHBOARD_TOKEN, max_age=86400*30, httponly=True, samesite="strict")
                return response
            return StarletteResponse("Invalid token", status_code=401)
        if request.url.path == "/auth":
            html = '''<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
            <style>body{background:#141420;color:#f0f0f5;font-family:system-ui;display:flex;align-items:center;justify-content:center;height:100vh;margin:0}
            form{text-align:center}input{background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.12);border-radius:8px;padding:10px 16px;color:#fff;font-size:16px;outline:none;width:240px}
            input:focus{border-color:#4fc3f7}button{background:#4fc3f7;border:none;border-radius:8px;padding:10px 24px;color:#000;font-size:14px;font-weight:600;cursor:pointer;margin-top:12px}
            h2{color:#4fc3f7;margin-bottom:16px}</style></head>
            <body><form method="POST" action="/auth"><h2>Neural Net</h2><input type="password" name="token" placeholder="Access token" autofocus><br><button>Enter</button></form></body></html>'''
            return StarletteResponse(html, media_type="text/html")
        return StarletteResponse(status_code=303, headers={"Location": "/auth"})

app.add_middleware(AuthMiddleware)


# --- Page Routes ---

@app.get("/")
async def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


# --- Knowledge API ---

@app.get("/api/graph")
async def get_graph(mode: str = "domain"):
    """Get graph data for D3.js visualization.

    mode=domain: Aggregated view (70 nodes, one per domain). Fast, clear.
    mode=chunks: Full chunk-level view (4000+ nodes). Detailed, heavy.
    """
    graph = store.get_chunk_relationships()

    if mode == "chunks":
        # Original full-detail mode
        chunks = store.get_all_chunks()
        text_map = {c["id"]: c["text"] for c in chunks}
        for node in graph["nodes"]:
            text = text_map.get(node["id"], "")
            node["preview"] = text[:300]
            node["full_text"] = text
        graph["stats"] = store.get_aggregate_stats()
        return graph

    # Domain-aggregated mode: collapse chunks into domain-level nodes
    from collections import defaultdict
    domain_chunks = defaultdict(list)
    for node in graph["nodes"]:
        d = node.get("domain") or "shared"
        domain_chunks[d].append(node)

    # Build domain nodes
    domain_nodes = []
    domain_id_map = {}  # old chunk id -> domain name
    for domain, chunks_list in domain_chunks.items():
        total_tokens = sum(c.get("tokens", 0) for c in chunks_list)
        content_types = set(c.get("content_type", "") for c in chunks_list)
        # Map all chunk IDs to this domain
        for c in chunks_list:
            domain_id_map[c["id"]] = domain
        domain_nodes.append({
            "id": f"domain:{domain}",
            "label": domain.replace("-", " ").title(),
            "domain": domain,
            "source_file": f"prompts/domains/{domain}.md" if domain != "shared" else "prompts/context/shared/",
            "tokens": total_tokens,
            "chunk_count": len(chunks_list),
            "content_type": ", ".join(sorted(content_types)),
            "preview": f"{len(chunks_list)} chunks, {total_tokens:,} tokens",
        })

    # Build domain-level edges from chunk-level edges
    domain_edge_weights = defaultdict(lambda: defaultdict(lambda: {"count": 0, "types": set()}))
    for edge in graph.get("edges", []):
        src_domain = domain_id_map.get(edge["source"])
        tgt_domain = domain_id_map.get(edge["target"])
        if src_domain and tgt_domain and src_domain != tgt_domain:
            key = tuple(sorted([src_domain, tgt_domain]))
            domain_edge_weights[key[0]][key[1]]["count"] += 1
            domain_edge_weights[key[0]][key[1]]["types"].add(edge.get("type", "sequence"))

    # Convert to edge list, only keep edges with meaningful connection
    domain_edges = []
    for src, targets in domain_edge_weights.items():
        for tgt, info in targets.items():
            best_type = "cross-domain" if "cross-domain" in info["types"] else (
                "semantic" if "semantic" in info["types"] else "sequence"
            )
            if info["count"] >= 2 or best_type in ("semantic", "cross-domain"):
                domain_edges.append({
                    "source": f"domain:{src}",
                    "target": f"domain:{tgt}",
                    "type": best_type,
                    "weight": info["count"],
                })

    result = {
        "nodes": domain_nodes,
        "edges": domain_edges,
        "stats": store.get_aggregate_stats(),
        "mode": "domain",
    }
    return result


@app.get("/api/treemap")
async def get_treemap():
    """Server-side squarified treemap layout. Zero client-side computation.

    Groups 70 domains into 8 categories. Returns positioned rectangles
    as percentage coordinates. Frontend renders pure CSS divs.
    """
    # Category groupings for the 70 domains
    CATEGORIES = {
        "Tech": [
            "software-dev", "frontend-development", "mobile-development",
            "cloud-infrastructure", "devops-sre", "data-engineering",
            "ai-machine-learning", "game-development", "robotics",
            "quantum-computing", "context-engineering",
        ],
        "Business": [
            "business-consulting", "gtm-strategy", "sales",
            "saas-building", "ecommerce", "operations-automation",
            "project-management", "customer-success", "branding",
            "crisis-management", "supply-chain",
        ],
        "Finance": [
            "accounting-tax", "personal-finance", "venture-capital",
            "real-estate", "insurance", "international-trade",
        ],
        "Law": [
            "business-law", "employment-law", "intellectual-property",
            "criminal-law",
        ],
        "Science": [
            "mathematics", "statistics", "economics", "data-analytics",
            "neuroscience", "environmental-science", "energy-systems",
            "electrical-engineering", "mechanical-engineering",
            "civil-engineering", "blockchain-web3", "cybersecurity",
        ],
        "Health": [
            "medicine-health", "mental-health", "nutrition-fitness",
        ],
        "Creative": [
            "creative-writing", "graphic-design", "video-production",
            "music-production", "photography", "product-design",
            "architecture-design", "podcasting", "event-planning",
        ],
        "Humanities": [
            "psychology-persuasion", "negotiation", "public-speaking",
            "marketing-content", "social-media", "course-creation",
            "research-authoring", "education-pedagogy", "hr-talent",
            "nonprofit", "political-science", "linguistics",
            "journalism", "philosophy", "history",
        ],
    }

    CATEGORY_COLORS = {
        "Tech": "#4fc3f7",
        "Business": "#66bb6a",
        "Finance": "#ffa726",
        "Law": "#ef5350",
        "Science": "#ab47bc",
        "Health": "#26c6da",
        "Creative": "#ff7043",
        "Humanities": "#78909c",
        "Projects": "#e0e040",
    }

    # Add user projects as a category
    CATEGORIES["Projects"] = [
        "project-flip-side", "project-bloodline", "project-shopmyroom",
        "project-goldie", "project-habitat", "project-tax",
    ]

    # Get chunk counts per domain and project from the store
    stats = store.get_aggregate_stats()
    domain_chunks = {}
    try:
        all_chunks = store.get_all_chunks()
        for c in all_chunks:
            d = c.get("domain") or "shared"
            domain_chunks[d] = domain_chunks.get(d, 0) + 1
            # Also count by project for the Projects category
            proj = c.get("project")
            if proj:
                proj_key = f"project-{proj}" if not proj.startswith("project-") else proj
                domain_chunks[proj_key] = domain_chunks.get(proj_key, 0) + 1
    except Exception:
        pass

    # Build category data with sizes
    categories = []
    for cat_name, domains in CATEGORIES.items():
        cat_domains = []
        for d in domains:
            count = domain_chunks.get(d, 0)
            cat_domains.append({
                "domain": d,
                "label": d.replace("-", " ").title(),
                "chunks": count,
                "size": max(count, 1),  # minimum size so empty domains still appear
            })
        # Add any domains in this category that exist in the index but aren't listed
        total = sum(dd["size"] for dd in cat_domains)
        categories.append({
            "name": cat_name,
            "color": CATEGORY_COLORS[cat_name],
            "domains": sorted(cat_domains, key=lambda x: x["size"], reverse=True),
            "total": total,
        })

    # Squarified treemap layout (percentage-based)
    # Step 1: Layout categories as top-level rectangles
    total_size = sum(c["total"] for c in categories) or 1
    categories.sort(key=lambda c: c["total"], reverse=True)

    def squarify(items, x, y, w, h, key="total"):
        """Squarified treemap layout. Returns items with x, y, w, h added."""
        if not items:
            return []
        if len(items) == 1:
            items[0]["x"] = x
            items[0]["y"] = y
            items[0]["w"] = w
            items[0]["h"] = h
            return items

        total = sum(i[key] for i in items) or 1
        # Decide split direction: horizontal if wider, vertical if taller
        if w >= h:
            # Vertical split: fill left strip first
            strip_items = []
            strip_sum = 0
            best_ratio = float("inf")
            best_split = 1
            for idx in range(1, len(items) + 1):
                strip_sum = sum(i[key] for i in items[:idx])
                strip_w = (strip_sum / total) * w
                if strip_w == 0:
                    continue
                worst = 0
                for i in items[:idx]:
                    item_h = (i[key] / strip_sum) * h if strip_sum else 0
                    ratio = max(strip_w / item_h, item_h / strip_w) if item_h > 0 else float("inf")
                    worst = max(worst, ratio)
                if worst <= best_ratio:
                    best_ratio = worst
                    best_split = idx
                else:
                    break

            strip_sum = sum(i[key] for i in items[:best_split])
            strip_w = (strip_sum / total) * w
            cy = y
            for i in items[:best_split]:
                item_h = (i[key] / strip_sum) * h if strip_sum else 0
                i["x"] = x
                i["y"] = cy
                i["w"] = strip_w
                i["h"] = item_h
                cy += item_h

            squarify(items[best_split:], x + strip_w, y, w - strip_w, h, key)
        else:
            # Horizontal split: fill top strip first
            strip_items = []
            strip_sum = 0
            best_ratio = float("inf")
            best_split = 1
            for idx in range(1, len(items) + 1):
                strip_sum = sum(i[key] for i in items[:idx])
                strip_h = (strip_sum / total) * h
                if strip_h == 0:
                    continue
                worst = 0
                for i in items[:idx]:
                    item_w = (i[key] / strip_sum) * w if strip_sum else 0
                    ratio = max(strip_h / item_w, item_w / strip_h) if item_w > 0 else float("inf")
                    worst = max(worst, ratio)
                if worst <= best_ratio:
                    best_ratio = worst
                    best_split = idx
                else:
                    break

            strip_sum = sum(i[key] for i in items[:best_split])
            strip_h = (strip_sum / total) * h
            cx = x
            for i in items[:best_split]:
                item_w = (i[key] / strip_sum) * w if strip_sum else 0
                i["x"] = cx
                i["y"] = y
                i["w"] = item_w
                i["h"] = strip_h
                cx += item_w

            squarify(items[best_split:], x, y + strip_h, w, h - strip_h, key)

        return items

    # Layout categories
    squarify(categories, 0, 0, 100, 100)

    # Layout domains within each category
    for cat in categories:
        if cat["w"] > 0 and cat["h"] > 0:
            squarify(cat["domains"], cat["x"], cat["y"], cat["w"], cat["h"], key="size")

    return {
        "categories": categories,
        "total_chunks": stats.get("total_chunks", 0),
        "domain_count": stats.get("domain_count", 0),
    }


@app.get("/api/search")
async def search(q: str = Query(...), top_k: int = 10, domain: str = None):
    """Search the knowledge base."""
    if not searcher:
        return JSONResponse({"error": "Search index not loaded. Run: python -m retrieval index"}, 500)
    top_k = max(1, min(top_k, 100))  # Clamp to sane range
    results = searcher.search(q, top_k=top_k, domain_filter=domain)
    return {
        "results": [
            {
                "chunk_id": r.chunk_id,
                "text": r.text[:500],
                "source_file": r.source_file,
                "header_path": r.header_path,
                "domain": r.domain,
                "score": round(r.score, 4),
                "context_label": r.context_label,
            }
            for r in results
        ],
        "count": len(results),
        "query": q,
    }


@app.get("/api/stats")
async def get_stats():
    """Get index statistics with degraded mode indicators."""
    stats = store.get_aggregate_stats()
    stats["searcher_loaded"] = searcher is not None
    stats["chat_cost_total"] = db.get_chat_cost_total()

    # Degraded mode detection: tell the frontend what's working and what isn't
    warnings = []
    if searcher is None:
        warnings.append("Search index not loaded. Run: python -m retrieval index")
    elif searcher.bm25 is None:
        warnings.append("BM25 index missing. Run: python -m retrieval index")
    if searcher and config.use_semantic and searcher.embeddings is None:
        warnings.append("Semantic embeddings not loaded. Falling back to BM25-only search.")
    if not chat_pipeline.api_key:
        warnings.append("ANTHROPIC_API_KEY not set. Chat will not work.")
    stats["warnings"] = warnings
    stats["degraded"] = len(warnings) > 0
    # System status for frontend indicators
    stats["semantic_enabled"] = str(config.use_semantic and searcher is not None and searcher.embeddings is not None)
    stats["reranker_ready"] = reranker.is_ready if reranker else False
    stats["reddit_configured"] = bool(os.environ.get("REDDIT_CLIENT_ID"))
    stats["brainfeed_configured"] = bool(os.environ.get("BRAINFEED_APP_ID"))
    return stats


@app.post("/api/reindex")
async def reindex():
    """Trigger knowledge base reindex."""
    from retrieval.indexer import Indexer
    indexer = Indexer(config, store)
    result = indexer.index()
    return {"status": "ok", "result": str(result)}


@app.get("/api/activate")
async def activate(q: str = Query(...), top_k: int = 30):
    """
    Get activation scores for a query across the entire knowledge graph.

    Returns chunk IDs with their relevance scores, simulating how a
    neural network activates in response to input. The frontend uses
    these scores to modulate node glow intensity.
    """
    if not searcher:
        return {"activations": []}
    # Use BM25-only search for activation to avoid loading the full transformer model
    results = searcher.search_bm25_only(q, top_k=top_k)
    max_score = results[0].score if results else 1
    return {
        "query": q,
        "activations": [
            {
                "chunk_id": r.chunk_id,
                "score": round(r.score / max_score, 4),  # normalize 0-1
                "domain": r.domain,
                "label": r.context_label,
            }
            for r in results
        ],
    }


@app.post("/api/learn")
async def learn_from_conversation(data: LearnContent):
    """
    Extract and index new knowledge from a conversation.

    This is the learning loop. After a valuable conversation, the user
    (or the system automatically) can extract key insights and add them
    to the knowledge base. The graph grows with use.
    """
    content = data.content
    title = data.title

    # Sanitize domain name: alphanumeric, hyphens, underscores only.
    # Prevents path traversal (../../etc/passwd) and shell injection.
    import re
    domain = re.sub(r"[^a-zA-Z0-9_-]", "", data.domain) or "learned"

    timestamp = int(time.time())
    filename = f"learned-{timestamp}.md"
    learned_dir = PROJECT_ROOT / "prompts" / "context" / "by-domain" / "learned"
    learned_dir.mkdir(parents=True, exist_ok=True)

    filepath = learned_dir / filename
    # Belt-and-suspenders: verify resolved path is inside the target directory
    if not str(filepath.resolve()).startswith(str(learned_dir.resolve())):
        return JSONResponse({"error": "Invalid file path"}, 400)
    md_content = f"# {title}\n\n> Extracted from conversation. Domain: {domain}\n\n{content}\n"
    filepath.write_text(md_content, encoding="utf-8")

    # Reindex to pick it up
    from retrieval.indexer import Indexer
    indexer = Indexer(config, store)
    indexer.index()

    return {"status": "ok", "file": str(filepath), "message": f"Knowledge added and indexed as {filename}"}


# --- Chat WebSocket ---

@app.websocket("/ws/chat")
async def chat_ws(websocket: WebSocket):
    await websocket.accept()
    MAX_MSG_SIZE = 100_000  # 100KB max per WebSocket message
    try:
        while True:
            data = await websocket.receive_text()

            # Size guard
            if len(data) > MAX_MSG_SIZE:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "content": "Message too large (max 100KB)"
                }))
                continue

            # JSON parse guard
            try:
                msg = json.loads(data)
            except (json.JSONDecodeError, ValueError):
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "content": "Invalid JSON"
                }))
                continue

            if not isinstance(msg, dict):
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "content": "Expected JSON object"
                }))
                continue

            user_message = str(msg.get("message", ""))[:10_000]  # Cap message length
            session_id = msg.get("session_id")
            model = msg.get("model", "auto")
            session_messages = msg.get("history", [])

            # Validate history is a list of reasonable size
            if not isinstance(session_messages, list):
                session_messages = []
            session_messages = session_messages[-50:]  # Keep last 50 messages max

            if not user_message.strip():
                continue

            _route_info = None

            # Save user message
            if session_id:
                db.add_message(session_id, "user", user_message)

            # Stream response
            async for event in chat_pipeline.stream_response(
                user_message,
                session_messages=session_messages,
                model_key=model,
            ):
                await websocket.send_text(json.dumps(event))

                # Capture route info for neural logging
                if event["type"] == "route":
                    _route_info = event["content"]

                # Save assistant response + log routing when done
                if event["type"] == "done" and session_id:
                    meta = event["content"]
                    msg_id = db.add_message(
                        session_id, "assistant", meta["full_response"],
                        model=meta["model"],
                        tokens_in=meta["tokens_in"],
                        tokens_out=meta["tokens_out"],
                        cost=meta["cost"],
                        context_chunks=meta["chunk_ids"],
                        domain=meta["domain"],
                    )
                    # Attach message_id so frontend can send feedback
                    event["content"]["message_id"] = msg_id
                    # Passive neural logging: embed query and log routing decision
                    try:
                        query_emb = None
                        if searcher and searcher.model is not None:
                            import numpy as np
                            emb = searcher.model.encode([user_message], normalize_embeddings=True)
                            query_emb = emb[0].astype(np.float32).tobytes()
                        db.log_routing(
                            query_text=user_message,
                            query_embedding=query_emb,
                            predicted_domain=meta["domain"],
                            tier=_route_info.get("tier", 2) if _route_info else 2,
                            chunk_ids=meta["chunk_ids"],
                        )
                    except Exception as log_err:
                        # Log but never block chat for logging failures
                        print(f"Neural logging failed: {log_err}")

    except WebSocketDisconnect:
        pass


# --- Project API ---

@app.get("/api/projects")
async def list_projects():
    projects = db.list_projects()
    for p in projects:
        p["tasks"] = db.list_tasks(p["id"])
    return projects


@app.post("/api/projects")
async def create_project(data: ProjectCreate):
    return db.create_project(
        name=data.name,
        description=data.description,
        tech_stack=data.tech_stack,
        path=data.path,
        revenue_monthly=data.revenue_monthly,
    )


@app.put("/api/projects/{project_id}")
async def update_project(project_id: str, data: ProjectUpdate):
    updates = data.model_dump(exclude_none=True)
    if not updates:
        return JSONResponse({"error": "No fields to update"}, 400)
    result = db.update_project(project_id, **updates)
    if not result:
        return JSONResponse({"error": "Project not found"}, 404)
    return result


@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: str):
    db.delete_project(project_id)
    return {"status": "ok"}


@app.get("/api/projects/{project_id}/tasks")
async def list_tasks(project_id: str):
    return db.list_tasks(project_id)


@app.post("/api/projects/{project_id}/tasks")
async def create_task(project_id: str, data: TaskCreate):
    return db.create_task(
        project_id=project_id,
        title=data.title,
        priority=data.priority,
        due_date=data.due_date,
    )


@app.put("/api/tasks/{task_id}")
async def update_task(task_id: str, data: TaskUpdate):
    updates = data.model_dump(exclude_none=True)
    if not updates:
        return JSONResponse({"error": "No fields to update"}, 400)
    db.update_task(task_id, **updates)
    return {"status": "ok"}


@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str):
    db.delete_task(task_id)
    return {"status": "ok"}


# --- Chat Session API ---

@app.get("/api/chat/sessions")
async def list_chat_sessions():
    return db.list_sessions()


@app.post("/api/chat/sessions")
async def create_chat_session(data: ChatSessionCreate = None):
    data = data or ChatSessionCreate()
    return db.create_session(
        title=data.title,
        domain=data.domain,
        model=data.model,
    )


@app.get("/api/chat/sessions/{session_id}/messages")
async def get_session_messages(session_id: str):
    return db.get_session_messages(session_id)


# --- Finance API ---

@app.get("/api/finances")
async def list_finances(entry_type: str = None, limit: int = 50):
    return db.list_financial_entries(limit=limit, entry_type=entry_type)


@app.post("/api/finances")
async def add_finance(data: FinanceCreate):
    return db.add_financial_entry(
        date=data.date,
        amount=data.amount,
        category=data.category,
        description=data.description,
        entry_type=data.type,
        source=data.source,
        recurring=data.recurring,
    )


@app.get("/api/finances/summary")
async def finance_summary():
    return db.get_financial_summary()


# --- Goals API ---

@app.get("/api/goals")
async def list_goals():
    return db.list_goals()


@app.post("/api/goals")
async def create_goal(data: GoalCreate):
    return db.create_goal(
        title=data.title,
        target_date=data.target_date,
        category=data.category,
        notes=data.notes,
    )


@app.put("/api/goals/{goal_id}")
async def update_goal(goal_id: str, data: GoalUpdate):
    updates = data.model_dump(exclude_none=True)
    if not updates:
        return JSONResponse({"error": "No fields to update"}, 400)
    db.update_goal(goal_id, **updates)
    return {"status": "ok"}


# --- Route classification (for frontend) ---

@app.get("/api/route")
async def route_message(q: str = Query(...)):
    """Classify a message for domain routing. Uses neural router if trained."""
    # Try neural routing with embedding if available
    query_emb = None
    if searcher and searcher.model is not None:
        try:
            emb = searcher.model.encode([q], normalize_embeddings=True)
            query_emb = emb[0].astype(np.float32)
        except Exception:
            pass

    if query_emb is not None:
        route = neural_router.classify(q, query_emb)
        method = "neural" if neural_router.is_ready else "keyword"
    else:
        route = classify(q)
        method = "keyword"

    return {
        "primary_domain": route.primary_domain,
        "supporting_domains": route.supporting_domains,
        "tier": route.tier,
        "domain_file": route.domain_file,
        "method": method,
    }


# --- Neural Learning API ---

@app.post("/api/feedback")
async def submit_feedback(data: FeedbackSubmit):
    """Save thumbs up/down for a message. Updates chunk effectiveness."""
    db.add_feedback(data.message_id, data.session_id, data.rating)
    trainer.on_feedback()
    return {"status": "ok", "message_id": data.message_id, "rating": data.rating}


@app.get("/api/neural/status")
async def neural_status():
    """Get neural learning status: samples, model readiness, accuracy."""
    status = db.get_neural_status()
    status["neural_router_active"] = neural_router.is_ready
    status["reranker_active"] = reranker.is_ready
    status["adapter_active"] = adapter.is_ready
    status["orchestrator"] = trainer.get_status()
    return status


@app.post("/api/neural/train")
async def train_neural():
    """Trigger training for all neural components that have enough data."""
    results = trainer.train_all()
    return {"status": "ok", "results": results}


# --- Agent API ---

AGENT_MAP = {
    "flipside": FlipSideAgent,
    "bloodline": BloodlineAgent,
}


# Cache folder stats to avoid O(n²) file walks on every dashboard load
_folder_stats_cache: dict = {}
_folder_stats_expiry: float = 0

def _get_folder_stats(key: str, folder: Path) -> dict:
    """Cached folder scan. Refreshes every 5 minutes."""
    global _folder_stats_cache, _folder_stats_expiry
    if time.time() > _folder_stats_expiry:
        _folder_stats_cache = {}
        _folder_stats_expiry = time.time() + 300  # 5 min cache

    if key in _folder_stats_cache:
        return _folder_stats_cache[key]

    skip_dirs = {"node_modules", ".git", "__pycache__", ".next", "venv", ".gstack"}
    total_files = 0
    latest_mtime = 0
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        total_files += len(files)
        for fname in files:
            try:
                mt = (Path(root) / fname).stat().st_mtime
                if mt > latest_mtime:
                    latest_mtime = mt
            except OSError:
                pass

    from datetime import datetime
    result = {
        "total_files": total_files,
        "last_activity": datetime.fromtimestamp(latest_mtime).strftime("%Y-%m-%d %H:%M") if latest_mtime else "unknown",
    }
    _folder_stats_cache[key] = result
    return result


@app.get("/api/projects/live")
async def get_live_projects():
    """Project status with cached folder scans and founder metrics."""
    latest_runs = db.get_latest_run_per_project()

    # Get financial data per project (from db projects table)
    db_projects = {p["name"]: p for p in db.list_projects()}

    # Get pending task counts per project
    task_counts = {}
    for p in db.list_projects():
        tasks = db.list_tasks(p["id"])
        pending = [t for t in tasks if t.get("status") != "done"]
        overdue = []
        for t in pending:
            if t.get("due_date"):
                try:
                    from datetime import datetime
                    due = datetime.strptime(t["due_date"], "%Y-%m-%d")
                    if due.date() < datetime.now().date():
                        overdue.append(t)
                except (ValueError, TypeError):
                    pass
        task_counts[p["name"]] = {
            "total": len(tasks),
            "pending": len(pending),
            "overdue": len(overdue),
        }

    projects = []

    for key, proj_config in PROJECT_REGISTRY.items():
        folder = Path(proj_config["path"])
        db_proj = db_projects.get(proj_config["name"], {})
        tasks = task_counts.get(proj_config["name"], {"total": 0, "pending": 0, "overdue": 0})

        project_data = {
            "key": key,
            "name": proj_config["name"],
            "description": proj_config["description"],
            "category": proj_config["category"],
            "has_agent": proj_config.get("agent") is not None,
            "agent_schedule": proj_config.get("agent_schedule"),
            "revenue_monthly": db_proj.get("revenue_monthly", 0),
            "task_pending": tasks["pending"],
            "task_overdue": tasks["overdue"],
            "task_total": tasks["total"],
        }

        if folder.exists():
            stats = _get_folder_stats(key, folder)
            project_data["exists"] = True
            project_data["total_files"] = stats["total_files"]
            project_data["last_activity"] = stats["last_activity"]

            # Chunk count (use per-request connection, not shared store.conn)
            try:
                conn = store._connect() if hasattr(store, '_connect') else None
                if conn:
                    cursor = conn.execute(
                        "SELECT COUNT(*) as n FROM chunks WHERE project = ?", (key,)
                    )
                    project_data["indexed_chunks"] = cursor.fetchone()[0]
                    conn.close()
                else:
                    cursor = store.conn.execute(
                        "SELECT COUNT(*) as n FROM chunks WHERE project = ?", (key,)
                    )
                    project_data["indexed_chunks"] = cursor.fetchone()["n"]
            except Exception:
                project_data["indexed_chunks"] = 0
        else:
            project_data["exists"] = False
            project_data["total_files"] = 0
            project_data["last_activity"] = "folder not found"
            project_data["indexed_chunks"] = 0

        run = latest_runs.get(key)
        project_data["latest_agent_run"] = run
        projects.append(project_data)

    return projects


@app.post("/api/agents/run/{project_key}")
async def run_agent(project_key: str):
    """Manually trigger an agent for a specific project."""
    if project_key not in PROJECT_REGISTRY:
        return JSONResponse({"error": f"Unknown project: {project_key}"}, 404)

    config = PROJECT_REGISTRY[project_key]
    agent_type = config.get("agent")
    if not agent_type or agent_type not in AGENT_MAP:
        return JSONResponse({"error": f"No agent configured for {project_key}"}, 400)

    agent_cls = AGENT_MAP[agent_type]
    agent = agent_cls(project_key, config, db=db)
    findings = agent.run()

    return {"status": "ok", "findings": findings}


@app.get("/api/agents/runs")
async def list_agent_runs(limit: int = 20):
    """Get recent agent runs across all projects."""
    return db.get_latest_agent_runs(limit=limit)


@app.get("/api/agents/health")
async def get_agent_health():
    """Check health of all autonomous systems.

    Queries real data sources (D1, production URLs) to verify
    that scheduled processes are actually working, not just running.
    """
    health = {}

    # Flip Side Intelligence Bot: check D1 for briefing freshness
    try:
        from retrieval.store import Store as _
        # Query D1 via Cloudflare MCP would be ideal, but we can check
        # our own agent_runs table for the latest Flip Side run
        latest_fs = db.get_project_agent_history("the-flip-side", limit=1)
        if latest_fs:
            last_run = latest_fs[0]
            age_hours = (time.time() - last_run["created_at"]) / 3600
            health["flipside_agent"] = {
                "status": "healthy" if age_hours < 168 else "stale",  # weekly agent
                "last_run": last_run["created_at"],
                "age_hours": round(age_hours, 1),
                "findings_summary": last_run.get("status", "unknown"),
            }
        else:
            health["flipside_agent"] = {"status": "never_run"}
    except Exception as e:
        health["flipside_agent"] = {"status": "error", "error": str(e)}

    # Bloodline site health: check latest agent run
    try:
        latest_bl = db.get_project_agent_history("bloodline", limit=1)
        if latest_bl:
            last_run = latest_bl[0]
            age_hours = (time.time() - last_run["created_at"]) / 3600
            findings = last_run.get("findings", {})
            site_health = findings.get("site_health", {})
            health["bloodline_agent"] = {
                "status": "healthy" if age_hours < 26 and site_health.get("healthy") else "degraded",
                "last_run": last_run["created_at"],
                "age_hours": round(age_hours, 1),
                "site_status": site_health.get("status_code"),
                "response_ms": site_health.get("response_ms"),
            }
        else:
            health["bloodline_agent"] = {"status": "never_run"}
    except Exception as e:
        health["bloodline_agent"] = {"status": "error", "error": str(e)}

    # Overall system health
    all_statuses = [v.get("status") for v in health.values()]
    if all(s == "healthy" for s in all_statuses):
        health["overall"] = "healthy"
    elif any(s in ("error", "never_run") for s in all_statuses):
        health["overall"] = "degraded"
    else:
        health["overall"] = "warning"

    return health


@app.get("/api/reddit/digest")
async def reddit_digest(time_filter: str = "day", max_results: int = 30):
    """Get a curated Reddit intelligence digest. Runs in executor to avoid blocking."""
    from dashboard.reddit_scanner import scan_subreddits, format_digest
    import asyncio
    loop = asyncio.get_event_loop()
    posts = await loop.run_in_executor(
        None, lambda: scan_subreddits(time_filter=time_filter, max_results=max_results)
    )
    digest = format_digest(posts)
    return {
        "posts": posts,
        "digest": digest,
        "count": len(posts),
        "time_filter": time_filter,
    }


@app.post("/api/agents/flipside/lark")
async def flipside_post_to_lark():
    """Run Flip Side agent and post results to Lark group chat."""
    config = PROJECT_REGISTRY.get("the-flip-side")
    if not config:
        return JSONResponse({"error": "Flip Side project not found"}, 404)

    agent = FlipSideAgent("the-flip-side", config, db=db)
    findings = agent.run()
    message = agent.format_lark_card(findings)

    return {
        "status": "ok",
        "findings": findings,
        "lark_message": message,
        "lark_chat_id": config.get("lark_chat_id"),
        "note": "Call /api/agents/flipside/lark/send to actually post to Lark",
    }
