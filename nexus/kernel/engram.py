from __future__ import annotations

import hashlib
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _simple_embedding(text: str, dim: int = 64) -> list[float]:
    h = hashlib.sha256(text.lower().encode()).digest()
    raw = [b / 255.0 for b in h]
    while len(raw) < dim:
        h = hashlib.sha256(h).digest()
        raw.extend(b / 255.0 for b in h)
    return raw[:dim]


class WorkingMemory:
    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    def set(self, key: str, value: Any) -> None:
        self._store[key] = value

    def get(self, key: str) -> Any:
        return self._store.get(key)

    def clear(self) -> None:
        self._store.clear()


class EpisodicMemory:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path), timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def init_db(self) -> None:
        conn = self._conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS episodic (
                id        TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                source    TEXT NOT NULL,
                content   TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS episodic_fts
            USING fts5(content, content_rowid='rowid')
        """)
        conn.commit()
        conn.close()

    def store(self, content: str, source: str = "unknown") -> str:
        entry_id = uuid.uuid4().hex[:12]
        ts = datetime.now(timezone.utc).isoformat()
        conn = self._conn()
        conn.execute(
            "INSERT INTO episodic (id, timestamp, source, content) VALUES (?, ?, ?, ?)",
            (entry_id, ts, source, content),
        )
        conn.execute(
            "INSERT INTO episodic_fts (rowid, content) VALUES (last_insert_rowid(), ?)",
            (content,),
        )
        conn.commit()
        conn.close()
        return entry_id

    def recall(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        conn = self._conn()
        rows = conn.execute("""
            SELECT e.id, e.timestamp, e.source, e.content
            FROM episodic e
            JOIN episodic_fts f ON f.rowid = e.rowid
            WHERE episodic_fts MATCH ?
            ORDER BY e.timestamp DESC
            LIMIT ?
        """, (query, limit)).fetchall()
        conn.close()
        return [{"id": r["id"], "timestamp": r["timestamp"], "source": r["source"], "content": r["content"]} for r in rows]

    def recall_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return the most recent episodic memories without requiring a search query."""
        conn = self._conn()
        rows = conn.execute("""
            SELECT id, timestamp, source, content
            FROM episodic
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,)).fetchall()
        conn.close()
        return [{"id": r["id"], "timestamp": r["timestamp"], "source": r["source"], "content": r["content"]} for r in rows]

    def get(self, entry_id: str) -> dict[str, Any] | None:
        """Fetch a single episodic entry by id. Returns None if not found.

        Used by the chat-history settings page to resolve full transcripts
        from the memory_id stored on each chronicle messages.exchange event.
        """
        conn = self._conn()
        row = conn.execute(
            "SELECT id, timestamp, source, content FROM episodic WHERE id = ?",
            (entry_id,),
        ).fetchone()
        conn.close()
        if row is None:
            return None
        return {"id": row["id"], "timestamp": row["timestamp"], "source": row["source"], "content": row["content"]}


class SemanticMemory:
    def __init__(self, db_path: Path, dim: int = 64) -> None:
        self._db_path = db_path
        self._dim = dim

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path), timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        try:
            conn.enable_load_extension(True)
            import sqlite_vec  # type: ignore
            sqlite_vec.load(conn)
        except Exception:
            pass
        return conn

    def init_db(self) -> None:
        conn = self._conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS semantic (
                id        TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                category  TEXT NOT NULL,
                content   TEXT NOT NULL,
                embedding BLOB NOT NULL
            )
        """)
        conn.commit()
        conn.close()

    def store(self, content: str, category: str = "general") -> str:
        entry_id = uuid.uuid4().hex[:12]
        ts = datetime.now(timezone.utc).isoformat()
        emb = _simple_embedding(content, self._dim)
        emb_blob = bytes(int(v * 255) for v in emb)
        conn = self._conn()
        conn.execute(
            "INSERT INTO semantic (id, timestamp, category, content, embedding) VALUES (?, ?, ?, ?, ?)",
            (entry_id, ts, category, content, emb_blob),
        )
        conn.commit()
        conn.close()
        return entry_id

    def search(self, query: str, category: str | None = None, limit: int = 5) -> list[dict[str, Any]]:
        query_emb = _simple_embedding(query, self._dim)
        conn = self._conn()
        cat_clause = "AND category = ?" if category else ""
        params: list[Any] = [category] if category else []
        rows = conn.execute(
            f"SELECT id, timestamp, category, content, embedding FROM semantic WHERE 1=1 {cat_clause}",
            params,
        ).fetchall()
        conn.close()

        def cosine_sim(a: list[float], b_blob: bytes) -> float:
            b = [v / 255.0 for v in b_blob]
            dot = sum(x * y for x, y in zip(a, b))
            mag_a = sum(x * x for x in a) ** 0.5
            mag_b = sum(y * y for y in b) ** 0.5
            if mag_a == 0 or mag_b == 0:
                return 0.0
            return dot / (mag_a * mag_b)

        scored = [(cosine_sim(query_emb, r["embedding"]), r) for r in rows]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {"id": r["id"], "timestamp": r["timestamp"], "category": r["category"],
             "content": r["content"], "score": s}
            for s, r in scored[:limit]
        ]


