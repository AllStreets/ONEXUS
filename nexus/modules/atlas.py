"""
Atlas — the living world model.
A temporal knowledge graph where facts have confidence scores, sources,
and time-based decay. Conflicting facts coexist with competing confidence.
"""
import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any
from nexus.modules.base import NexusModule


@dataclass
class Fact:
    id: str
    subject: str
    predicate: str
    obj: str
    confidence: float
    source: str
    timestamp: str
    max_age_days: int | None


class AtlasModule(NexusModule):
    name = "atlas"
    description = "Living world model — temporal knowledge graph with confidence decay"
    version = "0.1.0"

    def __init__(self, db_path: str | Path | None = None):
        self._db_path = str(db_path) if db_path else ":memory:"

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def init_db(self) -> None:
        conn = self._conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS atlas_facts (
                id           TEXT PRIMARY KEY,
                subject      TEXT NOT NULL,
                predicate    TEXT NOT NULL,
                object       TEXT NOT NULL,
                confidence   REAL NOT NULL,
                source       TEXT NOT NULL,
                timestamp    TEXT NOT NULL,
                max_age_days INTEGER
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_atlas_subject ON atlas_facts(subject)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_atlas_predicate ON atlas_facts(predicate)")
        conn.commit()
        conn.close()

    def add_fact(
        self,
        subject: str,
        predicate: str,
        obj: str,
        confidence: float,
        source: str,
        max_age_days: int | None = None,
    ) -> str:
        fact_id = uuid.uuid4().hex[:12]
        ts = datetime.now(timezone.utc).isoformat()
        conn = self._conn()
        conn.execute(
            """INSERT INTO atlas_facts
               (id, subject, predicate, object, confidence, source, timestamp, max_age_days)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (fact_id, subject, predicate, obj, confidence, source, ts, max_age_days),
        )
        conn.commit()
        conn.close()
        return fact_id

    def remove_fact(self, fact_id: str) -> None:
        conn = self._conn()
        conn.execute("DELETE FROM atlas_facts WHERE id = ?", (fact_id,))
        conn.commit()
        conn.close()

    def query(
        self,
        subject: str | None = None,
        predicate: str | None = None,
        obj: str | None = None,
        apply_decay: bool = False,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        clauses = []
        params: list[Any] = []
        if subject:
            clauses.append("LOWER(subject) = LOWER(?)")
            params.append(subject)
        if predicate:
            clauses.append("LOWER(predicate) = LOWER(?)")
            params.append(predicate)
        if obj:
            clauses.append("LOWER(object) = LOWER(?)")
            params.append(obj)
        where = " AND ".join(clauses) if clauses else "1=1"
        conn = self._conn()
        rows = conn.execute(
            f"SELECT * FROM atlas_facts WHERE {where} ORDER BY confidence DESC LIMIT ?",
            params + [limit],
        ).fetchall()
        conn.close()

        now = datetime.now(timezone.utc)
        results = []
        for r in rows:
            conf = r["confidence"]
            if apply_decay and r["max_age_days"] is not None:
                created = datetime.fromisoformat(r["timestamp"])
                age_days = (now - created).total_seconds() / 86400
                decay = max(0.0, 1.0 - (age_days / max(r["max_age_days"], 0.001)))
                conf = conf * decay
            results.append({
                "id": r["id"],
                "subject": r["subject"],
                "predicate": r["predicate"],
                "object": r["object"],
                "confidence": round(conf, 3),
                "source": r["source"],
                "timestamp": r["timestamp"],
            })
        return results

    def _extract_subject(self, message: str) -> str | None:
        """Extract a likely subject from a query message."""
        lower = message.lower()
        for prefix in ("what do you know about ", "tell me about ", "who is ", "what is "):
            if lower.startswith(prefix):
                return message[len(prefix):].rstrip("?").strip()
        words = message.split()
        if len(words) <= 3:
            return message.strip("?").strip()
        return None

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        subject = self._extract_subject(message)
        if subject:
            results = self.query(subject=subject, apply_decay=True)
            if not results:
                return f"[Atlas] No facts found about '{subject}'."
            lines = [f"[Atlas] Known facts about '{subject}':"]
            for f in results:
                lines.append(
                    f"  - {f['subject']} {f['predicate']} {f['object']} "
                    f"(confidence: {f['confidence']}, source: {f['source']})"
                )
            return "\n".join(lines)
        # Fallback: show all recent facts
        results = self.query(apply_decay=True, limit=10)
        if not results:
            return "[Atlas] No facts in the world model yet."
        lines = ["[Atlas] Recent world model facts:"]
        for f in results:
            lines.append(f"  - {f['subject']} {f['predicate']} {f['object']} ({f['confidence']})")
        return "\n".join(lines)
