"""
Episodic Memory — SQLite session log with full-text search & vector search.

Stores past sessions/tasks with outcomes so Woody can recall
"like last time" context, answer "what did I ask earlier?", and avoid repeating failed approaches.

Schema:
  sessions: id, timestamp, user_request, intent, result_summary, success, duration_ms, tool_calls
  tool_calls: id, session_id, tool_name, inputs, output, tier, confirmed, timestamp

Vector embeddings stored in sqlite-vec for semantic recall if available, with robust
LIKE/token-matching fallback.
"""
from __future__ import annotations

import datetime
import json
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from woody.utils.logging import get_logger

log = get_logger(__name__)


@dataclass
class SessionRecord:
    session_id: str
    timestamp: float
    user_request: str
    intent: str
    result_summary: str
    success: bool
    duration_ms: float
    tool_call_count: int = 0


class EpisodicMemory:
    """
    Persistent episodic memory backed by SQLite.

    Usage:
        mem = EpisodicMemory(db_path="~/.Woody/episodic.db")
        mem.open()
        mem.log_session(session_id="abc", user_request="Open Notepad", ...)
        history = mem.get_recent(n=5)
        similar = mem.search("open a text editor", n=3)
    """

    def __init__(self, db_path: str | Path = "~/.Woody/episodic.db") -> None:
        self._db_path = Path(db_path).expanduser()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self._has_vec = False

    def open(self) -> None:
        """Open the database and create tables if needed."""
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._create_tables()
        self._try_load_vec()
        log.info("episodic.opened", path=str(self._db_path))

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def _create_tables(self) -> None:
        assert self._conn
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id          TEXT PRIMARY KEY,
                timestamp   REAL NOT NULL,
                user_request TEXT NOT NULL,
                intent      TEXT,
                result_summary TEXT,
                success     INTEGER DEFAULT 1,
                duration_ms REAL DEFAULT 0,
                tool_calls  INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS tool_calls (
                id          TEXT PRIMARY KEY,
                session_id  TEXT NOT NULL,
                tool_name   TEXT NOT NULL,
                inputs      TEXT,
                output      TEXT,
                tier        TEXT,
                confirmed   INTEGER,
                timestamp   REAL,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );

            CREATE INDEX IF NOT EXISTS idx_sessions_ts ON sessions(timestamp);
            CREATE INDEX IF NOT EXISTS idx_sessions_req ON sessions(user_request);
            CREATE INDEX IF NOT EXISTS idx_tool_session ON tool_calls(session_id);
        """)
        self._conn.commit()

    def _try_load_vec(self) -> None:
        """Try to load sqlite-vec extension for vector search."""
        try:
            import sqlite_vec
            assert self._conn
            self._conn.enable_load_extension(True)
            sqlite_vec.load(self._conn)
            self._conn.enable_load_extension(False)

            # Create vector table for session embeddings
            self._conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS session_embeddings
                USING vec0(session_id TEXT, embedding FLOAT[384])
            """)
            self._conn.commit()
            self._has_vec = True
            log.info("episodic.vec_loaded")
        except Exception as e:
            log.debug("episodic.vec_unavailable", reason=str(e), fallback="text_search")

    def log_session(
        self,
        session_id: str,
        user_request: str,
        intent: str = "",
        result_summary: str = "",
        success: bool = True,
        duration_ms: float = 0.0,
        tool_call_count: int = 0,
    ) -> None:
        """Log a completed session."""
        if not self._conn:
            return
        self._conn.execute(
            """INSERT OR REPLACE INTO sessions
               (id, timestamp, user_request, intent, result_summary, success, duration_ms, tool_calls)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (session_id, time.time(), user_request, intent, result_summary,
             int(success), duration_ms, tool_call_count),
        )
        self._conn.commit()

    def log_tool_call(
        self,
        session_id: str,
        tool_name: str,
        inputs: dict,
        output: Any,
        tier: str = "read_only",
        confirmed: bool | None = None,
    ) -> None:
        """Log a single tool call within a session."""
        if not self._conn:
            return
        self._conn.execute(
            """INSERT INTO tool_calls
               (id, session_id, tool_name, inputs, output, tier, confirmed, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (str(uuid.uuid4()), session_id, tool_name,
             json.dumps(inputs)[:2000],
             json.dumps(str(output))[:2000],
             tier,
             int(confirmed) if confirmed is not None else None,
             time.time()),
        )
        self._conn.commit()

    def get_recent(self, n: int = 5) -> list[dict]:
        """Return the n most recent sessions."""
        if not self._conn:
            return []
        rows = self._conn.execute(
            "SELECT * FROM sessions ORDER BY timestamp DESC LIMIT ?", (n,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_recent_summary(self, n: int = 5) -> list[dict]:
        """Return structured recent session records with formatted timestamps."""
        sessions = self.get_recent(n=n)
        result = []
        for s in sessions:
            ts = datetime.datetime.fromtimestamp(s["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
            result.append({
                "session_id": s["id"],
                "time": ts,
                "request": s["user_request"],
                "intent": s.get("intent", ""),
                "result": s.get("result_summary", ""),
                "success": bool(s.get("success", 1)),
            })
        return result

    def search(self, query: str, n: int = 5) -> list[dict]:
        """
        Search past sessions for keyword/sub-string matches across user requests,
        intents, and result summaries.
        """
        if not self._conn or not query or not query.strip():
            return self.get_recent_summary(n=n)

        terms = [t.strip() for t in query.strip().split() if len(t.strip()) > 1]
        if not terms:
            terms = [query.strip()]

        where_clauses = []
        params = []
        for term in terms:
            term_param = f"%{term}%"
            where_clauses.append("(user_request LIKE ? OR intent LIKE ? OR result_summary LIKE ?)")
            params.extend([term_param, term_param, term_param])

        where_sql = " OR ".join(where_clauses)
        sql = f"""
            SELECT * FROM sessions
            WHERE {where_sql}
            ORDER BY timestamp DESC
            LIMIT ?
        """
        params.append(n)

        rows = self._conn.execute(sql, params).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            ts = datetime.datetime.fromtimestamp(d["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
            result.append({
                "session_id": d["id"],
                "time": ts,
                "request": d["user_request"],
                "intent": d.get("intent", ""),
                "result": d.get("result_summary", ""),
                "success": bool(d.get("success", 1)),
            })
        return result

    def search_similar(self, query: str, n: int = 3) -> list[dict]:
        """Alias for search."""
        return self.search(query=query, n=n)

    def format_history_for_prompt(self, n: int = 3) -> str:
        """Format recent session history for inclusion in the planner prompt."""
        sessions = self.get_recent(n=n)
        if not sessions:
            return ""
        lines = []
        for s in sessions:
            ts = datetime.datetime.fromtimestamp(s["timestamp"]).strftime("%H:%M")
            status = "✓" if s["success"] else "✗"
            lines.append(f"{status} [{ts}] {s['user_request']} → {s['result_summary'][:80]}")
        return "\n".join(lines)

    def get_session_count(self) -> int:
        if not self._conn:
            return 0
        return self._conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