_DEFAULT_HALF_LIFE_HOURS: dict[str, float] = {"default": 720.0}  # 30 days


class AtlasFacts:
    """Temporal knowledge graph -- Engram's semantic tier, extended (N1.2).

    Facts are (subject, relation, object) triples with confidence that
    decays deterministically at read time (half-life per fact class;
    config default via NEXUS_ATLAS_HALF_LIFE_HOURS, overridable per class).
    Re-confirmation restores confidence; contradictory facts coexist with
    competing confidences; every fact carries a source_ref citation.
    """

    def __init__(self, db_path: Path, half_lives: dict[str, float] | None = None) -> None:
        self._db_path = db_path
        self._half_lives = dict(_DEFAULT_HALF_LIFE_HOURS)
        env = os.environ.get("NEXUS_ATLAS_HALF_LIFE_HOURS")
        if env:
            try:
                self._half_lives["default"] = float(env)
            except ValueError:
                pass
        if half_lives:
            self._half_lives.update(half_lives)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path), timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def init_db(self) -> None:
        conn = self._conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS atlas_facts (
                id                TEXT PRIMARY KEY,
                subject           TEXT NOT NULL,
                relation          TEXT NOT NULL,
                object            TEXT NOT NULL,
                fact_class        TEXT NOT NULL DEFAULT 'default',
                confidence        REAL NOT NULL,
                observed_at       TEXT NOT NULL,
                last_confirmed_at TEXT NOT NULL,
                source_ref        TEXT NOT NULL DEFAULT ''
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_atlas_subject ON atlas_facts(subject)")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_atlas_spo ON atlas_facts(subject, relation, object)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS atlas_edges (
                src_id TEXT NOT NULL,
                dst_id TEXT NOT NULL,
                label  TEXT NOT NULL DEFAULT 'related',
                PRIMARY KEY (src_id, dst_id, label)
            )
        """)
        conn.commit()
        conn.close()

    def set_half_life(self, fact_class: str, hours: float) -> None:
        self._half_lives[fact_class] = float(hours)

    def effective_confidence(self, stored: float, last_confirmed_at: str,
                             fact_class: str, now: datetime) -> float:
        try:
            confirmed = datetime.fromisoformat(last_confirmed_at)
        except (TypeError, ValueError):
            return float(stored)
        if confirmed.tzinfo is None:
            confirmed = confirmed.replace(tzinfo=timezone.utc)
        age_hours = max(0.0, (now - confirmed).total_seconds() / 3600.0)
        half_life = self._half_lives.get(fact_class, self._half_lives["default"])
        if half_life <= 0:
            return float(stored)
        return float(stored) * (0.5 ** (age_hours / half_life))

    def observe(self, subject: str, relation: str, obj: str, *,
                confidence: float = 0.9, fact_class: str = "default",
                source_ref: str = "", now: datetime | None = None) -> str:
        ts = (now or datetime.now(timezone.utc)).isoformat()
        conn = self._conn()
        row = conn.execute(
            "SELECT id, confidence FROM atlas_facts WHERE subject = ? AND relation = ? AND object = ?",
            (subject, relation, obj),
        ).fetchone()
        if row is not None:
            # Re-confirmation: restore confidence, bump last_confirmed_at.
            new_conf = max(float(confidence), float(row["confidence"]))
            conn.execute(
                "UPDATE atlas_facts SET confidence = ?, last_confirmed_at = ?, "
                "source_ref = CASE WHEN ? = '' THEN source_ref ELSE ? END WHERE id = ?",
                (new_conf, ts, source_ref, source_ref, row["id"]),
            )
            conn.commit()
            conn.close()
            return row["id"]
        fact_id = uuid.uuid4().hex[:12]
        conn.execute(
            "INSERT INTO atlas_facts (id, subject, relation, object, fact_class, "
            "confidence, observed_at, last_confirmed_at, source_ref) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (fact_id, subject, relation, obj, fact_class, float(confidence),
             ts, ts, source_ref),
        )
        conn.commit()
        conn.close()
        return fact_id

    def beliefs(self, subject: str, relation: str | None = None, *,
                now: datetime | None = None, min_confidence: float = 0.0) -> list[dict[str, Any]]:
        moment = now or datetime.now(timezone.utc)
        conn = self._conn()
        if relation:
            rows = conn.execute(
                "SELECT * FROM atlas_facts WHERE subject = ? AND relation = ?",
                (subject, relation)).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM atlas_facts WHERE subject = ?", (subject,)).fetchall()
        conn.close()
        out: list[dict[str, Any]] = []
        for r in rows:
            eff = self.effective_confidence(float(r["confidence"]),
                                            r["last_confirmed_at"],
                                            r["fact_class"], moment)
            if eff < min_confidence:
                continue
            out.append({
                "id": r["id"], "subject": r["subject"], "relation": r["relation"],
                "object": r["object"], "fact_class": r["fact_class"],
                "confidence": round(eff, 6),
                "stored_confidence": float(r["confidence"]),
                "observed_at": r["observed_at"],
                "last_confirmed_at": r["last_confirmed_at"],
                "source_ref": r["source_ref"],
            })
        out.sort(key=lambda f: f["confidence"], reverse=True)
        return out

    def link(self, src_id: str, dst_id: str, label: str = "related") -> None:
        conn = self._conn()
        conn.execute(
            "INSERT OR IGNORE INTO atlas_edges (src_id, dst_id, label) VALUES (?, ?, ?)",
            (src_id, dst_id, label))
        conn.commit()
        conn.close()

    def neighbors(self, fact_id: str, *, now: datetime | None = None) -> list[dict[str, Any]]:
        moment = now or datetime.now(timezone.utc)
        conn = self._conn()
        rows = conn.execute("""
            SELECT f.*, e.label FROM atlas_edges e
            JOIN atlas_facts f
              ON f.id = CASE WHEN e.src_id = ? THEN e.dst_id ELSE e.src_id END
            WHERE e.src_id = ? OR e.dst_id = ?
        """, (fact_id, fact_id, fact_id)).fetchall()
        conn.close()
        return [{
            "id": r["id"], "subject": r["subject"], "relation": r["relation"],
            "object": r["object"], "label": r["label"],
            "confidence": round(self.effective_confidence(
                float(r["confidence"]), r["last_confirmed_at"],
                r["fact_class"], moment), 6),
            "source_ref": r["source_ref"],
        } for r in rows]


class Engram:
    def __init__(self, db_path: Path) -> None:
        self._db_path = Path(db_path)
        self.working = WorkingMemory()
        self.episodic = EpisodicMemory(self._db_path)
        self.semantic = SemanticMemory(self._db_path)
        self.atlas = AtlasFacts(self._db_path)

    def init_db(self) -> None:
        self.episodic.init_db()
        self.semantic.init_db()
        self.atlas.init_db()

    def partition(self, workspace_root: Path) -> "Engram":
        """Return a new Engram scoped to *workspace_root*/engram/.

        The returned instance has its own episodic and semantic stores
        isolated under the workspace's directory — cross-workspace reads
        require the ``engram.read.global`` capability.

        Parameters
        ----------
        workspace_root:
            The workspace directory (e.g. ``~/.nexus/workspaces/my-id/``).
            The ``engram/`` sub-directory is created automatically.
        """
        engram_dir = Path(workspace_root) / "engram"
        engram_dir.mkdir(parents=True, exist_ok=True)
        # Each workspace gets its own DB file so episodic / semantic are
        # fully isolated.  Working memory is always transient — a fresh
        # WorkingMemory is fine for each partition.
        db_path = engram_dir / "episodic.sqlite"
        child = Engram(db_path)
        child.init_db()
        return child
