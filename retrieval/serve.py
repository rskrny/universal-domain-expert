"""
Lightweight dashboard server for the knowledge retrieval system.

Serves the dashboard UI and exposes REST API endpoints for:
- Search with feedback
- Domain graph exploration
- Knowledge gap analysis
- Stats and health monitoring

Launch: python -m retrieval.serve
         python -m retrieval.serve --port 8600
"""

import json
import os
import sys
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

# Fix Windows console encoding
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from retrieval.config import RetrievalConfig
from retrieval.store import Store


def _get_config() -> RetrievalConfig:
    config_path = ROOT / "retrieval" / "config.yaml"
    if config_path.exists():
        config = RetrievalConfig.from_yaml(config_path)
    else:
        config = RetrievalConfig()
    config.knowledge_root = ROOT
    config.store_dir = ROOT / "retrieval" / "store"
    config.db_path = config.store_dir / "metadata.db"
    return config


# Lazy-loaded searcher (heavy, only init when needed)
_searcher = None


def _get_searcher():
    global _searcher
    if _searcher is None:
        from retrieval.searcher import Searcher
        _searcher = Searcher(_get_config())
    return _searcher


class DashboardHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the dashboard."""

    def log_message(self, format, *args):
        """Suppress default logging noise."""
        pass

    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _send_html(self, filepath):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(filepath.read_bytes())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == "/" or path == "/index.html":
            ui_path = ROOT / "retrieval" / "ui" / "index.html"
            if ui_path.exists():
                self._send_html(ui_path)
            else:
                self._send_json({"error": "UI not found"}, 404)

        elif path == "/api/search":
            query = params.get("q", [""])[0]
            top_k = int(params.get("k", ["10"])[0])
            domain = params.get("domain", [None])[0]
            expand = params.get("expand", ["false"])[0] == "true"

            if not query:
                self._send_json({"results": [], "count": 0})
                return

            searcher = _get_searcher()

            if expand:
                from retrieval.query_expander import search_with_expansion
                results = search_with_expansion(
                    searcher, query, top_k=top_k, domain_filter=domain
                )
            else:
                results = searcher.search(
                    query=query, top_k=top_k, domain_filter=domain
                )

            self._send_json({
                "results": [
                    {
                        "chunk_id": r.chunk_id,
                        "text": r.text[:500],
                        "full_text": r.text,
                        "source_file": r.source_file,
                        "header_path": r.header_path,
                        "domain": r.domain,
                        "tags": r.tags,
                        "score": round(r.score, 5),
                        "context_label": r.context_label,
                        "bm25_rank": r.bm25_rank,
                        "semantic_rank": r.semantic_rank,
                    }
                    for r in results
                ],
                "count": len(results),
                "query": query,
                "expanded": expand,
            })

        elif path == "/api/stats":
            config = _get_config()
            store = Store(config.db_path, config.store_dir)
            agg = store.get_aggregate_stats()
            feedback_count = store.feedback_count()
            routing_count = store.routing_log_count()
            store.close()

            self._send_json({
                **agg,
                "feedback_count": feedback_count,
                "routing_log_count": routing_count,
                "neural_router_ready": routing_count >= 50,
            })

        elif path == "/api/gaps":
            config = _get_config()
            store = Store(config.db_path, config.store_dir)
            domain_stats = store.get_domain_difficulty_stats()
            hard_queries = store.get_hard_queries(min_difficulty=0.5, limit=20)
            store.close()

            self._send_json({
                "domain_difficulty": domain_stats,
                "hard_queries": hard_queries,
            })

        elif path == "/api/graph":
            from retrieval.domain_graph import get_graph_summary
            config = _get_config()
            summary = get_graph_summary(config)
            self._send_json(summary)

        elif path == "/api/graph/neighbors":
            domain = params.get("domain", [""])[0]
            hops = int(params.get("hops", ["1"])[0])
            if not domain:
                self._send_json({"error": "domain required"}, 400)
                return
            from retrieval.domain_graph import get_adjacent_domains
            config = _get_config()
            neighbors = get_adjacent_domains(config, domain, hops=hops)
            self._send_json({"domain": domain, "hops": hops, "neighbors": neighbors})

        elif path == "/api/domains":
            config = _get_config()
            store = Store(config.db_path, config.store_dir)
            domains = store.list_domains()
            store.close()
            self._send_json({"domains": sorted(domains)})

        elif path == "/api/feedback/stats":
            config = _get_config()
            store = Store(config.db_path, config.store_dir)
            count = store.feedback_count()
            scores = store.get_chunk_feedback_scores()
            store.close()
            positive = sum(1 for v in scores.values() if v > 0)
            negative = sum(1 for v in scores.values() if v < 0)
            self._send_json({
                "total": count,
                "chunks_rated": len(scores),
                "positive": positive,
                "negative": negative,
            })

        elif path == "/api/reddit":
            # Serve Reddit saved posts analysis if available
            reddit_path = Path("C:/Users/rskrn/Desktop/reddit api/saved_posts_raw.json")
            if reddit_path.exists():
                posts = json.loads(reddit_path.read_text(encoding="utf-8"))
                # Last 30 days
                cutoff = time.time() - 30 * 86400
                recent = [p for p in posts if p.get("created_utc", 0) > cutoff]
                self._send_json({
                    "total_saved": len(posts),
                    "last_30_days": len(recent),
                    "recent": [
                        {
                            "title": p["title"][:120],
                            "subreddit": p["subreddit"],
                            "score": p["score"],
                            "url": p.get("permalink", ""),
                            "created_date": p.get("created_date", ""),
                        }
                        for p in sorted(recent, key=lambda x: x["created_utc"], reverse=True)[:20]
                    ],
                })
            else:
                self._send_json({"total_saved": 0, "last_30_days": 0, "recent": []})

        else:
            self._send_json({"error": "not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        content_length = int(self.headers.get("Content-Length", 0))
        body = {}
        if content_length > 0:
            raw = self.rfile.read(content_length)
            body = json.loads(raw.decode("utf-8"))

        if path == "/api/feedback":
            chunk_id = body.get("chunk_id")
            query = body.get("query", "")
            rating = body.get("rating", 0)

            if not chunk_id or rating not in (-1, 1):
                self._send_json({"error": "chunk_id and rating (+1/-1) required"}, 400)
                return

            config = _get_config()
            store = Store(config.db_path, config.store_dir)
            store.add_feedback(chunk_id, query, rating)
            count = store.feedback_count()
            store.close()

            self._send_json({"recorded": True, "total_feedback": count})

        elif path == "/api/routing":
            query = body.get("query", "")
            domain = body.get("domain", "")
            confidence = body.get("confidence", 0.0)

            if not query or not domain:
                self._send_json({"error": "query and domain required"}, 400)
                return

            config = _get_config()
            store = Store(config.db_path, config.store_dir)
            store.log_routing(query, domain, confidence)
            count = store.routing_log_count()
            store.close()

            self._send_json({
                "logged": True,
                "total_entries": count,
                "neural_ready": count >= 50,
            })

        else:
            self._send_json({"error": "not found"}, 404)


def run(port=8600):
    print(f"\n  Knowledge Dashboard")
    print(f"  http://localhost:{port}")
    print(f"  Press Ctrl+C to stop\n")

    server = HTTPServer(("127.0.0.1", port), DashboardHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8600)
    args = parser.parse_args()
    run(args.port)
