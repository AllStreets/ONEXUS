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
