"""
Aegis — trust and permissions engine for Nexus.
Batch 1: binary allow/deny per module.
Batch 3 upgrades to graduated 0-100 trust with outcome-based adjustment.
"""
import sqlite3
from typing import Any


class PermissionDenied(Exception):
    def __init__(self, module: str, action: str):
        self.module = module
        self.action = action
        super().__init__(f"Permission denied: {module} cannot perform {action}")


class Aegis:
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
            CREATE TABLE IF NOT EXISTS aegis_policies (
                module  TEXT PRIMARY KEY,
                allowed INTEGER NOT NULL DEFAULT 0,
                trust   INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.commit()
        conn.close()

    def set_policy(self, module: str, allowed: bool) -> None:
        conn = self._conn()
        conn.execute("""
            INSERT INTO aegis_policies (module, allowed) VALUES (?, ?)
            ON CONFLICT(module) DO UPDATE SET allowed = excluded.allowed
        """, (module, int(allowed)))
        conn.commit()
        conn.close()

    def is_allowed(self, module: str, action: str) -> bool:
        conn = self._conn()
        row = conn.execute("SELECT allowed FROM aegis_policies WHERE module = ?", (module,)).fetchone()
        conn.close()
        if row is None:
            return False
        return bool(row["allowed"])

    def check(self, module: str, action: str) -> None:
        if not self.is_allowed(module, action):
            raise PermissionDenied(module, action)

    def list_policies(self) -> list[dict[str, Any]]:
        conn = self._conn()
        rows = conn.execute("SELECT module, allowed, trust FROM aegis_policies").fetchall()
        conn.close()
        return [{"module": r["module"], "allowed": bool(r["allowed"]), "trust": r["trust"]} for r in rows]

    def get_trust(self, module: str) -> int:
        conn = self._conn()
        row = conn.execute("SELECT trust FROM aegis_policies WHERE module = ?", (module,)).fetchone()
        conn.close()
        return int(row["trust"]) if row else 0

    def adjust_trust(self, module: str, delta: int, reason: str) -> int:
        conn = self._conn()
        row = conn.execute("SELECT trust FROM aegis_policies WHERE module = ?", (module,)).fetchone()
        if row is None:
            conn.close()
            return 0
        new_trust = max(0, min(100, int(row["trust"]) + delta))
        conn.execute("UPDATE aegis_policies SET trust = ? WHERE module = ?", (new_trust, module))
        conn.commit()
        conn.close()
        self._log_trust_change(module, delta, new_trust, reason)
        return new_trust

    def check_trust(self, module: str, required_trust: int) -> bool:
        return self.get_trust(module) >= required_trust

    def _log_trust_change(self, module: str, delta: int, new_trust: int, reason: str) -> None:
        conn = self._conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS aegis_trust_log (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                module    TEXT NOT NULL,
                delta     INTEGER NOT NULL,
                new_trust INTEGER NOT NULL,
                reason    TEXT NOT NULL
            )
        """)
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO aegis_trust_log (timestamp, module, delta, new_trust, reason) VALUES (?, ?, ?, ?, ?)",
            (ts, module, delta, new_trust, reason),
        )
        conn.commit()
        conn.close()

    def trust_history(self, module: str, limit: int = 50) -> list[dict[str, Any]]:
        conn = self._conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS aegis_trust_log (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                module    TEXT NOT NULL,
                delta     INTEGER NOT NULL,
                new_trust INTEGER NOT NULL,
                reason    TEXT NOT NULL
            )
        """)
        rows = conn.execute(
            "SELECT timestamp, delta, new_trust, reason FROM aegis_trust_log WHERE module = ? ORDER BY id ASC LIMIT ?",
            (module, limit),
        ).fetchall()
        conn.close()
        return [{"timestamp": r["timestamp"], "delta": r["delta"], "new_trust": r["new_trust"], "reason": r["reason"]} for r in rows]
