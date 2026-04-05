"""
Extended database layer for the dashboard.

Adds tables for projects, chat, finances, and goals
to the existing retrieval system's metadata.db.
"""

import json
import logging
import re
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Optional

logger = logging.getLogger("dashboard.db")

# Column whitelists per table. Update methods reject any key not in these sets.
# This prevents SQL injection via column names passed through **kwargs.
_ALLOWED_COLUMNS = {
    "projects": {
        "name", "status", "description", "tech_stack",
        "revenue_monthly", "path", "updated_at",
    },
    "project_tasks": {
        "title", "status", "priority", "due_date",
    },
    "goals": {
        "title", "target_date", "progress", "category",
        "notes", "status", "updated_at",
    },
}


def _validate_update_kwargs(table: str, kwargs: dict) -> dict:
    """Filter kwargs to only allowed column names. Logs and drops invalid keys."""
    allowed = _ALLOWED_COLUMNS.get(table, set())
    clean = {}
    for k, v in kwargs.items():
        if k in allowed:
            clean[k] = v
        else:
            logger.warning("Rejected invalid column %r for table %r", k, table)
    return clean


class DashboardDB:
    """Dashboard-specific database operations. Shares metadata.db with retrieval.

    Uses per-call connections to avoid concurrent access issues with async FastAPI.
    WAL mode allows concurrent reads while a write is in progress.
    A threading lock serializes writes to prevent lost-update races.
    """

    def __init__(self, db_path: Path):
        self.db_path = str(Path(db_path))
        import threading
        self._write_lock = threading.Lock()
        # Run schema init with a temporary connection
        conn = self._connect()
        self._init_dashboard_schema(conn)
        conn.close()

    def _connect(self) -> sqlite3.Connection:
        """Create a new connection with standard pragmas."""
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_dashboard_schema(self, conn: sqlite3.Connection):
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                description TEXT,
                tech_stack TEXT,
                revenue_monthly REAL DEFAULT 0,
                path TEXT,
                created_at REAL,
                updated_at REAL
            );

            CREATE TABLE IF NOT EXISTS project_tasks (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                title TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                priority TEXT DEFAULT 'medium',
                due_date TEXT,
                created_at REAL,
                FOREIGN KEY (project_id) REFERENCES projects(id)
            );

            CREATE TABLE IF NOT EXISTS chat_sessions (
                id TEXT PRIMARY KEY,
                title TEXT,
                domain TEXT,
                model TEXT,
                created_at REAL,
                updated_at REAL
            );

            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                model TEXT,
                tokens_in INTEGER DEFAULT 0,
                tokens_out INTEGER DEFAULT 0,
                cost REAL DEFAULT 0,
                context_chunks TEXT,
                domain TEXT,
                created_at REAL,
                FOREIGN KEY (session_id) REFERENCES chat_sessions(id)
            );

            CREATE TABLE IF NOT EXISTS financial_entries (
                id TEXT PRIMARY KEY,
                date TEXT NOT NULL,
                category TEXT,
                description TEXT,
                amount REAL NOT NULL,
                type TEXT DEFAULT 'expense',
                source TEXT,
                recurring INTEGER DEFAULT 0,
                created_at REAL
            );

            CREATE TABLE IF NOT EXISTS goals (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                target_date TEXT,
                progress REAL DEFAULT 0,
                category TEXT,
                notes TEXT,
                status TEXT DEFAULT 'active',
                created_at REAL,
                updated_at REAL
            );

            CREATE INDEX IF NOT EXISTS idx_tasks_project ON project_tasks(project_id);
            CREATE INDEX IF NOT EXISTS idx_messages_session ON chat_messages(session_id);
            CREATE INDEX IF NOT EXISTS idx_financial_date ON financial_entries(date);

            -- Neural learning tables
            CREATE TABLE IF NOT EXISTS message_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER NOT NULL,
                session_id TEXT NOT NULL,
                rating INTEGER NOT NULL,
                created_at REAL
            );

            CREATE TABLE IF NOT EXISTS routing_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query_text TEXT,
                query_embedding BLOB,
                predicted_domain TEXT,
                actual_domain TEXT,
                tier INTEGER,
                chunk_ids TEXT,
                rating INTEGER,
                method TEXT DEFAULT 'keyword',
                created_at REAL
            );

            CREATE TABLE IF NOT EXISTS chunk_effectiveness (
                chunk_id INTEGER PRIMARY KEY,
                times_retrieved INTEGER DEFAULT 0,
                times_helpful INTEGER DEFAULT 0,
                effectiveness REAL DEFAULT 0.5,
                updated_at REAL
            );

            CREATE TABLE IF NOT EXISTS training_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                component TEXT NOT NULL,
                samples_used INTEGER,
                accuracy REAL,
                metrics TEXT,
                created_at REAL
            );

            -- Agent runs table (autonomous project agents)
            CREATE TABLE IF NOT EXISTS agent_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project TEXT NOT NULL,
                agent_type TEXT NOT NULL,
                status TEXT DEFAULT 'success',
                findings TEXT,
                created_at REAL
            );

            CREATE INDEX IF NOT EXISTS idx_feedback_message ON message_feedback(message_id);
            CREATE INDEX IF NOT EXISTS idx_routing_domain ON routing_log(predicted_domain);
            CREATE INDEX IF NOT EXISTS idx_training_component ON training_runs(component);
            CREATE INDEX IF NOT EXISTS idx_agent_runs_project ON agent_runs(project);
        """)
        conn.commit()

    # --- Helper: read and write patterns ---

    def _read(self, sql: str, params: tuple = ()) -> list[dict]:
        """Execute a read query, return list of dicts. Connection auto-closed."""
        conn = self._connect()
        try:
            return [dict(row) for row in conn.execute(sql, params)]
        finally:
            conn.close()

    def _read_one(self, sql: str, params: tuple = ()) -> Optional[dict]:
        """Execute a read query, return single dict or None."""
        conn = self._connect()
        try:
            row = conn.execute(sql, params).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def _write(self, statements: list[tuple], return_lastrowid: bool = False) -> Optional[int]:
        """Execute one or more write statements atomically under the write lock.

        statements: list of (sql, params) tuples.
        Returns lastrowid of the last statement if return_lastrowid=True.
        """
        with self._write_lock:
            conn = self._connect()
            try:
                cursor = None
                for sql, params in statements:
                    cursor = conn.execute(sql, params)
                conn.commit()
                return cursor.lastrowid if return_lastrowid and cursor else None
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    # --- Projects ---

    def create_project(self, name: str, description: str = "", tech_stack: str = "",
                       path: str = "", revenue_monthly: float = 0) -> dict:
        now = time.time()
        project_id = str(uuid.uuid4())
        self._write([
            ("INSERT INTO projects (id, name, description, tech_stack, path, revenue_monthly, created_at, updated_at) "
             "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
             (project_id, name, description, tech_stack, path, revenue_monthly, now, now)),
        ])
        return self.get_project(project_id)

    def get_project(self, project_id: str) -> Optional[dict]:
        return self._read_one("SELECT * FROM projects WHERE id = ?", (project_id,))

    def list_projects(self) -> list[dict]:
        return self._read("SELECT * FROM projects ORDER BY updated_at DESC")

    def update_project(self, project_id: str, **kwargs) -> Optional[dict]:
        kwargs["updated_at"] = time.time()
        kwargs = _validate_update_kwargs("projects", kwargs)
        if not kwargs:
            return self.get_project(project_id)
        sets = ", ".join(f"{k} = ?" for k in kwargs)
        vals = list(kwargs.values()) + [project_id]
        self._write([(f"UPDATE projects SET {sets} WHERE id = ?", vals)])
        return self.get_project(project_id)

    def delete_project(self, project_id: str):
        self._write([
            ("DELETE FROM project_tasks WHERE project_id = ?", (project_id,)),
            ("DELETE FROM projects WHERE id = ?", (project_id,)),
        ])

    # --- Project Tasks ---

    def create_task(self, project_id: str, title: str, priority: str = "medium",
                    due_date: str = None) -> dict:
        task_id = str(uuid.uuid4())
        self._write([
            ("INSERT INTO project_tasks (id, project_id, title, priority, due_date, created_at) "
             "VALUES (?, ?, ?, ?, ?, ?)",
             (task_id, project_id, title, priority, due_date, time.time())),
        ])
        return {"id": task_id, "project_id": project_id, "title": title,
                "status": "pending", "priority": priority, "due_date": due_date}

    def list_tasks(self, project_id: str) -> list[dict]:
        return self._read(
            "SELECT * FROM project_tasks WHERE project_id = ? ORDER BY created_at",
            (project_id,),
        )

    def update_task(self, task_id: str, **kwargs):
        kwargs = _validate_update_kwargs("project_tasks", kwargs)
        if not kwargs:
            return
        sets = ", ".join(f"{k} = ?" for k in kwargs)
        vals = list(kwargs.values()) + [task_id]
        self._write([(f"UPDATE project_tasks SET {sets} WHERE id = ?", vals)])

    def delete_task(self, task_id: str):
        self._write([("DELETE FROM project_tasks WHERE id = ?", (task_id,))])

    # --- Chat Sessions ---

    def create_session(self, title: str = "New Chat", domain: str = None,
                       model: str = "haiku") -> dict:
        now = time.time()
        session_id = str(uuid.uuid4())
        self._write([
            ("INSERT INTO chat_sessions (id, title, domain, model, created_at, updated_at) "
             "VALUES (?, ?, ?, ?, ?, ?)",
             (session_id, title, domain, model, now, now)),
        ])
        return {"id": session_id, "title": title, "domain": domain, "model": model,
                "created_at": now, "updated_at": now}

    def list_sessions(self, limit: int = 20) -> list[dict]:
        return self._read(
            "SELECT * FROM chat_sessions ORDER BY updated_at DESC LIMIT ?", (limit,)
        )

    def get_session_messages(self, session_id: str, limit: int = 50) -> list[dict]:
        rows = self._read(
            "SELECT * FROM chat_messages WHERE session_id = ? ORDER BY created_at LIMIT ?",
            (session_id, limit),
        )
        for msg in rows:
            if msg.get("context_chunks"):
                try:
                    msg["context_chunks"] = json.loads(msg["context_chunks"])
                except (json.JSONDecodeError, TypeError):
                    msg["context_chunks"] = []
            else:
                msg["context_chunks"] = []
        return rows

    def add_message(self, session_id: str, role: str, content: str,
                    model: str = None, tokens_in: int = 0, tokens_out: int = 0,
                    cost: float = 0, context_chunks: list = None, domain: str = None) -> int:
        now = time.time()
        msg_id = self._write([
            ("INSERT INTO chat_messages (session_id, role, content, model, tokens_in, "
             "tokens_out, cost, context_chunks, domain, created_at) "
             "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
             (session_id, role, content, model, tokens_in, tokens_out, cost,
              json.dumps(context_chunks or []), domain, now)),
            ("UPDATE chat_sessions SET updated_at = ? WHERE id = ?",
             (now, session_id)),
        ], return_lastrowid=True)
        return msg_id

    # --- Financial Entries ---

    def add_financial_entry(self, date: str, amount: float, category: str = "",
                           description: str = "", entry_type: str = "expense",
                           source: str = "", recurring: bool = False) -> dict:
        entry_id = str(uuid.uuid4())
        self._write([
            ("INSERT INTO financial_entries (id, date, category, description, amount, type, source, recurring, created_at) "
             "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
             (entry_id, date, category, description, amount, entry_type, source,
              1 if recurring else 0, time.time())),
        ])
        return {"id": entry_id, "date": date, "category": category, "description": description,
                "amount": amount, "type": entry_type, "source": source, "recurring": recurring}

    def list_financial_entries(self, limit: int = 50, entry_type: str = None) -> list[dict]:
        if entry_type:
            return self._read(
                "SELECT * FROM financial_entries WHERE type = ? ORDER BY date DESC LIMIT ?",
                (entry_type, limit),
            )
        return self._read(
            "SELECT * FROM financial_entries ORDER BY date DESC LIMIT ?", (limit,)
        )

    def get_financial_summary(self) -> dict:
        row = self._read_one("""
            SELECT
                COALESCE(SUM(CASE WHEN type = 'revenue' AND recurring = 1 THEN amount ELSE 0 END), 0) as mrr,
                COALESCE(SUM(CASE WHEN type = 'revenue' THEN amount ELSE 0 END), 0) as total_revenue,
                COALESCE(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 0) as total_expenses
            FROM financial_entries
            WHERE date >= date('now', '-30 days')
        """)
        return {
            "mrr": row["mrr"],
            "revenue_this_month": row["total_revenue"],
            "expenses_this_month": row["total_expenses"],
            "net_profit": row["total_revenue"] - row["total_expenses"],
        }

    # --- Goals ---

    def create_goal(self, title: str, target_date: str = None, category: str = "",
                    notes: str = "") -> dict:
        now = time.time()
        goal_id = str(uuid.uuid4())
        self._write([
            ("INSERT INTO goals (id, title, target_date, category, notes, created_at, updated_at) "
             "VALUES (?, ?, ?, ?, ?, ?, ?)",
             (goal_id, title, target_date, category, notes, now, now)),
        ])
        return {"id": goal_id, "title": title, "target_date": target_date,
                "progress": 0, "category": category, "notes": notes, "status": "active"}

    def list_goals(self) -> list[dict]:
        return self._read("SELECT * FROM goals WHERE status = 'active' ORDER BY created_at")

    def update_goal(self, goal_id: str, **kwargs):
        kwargs["updated_at"] = time.time()
        kwargs = _validate_update_kwargs("goals", kwargs)
        if not kwargs:
            return
        sets = ", ".join(f"{k} = ?" for k in kwargs)
        vals = list(kwargs.values()) + [goal_id]
        self._write([(f"UPDATE goals SET {sets} WHERE id = ?", vals)])

    # --- Neural Feedback ---

    def add_feedback(self, message_id: int, session_id: str, rating: int):
        """Save thumbs up (1) or thumbs down (-1) for a message."""
        # First, read the context_chunks for this message
        msg = self._read_one(
            "SELECT context_chunks FROM chat_messages WHERE id = ?", (message_id,)
        )

        # Build all write statements for atomic execution
        stmts = [
            ("INSERT INTO message_feedback (message_id, session_id, rating, created_at) "
             "VALUES (?, ?, ?, ?)",
             (message_id, session_id, rating, time.time())),
        ]

        if msg and msg.get("context_chunks"):
            try:
                chunk_ids = json.loads(msg["context_chunks"])
            except (json.JSONDecodeError, TypeError):
                chunk_ids = []
            helpful = 1 if rating > 0 else 0
            now = time.time()
            for cid in chunk_ids:
                stmts.append((
                    """INSERT INTO chunk_effectiveness (chunk_id, times_retrieved, times_helpful, effectiveness, updated_at)
                    VALUES (?, 1, ?, ?, ?)
                    ON CONFLICT(chunk_id) DO UPDATE SET
                        times_retrieved = times_retrieved + 1,
                        times_helpful = times_helpful + ?,
                        effectiveness = CAST(times_helpful + ? AS REAL) / (times_retrieved + 1),
                        updated_at = ?""",
                    (cid, helpful, helpful if helpful else 0.0, now,
                     helpful, helpful, now),
                ))

        self._write(stmts)

    def log_routing(self, query_text: str, query_embedding: bytes,
                    predicted_domain: str, tier: int, chunk_ids: list,
                    method: str = "keyword"):
        """Log a routing decision for neural router training."""
        self._write([
            ("INSERT INTO routing_log (query_text, query_embedding, predicted_domain, "
             "tier, chunk_ids, method, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
             (query_text, query_embedding, predicted_domain, tier,
              json.dumps(chunk_ids or []), method, time.time())),
        ])

    def get_neural_status(self) -> dict:
        """Get training data counts and model status."""
        conn = self._connect()
        try:
            routing = conn.execute("SELECT COUNT(*) as n FROM routing_log").fetchone()["n"]
            feedback = conn.execute("SELECT COUNT(*) as n FROM message_feedback").fetchone()["n"]
            thumbs_up = conn.execute(
                "SELECT COUNT(*) as n FROM message_feedback WHERE rating = 1"
            ).fetchone()["n"]
            chunks_rated = conn.execute(
                "SELECT COUNT(*) as n FROM chunk_effectiveness WHERE times_retrieved > 0"
            ).fetchone()["n"]
            last_train = conn.execute(
                "SELECT component, accuracy, samples_used, created_at FROM training_runs "
                "ORDER BY created_at DESC LIMIT 3"
            ).fetchall()
        finally:
            conn.close()

        return {
            "routing_samples": routing,
            "feedback_count": feedback,
            "thumbs_up": thumbs_up,
            "thumbs_down": feedback - thumbs_up,
            "satisfaction_rate": round(thumbs_up / feedback, 3) if feedback > 0 else None,
            "chunks_rated": chunks_rated,
            "router_ready": routing >= 50,
            "reranker_ready": feedback >= 30,
            "adapter_ready": feedback >= 30,
            "recent_training": [dict(r) for r in last_train],
        }

    def get_routing_training_data(self) -> list[dict]:
        """Get all routing log entries with embeddings for training."""
        return self._read(
            "SELECT query_embedding, predicted_domain, actual_domain, rating "
            "FROM routing_log WHERE query_embedding IS NOT NULL"
        )

    def get_chunk_effectiveness_data(self) -> list[dict]:
        """Get chunk effectiveness scores for reranker training."""
        return self._read(
            "SELECT * FROM chunk_effectiveness WHERE times_retrieved >= 2 "
            "ORDER BY effectiveness DESC"
        )

    def log_training_run(self, component: str, samples_used: int,
                         accuracy: float, metrics: dict = None):
        """Record a training run."""
        self._write([
            ("INSERT INTO training_runs (component, samples_used, accuracy, metrics, created_at) "
             "VALUES (?, ?, ?, ?, ?)",
             (component, samples_used, accuracy, json.dumps(metrics or {}), time.time())),
        ])

    # --- Agent Runs ---

    def log_agent_run(self, project: str, agent_type: str, status: str,
                      findings: dict) -> int:
        """Record an autonomous agent execution."""
        return self._write([
            ("INSERT INTO agent_runs (project, agent_type, status, findings, created_at) "
             "VALUES (?, ?, ?, ?, ?)",
             (project, agent_type, status, json.dumps(findings), time.time())),
        ], return_lastrowid=True)

    def get_latest_agent_runs(self, limit: int = 20) -> list[dict]:
        """Get most recent agent runs across all projects."""
        rows = self._read(
            "SELECT * FROM agent_runs ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        for r in rows:
            if r.get("findings"):
                try:
                    r["findings"] = json.loads(r["findings"])
                except (json.JSONDecodeError, TypeError):
                    r["findings"] = {}
        return rows

    def get_project_agent_history(self, project: str, limit: int = 10) -> list[dict]:
        """Get agent run history for a specific project."""
        rows = self._read(
            "SELECT * FROM agent_runs WHERE project = ? ORDER BY created_at DESC LIMIT ?",
            (project, limit),
        )
        for r in rows:
            if r.get("findings"):
                try:
                    r["findings"] = json.loads(r["findings"])
                except (json.JSONDecodeError, TypeError):
                    r["findings"] = {}
        return rows

    def get_latest_run_per_project(self) -> dict:
        """Get the most recent agent run for each project. Returns {project: run_dict}."""
        rows = self._read("""
            SELECT a.* FROM agent_runs a
            INNER JOIN (
                SELECT project, MAX(created_at) as max_created
                FROM agent_runs GROUP BY project
            ) b ON a.project = b.project AND a.created_at = b.max_created
        """)
        result = {}
        for r in rows:
            if r.get("findings"):
                try:
                    r["findings"] = json.loads(r["findings"])
                except (json.JSONDecodeError, TypeError):
                    r["findings"] = {}
            result[r["project"]] = r
        return result

    # --- Stats ---

    def get_chat_cost_total(self) -> float:
        row = self._read_one("SELECT COALESCE(SUM(cost), 0) as total FROM chat_messages")
        return row["total"] if row else 0.0

    def close(self):
        pass  # No persistent connection to close. Per-call connections auto-close.
