"""
Persistence layer with WAL mode, file tracking, and deduplication.

SQLite for metadata. File-based storage for BM25 and embeddings.
WAL mode for safe concurrent reads during MCP server operation.
"""

import json
import sqlite3
import pickle
from pathlib import Path
from typing import Optional
from functools import lru_cache

from .chunker import Chunk


class Store:
    """SQLite-backed storage with concurrency safety."""

    def __init__(self, db_path: Path, store_dir: Path):
        self.db_path = Path(db_path)
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(
            str(self.db_path),
            timeout=30,  # wait up to 30s for locks
        )
        self.conn.row_factory = sqlite3.Row
        # WAL mode: allows concurrent reads during writes
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=30000")
        self._init_schema()

    def _init_schema(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                source_file TEXT NOT NULL,
                header_path TEXT,
                chunk_index INTEGER,
                start_line INTEGER,
                end_line INTEGER,
                content_type TEXT DEFAULT 'prose',
                domain TEXT,
                project TEXT,
                tags TEXT,
                token_estimate INTEGER,
                content_hash TEXT
            );

            CREATE TABLE IF NOT EXISTS file_hashes (
                file_path TEXT PRIMARY KEY,
                hash TEXT NOT NULL,
                last_indexed REAL
            );

            CREATE TABLE IF NOT EXISTS index_meta (
                key TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chunk_id INTEGER NOT NULL,
                query_hash TEXT NOT NULL,
                query_text TEXT,
                rating INTEGER NOT NULL,
                created_at REAL NOT NULL,
                FOREIGN KEY (chunk_id) REFERENCES chunks(id)
            );

            CREATE TABLE IF NOT EXISTS difficulty_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query_text TEXT NOT NULL,
                query_hash TEXT NOT NULL,
                top_score REAL,
                score_gap REAL,
                result_count INTEGER,
                domain TEXT,
                difficulty_score REAL,
                created_at REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_chunks_source ON chunks(source_file);
            CREATE INDEX IF NOT EXISTS idx_chunks_domain ON chunks(domain);
            CREATE INDEX IF NOT EXISTS idx_chunks_hash ON chunks(content_hash);
            CREATE INDEX IF NOT EXISTS idx_chunks_type ON chunks(content_type);
            CREATE INDEX IF NOT EXISTS idx_feedback_chunk ON feedback(chunk_id);
            CREATE INDEX IF NOT EXISTS idx_feedback_query ON feedback(query_hash);
            CREATE INDEX IF NOT EXISTS idx_difficulty_domain ON difficulty_log(domain);

            CREATE TABLE IF NOT EXISTS enrichment_cache (
                chunk_id INTEGER PRIMARY KEY,
                enriched_text TEXT NOT NULL,
                created_at REAL NOT NULL,
                FOREIGN KEY (chunk_id) REFERENCES chunks(id)
            );
        """)
        self.conn.commit()
        # Migration: ensure routing_log table has the right schema
        try:
            self.conn.execute("SELECT assigned_domain FROM routing_log LIMIT 1")
        except sqlite3.OperationalError:
            # Table either doesn't exist or has different columns
            try:
                self.conn.execute("""
                    CREATE TABLE IF NOT EXISTS routing_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        query_text TEXT NOT NULL,
                        assigned_domain TEXT NOT NULL,
                        confidence REAL,
                        user_corrected INTEGER DEFAULT 0,
                        corrected_domain TEXT,
                        created_at REAL NOT NULL
                    )
                """)
                self.conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_routing_log_domain ON routing_log(assigned_domain)"
                )
                self.conn.commit()
            except sqlite3.OperationalError:
                pass  # Table exists with incompatible schema, skip routing features

        # Migration: add project column if it doesn't exist (for existing databases)
        try:
            self.conn.execute("SELECT project FROM chunks LIMIT 1")
        except sqlite3.OperationalError:
            self.conn.execute("ALTER TABLE chunks ADD COLUMN project TEXT")
            self.conn.commit()
        # Create project index (safe to run after migration)
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_project ON chunks(project)")
        self.conn.commit()

    # --- Chunk operations ---

    def clear_chunks(self):
        self.conn.execute("DELETE FROM chunks")
        self.conn.execute("DELETE FROM file_hashes")
        self.conn.commit()

    def insert_chunks(self, chunks: list[Chunk]):
        rows = []
        for c in chunks:
            rows.append((
                c.text,
                c.source_file,
                json.dumps(c.header_path),
                c.chunk_index,
                c.start_line,
                c.end_line,
                c.content_type,
                c.domain,
                getattr(c, "project", None),
                json.dumps(c.tags),
                len(c.text) // 4,
                c.content_hash,
            ))
        self.conn.executemany(
            """INSERT INTO chunks
               (text, source_file, header_path, chunk_index, start_line,
                end_line, content_type, domain, project, tags, token_estimate, content_hash)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        self.conn.commit()

    def delete_chunks_by_file(self, file_path: str):
        self.conn.execute("DELETE FROM chunks WHERE source_file = ?", (file_path,))
        self.conn.commit()

    def get_all_chunks(self) -> list[dict]:
        cursor = self.conn.execute(
            "SELECT id, text, source_file, header_path, chunk_index, "
            "start_line, end_line, content_type, domain, project, tags, "
            "token_estimate, content_hash FROM chunks ORDER BY id"
        )
        results = []
        for row in cursor:
            results.append({
                "id": row["id"],
                "text": row["text"],
                "source_file": row["source_file"],
                "header_path": json.loads(row["header_path"] or "[]"),
                "chunk_index": row["chunk_index"],
                "start_line": row["start_line"],
                "end_line": row["end_line"],
                "content_type": row["content_type"] or "prose",
                "domain": row["domain"],
                "project": row["project"],
                "tags": json.loads(row["tags"] or "[]"),
                "token_estimate": row["token_estimate"],
                "content_hash": row["content_hash"] or "",
            })
        return results

    def get_all_chunk_hashes(self) -> set[str]:
        cursor = self.conn.execute(
            "SELECT DISTINCT content_hash FROM chunks WHERE content_hash IS NOT NULL"
        )
        return {row["content_hash"] for row in cursor}

    def get_chunks_by_ids(self, chunk_ids: list[int]) -> list[dict]:
        if not chunk_ids:
            return []
        placeholders = ",".join("?" for _ in chunk_ids)
        cursor = self.conn.execute(
            f"SELECT * FROM chunks WHERE id IN ({placeholders})", chunk_ids
        )
        results = {}
        for row in cursor:
            results[row["id"]] = {
                "id": row["id"],
                "text": row["text"],
                "source_file": row["source_file"],
                "header_path": json.loads(row["header_path"] or "[]"),
                "chunk_index": row["chunk_index"],
                "start_line": row["start_line"],
                "end_line": row["end_line"],
                "content_type": row["content_type"] or "prose",
                "domain": row["domain"],
                "tags": json.loads(row["tags"] or "[]"),
                "token_estimate": row["token_estimate"],
                "content_hash": row["content_hash"] or "",
            }
        return [results[cid] for cid in chunk_ids if cid in results]

    def chunk_count(self) -> int:
        cursor = self.conn.execute("SELECT COUNT(*) as cnt FROM chunks")
        return cursor.fetchone()["cnt"]

    def list_domains(self) -> list[str]:
        cursor = self.conn.execute(
            "SELECT DISTINCT domain FROM chunks WHERE domain IS NOT NULL"
        )
        return [row["domain"] for row in cursor]

    def list_source_files(self) -> list[str]:
        cursor = self.conn.execute("SELECT DISTINCT source_file FROM chunks")
        return [row["source_file"] for row in cursor]

    def list_content_types(self) -> dict[str, int]:
        cursor = self.conn.execute(
            "SELECT content_type, COUNT(*) as cnt FROM chunks GROUP BY content_type"
        )
        return {row["content_type"]: row["cnt"] for row in cursor}

    # --- File hash tracking (for incremental indexing) ---

    def get_file_hashes(self) -> dict[str, str]:
        cursor = self.conn.execute("SELECT file_path, hash FROM file_hashes")
        return {row["file_path"]: row["hash"] for row in cursor}

    def set_file_hash(self, file_path: str, file_hash: str):
        import time
        self.conn.execute(
            "INSERT OR REPLACE INTO file_hashes (file_path, hash, last_indexed) "
            "VALUES (?, ?, ?)",
            (file_path, file_hash, time.time()),
        )
        self.conn.commit()

    # --- Index persistence ---

    def save_bm25(self, bm25_obj):
        path = self.store_dir / "bm25_index.pkl"
        with open(path, "wb") as f:
            pickle.dump(bm25_obj, f)

    def load_bm25(self):
        path = self.store_dir / "bm25_index.pkl"
        if not path.exists():
            return None
        with open(path, "rb") as f:
            return pickle.load(f)

    def save_embeddings(self, embeddings):
        import numpy as np
        path = self.store_dir / "embeddings.npy"
        np.save(str(path), embeddings)

    def load_embeddings(self):
        import numpy as np
        path = self.store_dir / "embeddings.npy"
        if not path.exists():
            return None
        return np.load(str(path))

    # --- Metadata ---

    def set_meta(self, key: str, value: str):
        self.conn.execute(
            "INSERT OR REPLACE INTO index_meta (key, value) VALUES (?, ?)",
            (key, value),
        )
        self.conn.commit()

    def get_meta(self, key: str) -> Optional[str]:
        cursor = self.conn.execute(
            "SELECT value FROM index_meta WHERE key = ?", (key,)
        )
        row = cursor.fetchone()
        return row["value"] if row else None

    # --- Aggregate statistics (for dashboard) ---

    def get_aggregate_stats(self) -> dict:
        """
        Compute aggregate statistics across the knowledge base.
        Returns tokens by domain, by file, content type distribution,
        and summary totals.
        """
        stats = {}

        # Tokens by domain
        cursor = self.conn.execute(
            "SELECT COALESCE(domain, 'shared') as domain, "
            "SUM(token_estimate) as total_tokens, COUNT(*) as chunk_count "
            "FROM chunks GROUP BY domain ORDER BY total_tokens DESC"
        )
        stats["tokens_by_domain"] = [
            {"domain": row["domain"], "tokens": row["total_tokens"], "chunks": row["chunk_count"]}
            for row in cursor
        ]

        # Tokens by file
        cursor = self.conn.execute(
            "SELECT source_file, COALESCE(domain, 'shared') as domain, "
            "SUM(token_estimate) as total_tokens, COUNT(*) as chunk_count "
            "FROM chunks GROUP BY source_file ORDER BY total_tokens DESC"
        )
        stats["tokens_by_file"] = [
            {"file": row["source_file"], "domain": row["domain"],
             "tokens": row["total_tokens"], "chunks": row["chunk_count"]}
            for row in cursor
        ]

        # Content type distribution
        cursor = self.conn.execute(
            "SELECT COALESCE(content_type, 'prose') as content_type, "
            "COUNT(*) as count, SUM(token_estimate) as tokens "
            "FROM chunks GROUP BY content_type ORDER BY count DESC"
        )
        stats["content_types"] = [
            {"type": row["content_type"], "count": row["count"], "tokens": row["tokens"]}
            for row in cursor
        ]

        # Totals
        cursor = self.conn.execute(
            "SELECT COUNT(*) as total_chunks, "
            "COALESCE(SUM(token_estimate), 0) as total_tokens, "
            "COALESCE(AVG(token_estimate), 0) as avg_tokens "
            "FROM chunks"
        )
        row = cursor.fetchone()
        stats["total_chunks"] = row["total_chunks"]
        stats["total_tokens"] = row["total_tokens"]
        stats["avg_tokens"] = round(row["avg_tokens"])

        # Domain count
        stats["domain_count"] = len([
            d for d in stats["tokens_by_domain"] if d["domain"] != "shared"
        ])

        # File count
        stats["file_count"] = len(stats["tokens_by_file"])

        return stats

    # --- Graph data (for visualization) ---

    def get_chunk_relationships(self, use_semantic_edges: bool = True) -> dict:
        """
        Extract relationships between chunks for knowledge graph viz.

        Three types of edges:
        1. sequence: Adjacent chunks within the same file (structural)
        2. semantic: Chunks with high embedding cosine similarity (intelligent)
        3. cross-domain: Semantic connections that cross domain boundaries (bridges)

        Semantic edges make the graph an actual neural network where connections
        represent meaning, not just file proximity.
        """
        chunks = self.get_all_chunks()
        nodes = []
        edges = []

        file_groups: dict[str, list[int]] = {}

        for c in chunks:
            nodes.append({
                "id": c["id"],
                "label": c["header_path"][-1] if c["header_path"] else c["source_file"],
                "source_file": c["source_file"],
                "domain": c["domain"],
                "content_type": c["content_type"],
                "tokens": c["token_estimate"],
                "header_path": c["header_path"],
                "tags": c["tags"],
                "start_line": c["start_line"],
                "end_line": c["end_line"],
                "content_hash": c["content_hash"],
            })
            file_groups.setdefault(c["source_file"], []).append(c["id"])

        # Structural edges (sequential chunks within a file)
        for file_path, chunk_ids in file_groups.items():
            for i in range(len(chunk_ids) - 1):
                edges.append({
                    "source": chunk_ids[i],
                    "target": chunk_ids[i + 1],
                    "type": "sequence",
                })

        # Semantic edges (real neural connections based on meaning)
        if use_semantic_edges:
            semantic_edges = self._compute_semantic_edges(chunks)
            edges.extend(semantic_edges)

        return {"nodes": nodes, "edges": edges}

    def _compute_semantic_edges(self, chunks: list[dict], threshold: float = 0.55,
                                 max_edges_per_node: int = 4) -> list[dict]:
        """
        Compute edges based on embedding cosine similarity.

        This is what makes the graph a real neural network. Each node connects
        to its most semantically similar nodes across the entire knowledge base.
        Cross-domain connections are especially valuable because they represent
        novel conceptual bridges.
        """
        import numpy as np

        embeddings = self.load_embeddings()
        if embeddings is None or len(embeddings) == 0:
            return []

        n = min(len(chunks), len(embeddings))
        if n == 0:
            return []

        # Normalize for cosine similarity
        norms = np.linalg.norm(embeddings[:n], axis=1, keepdims=True)
        norms[norms == 0] = 1
        normed = embeddings[:n] / norms

        # Compute similarity matrix
        sim_matrix = normed @ normed.T

        # Zero out self-similarity
        np.fill_diagonal(sim_matrix, 0)

        edges = []
        edge_set = set()

        for i in range(n):
            # Get top similar chunks for this node
            similarities = sim_matrix[i]
            top_indices = np.argsort(similarities)[::-1][:max_edges_per_node]

            for j in top_indices:
                if j >= n:
                    continue
                sim = float(similarities[j])
                if sim < threshold:
                    continue

                # Avoid duplicate edges
                edge_key = (min(chunks[i]["id"], chunks[j]["id"]),
                           max(chunks[i]["id"], chunks[j]["id"]))
                if edge_key in edge_set:
                    continue
                edge_set.add(edge_key)

                # Classify: cross-domain connections are conceptual bridges
                same_domain = chunks[i]["domain"] == chunks[j]["domain"]
                same_file = chunks[i]["source_file"] == chunks[j]["source_file"]

                if same_file:
                    continue  # Skip same-file connections (already have sequence edges)

                edge_type = "semantic" if same_domain else "cross-domain"

                edges.append({
                    "source": chunks[i]["id"],
                    "target": chunks[j]["id"],
                    "type": edge_type,
                    "weight": round(sim, 3),
                })

        return edges

    # --- Feedback operations ---

    def add_feedback(self, chunk_id: int, query_text: str, rating: int):
        """Record feedback (+1 or -1) for a chunk in response to a query."""
        import hashlib
        import time
        query_hash = hashlib.sha256(query_text.encode()).hexdigest()[:16]
        self.conn.execute(
            "INSERT INTO feedback (chunk_id, query_hash, query_text, rating, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (chunk_id, query_hash, query_text, rating, time.time()),
        )
        self.conn.commit()

    def get_chunk_feedback_scores(self) -> dict[int, float]:
        """Return average feedback score per chunk. Range: -1.0 to +1.0."""
        cursor = self.conn.execute(
            "SELECT chunk_id, AVG(rating) as avg_rating, COUNT(*) as cnt "
            "FROM feedback GROUP BY chunk_id HAVING cnt >= 1"
        )
        return {row["chunk_id"]: row["avg_rating"] for row in cursor}

    def feedback_count(self) -> int:
        cursor = self.conn.execute("SELECT COUNT(*) as cnt FROM feedback")
        return cursor.fetchone()["cnt"]

    # --- Routing log operations ---

    def log_routing(self, query_text: str, domain: str, confidence: float = 0.0):
        import time
        self.conn.execute(
            "INSERT INTO routing_log (query_text, assigned_domain, confidence, created_at) "
            "VALUES (?, ?, ?, ?)",
            (query_text, domain, confidence, time.time()),
        )
        self.conn.commit()

    def correct_routing(self, log_id: int, correct_domain: str):
        self.conn.execute(
            "UPDATE routing_log SET user_corrected = 1, corrected_domain = ? WHERE id = ?",
            (correct_domain, log_id),
        )
        self.conn.commit()

    def get_routing_training_data(self) -> list[dict]:
        """Get routing logs that have been user-corrected (for training)."""
        cursor = self.conn.execute(
            "SELECT query_text, corrected_domain as domain FROM routing_log "
            "WHERE user_corrected = 1 "
            "UNION ALL "
            "SELECT query_text, assigned_domain as domain FROM routing_log "
            "WHERE user_corrected = 0"
        )
        return [dict(row) for row in cursor]

    def routing_log_count(self) -> int:
        cursor = self.conn.execute("SELECT COUNT(*) as cnt FROM routing_log")
        return cursor.fetchone()["cnt"]

    # --- Difficulty log operations ---

    def log_difficulty(self, query_text: str, top_score: float, score_gap: float,
                       result_count: int, domain: str, difficulty_score: float):
        import hashlib
        import time
        query_hash = hashlib.sha256(query_text.encode()).hexdigest()[:16]
        self.conn.execute(
            "INSERT INTO difficulty_log "
            "(query_text, query_hash, top_score, score_gap, result_count, domain, difficulty_score, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (query_text, query_hash, top_score, score_gap, result_count, domain, difficulty_score, time.time()),
        )
        self.conn.commit()

    def get_hard_queries(self, min_difficulty: float = 0.7, limit: int = 20) -> list[dict]:
        """Return queries the system struggled with, grouped by domain."""
        cursor = self.conn.execute(
            "SELECT query_text, domain, difficulty_score, created_at "
            "FROM difficulty_log WHERE difficulty_score >= ? "
            "ORDER BY difficulty_score DESC LIMIT ?",
            (min_difficulty, limit),
        )
        return [dict(row) for row in cursor]

    def get_domain_difficulty_stats(self) -> list[dict]:
        """Average difficulty by domain. High = knowledge gaps."""
        cursor = self.conn.execute(
            "SELECT domain, AVG(difficulty_score) as avg_difficulty, "
            "COUNT(*) as query_count "
            "FROM difficulty_log GROUP BY domain "
            "ORDER BY avg_difficulty DESC"
        )
        return [dict(row) for row in cursor]

    # --- Enrichment cache ---

    def save_enriched_texts(self, enrichments: list[tuple[int, str]]):
        """Bulk save enriched texts. enrichments = [(chunk_id, enriched_text), ...]"""
        import time
        now = time.time()
        self.conn.executemany(
            "INSERT OR REPLACE INTO enrichment_cache (chunk_id, enriched_text, created_at) "
            "VALUES (?, ?, ?)",
            [(cid, text, now) for cid, text in enrichments],
        )
        self.conn.commit()

    def get_enriched_texts(self) -> dict[int, str]:
        """Return {chunk_id: enriched_text} for all cached enrichments."""
        cursor = self.conn.execute(
            "SELECT chunk_id, enriched_text FROM enrichment_cache"
        )
        return {row["chunk_id"]: row["enriched_text"] for row in cursor}

    def clear_enrichment_cache(self):
        """Clear all cached enrichments (e.g. before full reindex)."""
        self.conn.execute("DELETE FROM enrichment_cache")
        self.conn.commit()

    def close(self):
        self.conn.close()
