"""
Chronicle — immutable audit trail for every Nexus action.
SQLite-backed, queryable, exportable for compliance.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any


class Chronicle:
    def __init__(self, db_path: str):
        self._db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        conn = self._conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chronicle (
                event_id   TEXT PRIMARY KEY,
                timestamp  TEXT NOT NULL,
                source     TEXT NOT NULL,
                action     TEXT NOT NULL,
                payload    TEXT NOT NULL DEFAULT '{}'
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_chronicle_source ON chronicle(source)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_chronicle_action ON chronicle(action)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_chronicle_ts ON chronicle(timestamp)")
        conn.commit()
        conn.close()

    def log(self, source: str, action: str, payload: dict[str, Any] | None = None) -> str:
        event_id = uuid.uuid4().hex[:12]
        ts = datetime.now(timezone.utc).isoformat()
        conn = self._conn()
        conn.execute(
            "INSERT INTO chronicle (event_id, timestamp, source, action, payload) VALUES (?, ?, ?, ?, ?)",
            (event_id, ts, source, action, json.dumps(payload or {})),
        )
        conn.commit()
        conn.close()
        return event_id

    def query(self, source: str | None = None, action: str | None = None,
              since: str | None = None, until: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        clauses = []
        params: list[Any] = []
        if source:
            clauses.append("source = ?")
            params.append(source)
        if action:
            clauses.append("action = ?")
            params.append(action)
        if since:
            clauses.append("timestamp >= ?")
            params.append(since)
        if until:
            clauses.append("timestamp <= ?")
            params.append(until)
        where = " AND ".join(clauses) if clauses else "1=1"
        conn = self._conn()
        rows = conn.execute(
            f"SELECT * FROM chronicle WHERE {where} ORDER BY timestamp DESC LIMIT ?",
            params + [limit],
        ).fetchall()
        conn.close()
        return [
            {"event_id": r["event_id"], "timestamp": r["timestamp"], "source": r["source"],
             "action": r["action"], "payload": json.loads(r["payload"])}
            for r in rows
        ]
