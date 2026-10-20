"""
Chronicle — the audit trail for every Nexus action.
SQLite-backed, queryable, exportable for compliance.

Red-team round 2 (R2-4): the kernel only ever appends, but the ledger is a file owned by
the user, so any process running as them could edit it. Each row now carries ``chain``,
a SHA-256 over the previous row's chain and this row's fields, and ``verify()`` walks it.
Editing, deleting or reordering a chained row breaks the chain at that row. Rows written
before chaining existed are reported as legacy, not as tampering. Truncating the newest
rows, or rewriting the whole chain from the start, can only be caught against a head
recorded somewhere else: ``head()`` returns it for that.
"""
from __future__ import annotations

import hashlib
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
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(chronicle)")}
        if "chain" not in cols:
            conn.execute("ALTER TABLE chronicle ADD COLUMN chain TEXT")
        conn.commit()
        conn.close()

    @staticmethod
    def _link(prev: str, event_id: str, ts: str, source: str, action: str, payload: str) -> str:
        body = "\x1f".join((prev, event_id, ts, source, action, payload))
        return hashlib.sha256(body.encode("utf-8")).hexdigest()

    def log(self, source: str, action: str, payload: dict[str, Any] | None = None) -> str:
        event_id = uuid.uuid4().hex[:12]
        ts = datetime.now(timezone.utc).isoformat()
        body = json.dumps(payload or {})
        conn = self._conn()
        try:
            conn.execute("BEGIN IMMEDIATE")  # read the tail and append under one lock
            row = conn.execute(
                "SELECT chain FROM chronicle WHERE chain IS NOT NULL ORDER BY rowid DESC LIMIT 1"
            ).fetchone()
            chain = self._link(row["chain"] if row else "", event_id, ts, source, action, body)
            conn.execute(
                "INSERT INTO chronicle (event_id, timestamp, source, action, payload, chain) VALUES (?, ?, ?, ?, ?, ?)",
                (event_id, ts, source, action, body, chain),
            )
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()
        return event_id

    def head(self) -> dict[str, Any]:
        """The newest chain value and how many rows lead to it. Record it somewhere this
        process can't write to (a commit, a printout, another machine) to catch truncation."""
        conn = self._conn()
        row = conn.execute(
            "SELECT event_id, chain FROM chronicle WHERE chain IS NOT NULL ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
        count = conn.execute("SELECT COUNT(*) AS n FROM chronicle WHERE chain IS NOT NULL").fetchone()["n"]
        conn.close()
        return {"event_id": row["event_id"] if row else None, "chain": row["chain"] if row else None, "rows": count}

    def verify(self) -> dict[str, Any]:
        """Walk the chain in insertion order. ``ok`` is False at the first row whose chain
        doesn't follow from the row before it, with that row's ``event_id``."""
        conn = self._conn()
        rows = conn.execute(
            "SELECT event_id, timestamp, source, action, payload, chain FROM chronicle ORDER BY rowid"
        ).fetchall()
        conn.close()
        legacy = checked = 0
        prev = ""
        started = False
        for r in rows:
            if r["chain"] is None:
                if started:
                    return {"ok": False, "checked": checked, "legacy": legacy,
                            "broken_at": r["event_id"], "reason": "unchained row after the chain began"}
                legacy += 1
                continue
            started = True
            expected = self._link(prev, r["event_id"], r["timestamp"], r["source"], r["action"], r["payload"])
            if r["chain"] != expected:
                return {"ok": False, "checked": checked, "legacy": legacy,
                        "broken_at": r["event_id"], "reason": "chain does not follow from the previous row"}
            prev = r["chain"]
            checked += 1
        return {"ok": True, "checked": checked, "legacy": legacy, "broken_at": None, "reason": None}

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
