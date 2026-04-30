"""
Aegis -- trust and permissions engine for Nexus.
Graduated 0.0-1.0 floating-point trust with asymmetric outcome adjustment.
Trust tiers: OBSERVER, ADVISOR, MONITOR, EXECUTOR, AUTONOMOUS.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any, Optional


class PermissionDenied(Exception):
    def __init__(self, module: str, action: str):
        self.module = module
        self.action = action
        super().__init__(f"Permission denied: {module} cannot perform {action}")


class TrustTier:
    OBSERVER = "OBSERVER"
    ADVISOR = "ADVISOR"
    MONITOR = "MONITOR"
    EXECUTOR = "EXECUTOR"
    AUTONOMOUS = "AUTONOMOUS"

    _THRESHOLDS = {
        OBSERVER: 0.0,
        ADVISOR: 0.25,
        MONITOR: 0.50,
        EXECUTOR: 0.75,
        AUTONOMOUS: 1.0,
    }

    @classmethod
    def from_score(cls, score: float) -> str:
        if score >= 1.0:
            return cls.AUTONOMOUS
        if score >= 0.75:
            return cls.EXECUTOR
        if score >= 0.50:
            return cls.MONITOR
        if score >= 0.25:
            return cls.ADVISOR
        return cls.OBSERVER

    @classmethod
    def threshold(cls, tier_name: str) -> float:
        if tier_name not in cls._THRESHOLDS:
            raise ValueError(f"Unknown tier: {tier_name}")
        return cls._THRESHOLDS[tier_name]


# Adjustment deltas
_REWARD = 0.12
_PENALTY = -0.22


class Aegis:
    def __init__(self, db_path: str, chronicle: Optional[Any] = None):
        self._db_path = db_path
        self._chronicle = chronicle

    # -- internal helpers --------------------------------------------------

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.row_factory = sqlite3.Row
        return conn

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _log_chronicle(self, event: str, data: dict[str, Any]) -> None:
        if self._chronicle is None:
            return
        try:
            self._chronicle.log(event, data)
        except Exception:
            pass  # chronicle failure must never block trust operations

    # -- schema ------------------------------------------------------------

    def init_db(self) -> None:
        conn = self._conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS aegis_policies (
                module_name     TEXT PRIMARY KEY,
                trust_score     REAL NOT NULL DEFAULT 0.0,
                allowed         INTEGER NOT NULL DEFAULT 0,
                network_allowed INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS aegis_trust_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                module_name TEXT NOT NULL,
                old_score   REAL NOT NULL,
                new_score   REAL NOT NULL,
                delta       REAL NOT NULL,
                reason      TEXT NOT NULL,
                timestamp   TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()

    # -- policy management -------------------------------------------------

    def set_policy(self, module: str, allowed: bool = True, network: bool = False) -> None:
        conn = self._conn()
        conn.execute("""
            INSERT INTO aegis_policies (module_name, allowed, network_allowed)
            VALUES (?, ?, ?)
            ON CONFLICT(module_name) DO UPDATE SET
                allowed = excluded.allowed,
                network_allowed = excluded.network_allowed
        """, (module, int(allowed), int(network)))
        conn.commit()
        conn.close()

    def check(self, module: str, action: str) -> None:
        conn = self._conn()
        row = conn.execute(
            "SELECT allowed FROM aegis_policies WHERE module_name = ?", (module,)
        ).fetchone()
        conn.close()
        if row is None or not bool(row["allowed"]):
            raise PermissionDenied(module, action)

    def is_network_allowed(self, module: str) -> bool:
        conn = self._conn()
        row = conn.execute(
            "SELECT network_allowed FROM aegis_policies WHERE module_name = ?", (module,)
        ).fetchone()
        conn.close()
        if row is None:
            return False
        return bool(row["network_allowed"])

    # -- trust scoring -----------------------------------------------------

    def _ensure_module(self, conn: sqlite3.Connection, module: str) -> None:
        """Ensure a row exists for the module with defaults."""
        conn.execute("""
            INSERT OR IGNORE INTO aegis_policies (module_name) VALUES (?)
        """, (module,))

    def _record_history(self, conn: sqlite3.Connection, module: str,
                        old: float, new: float, delta: float, reason: str) -> None:
        ts = self._now()
        conn.execute("""
            INSERT INTO aegis_trust_history (module_name, old_score, new_score, delta, reason, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (module, old, new, delta, reason, ts))
        self._log_chronicle("aegis.trust_change", {
            "module": module,
            "old_score": old,
            "new_score": new,
            "delta": delta,
            "reason": reason,
            "tier": TrustTier.from_score(new),
            "timestamp": ts,
        })

    def record_outcome(self, module: str, success: bool) -> float:
        """Adjust trust based on outcome. Returns the new score."""
        delta = _REWARD if success else _PENALTY
        reason = "positive_outcome" if success else "negative_outcome"

        conn = self._conn()
        self._ensure_module(conn, module)
        row = conn.execute(
            "SELECT trust_score FROM aegis_policies WHERE module_name = ?", (module,)
        ).fetchone()
        old_score = float(row["trust_score"])
        new_score = max(0.0, min(1.0, old_score + delta))

        conn.execute(
            "UPDATE aegis_policies SET trust_score = ? WHERE module_name = ?",
            (new_score, module),
        )
        self._record_history(conn, module, old_score, new_score, delta, reason)
        conn.commit()
        conn.close()
        return new_score

    def get_trust(self, module: str) -> float:
        conn = self._conn()
        row = conn.execute(
            "SELECT trust_score FROM aegis_policies WHERE module_name = ?", (module,)
        ).fetchone()
        conn.close()
        return float(row["trust_score"]) if row else 0.0

    def get_tier(self, module: str) -> str:
        return TrustTier.from_score(self.get_trust(module))

    def revoke(self, module: str) -> None:
        """Immediately set trust to 0.0 and log the revocation."""
        conn = self._conn()
        self._ensure_module(conn, module)
        row = conn.execute(
            "SELECT trust_score FROM aegis_policies WHERE module_name = ?", (module,)
        ).fetchone()
        old_score = float(row["trust_score"])

        conn.execute(
            "UPDATE aegis_policies SET trust_score = 0.0 WHERE module_name = ?", (module,)
        )
        self._record_history(conn, module, old_score, 0.0, -old_score, "revoked")
        conn.commit()
        conn.close()

    def get_trust_history(self, module: str, limit: int = 100) -> list[dict[str, Any]]:
        conn = self._conn()
        rows = conn.execute("""
            SELECT old_score, new_score, delta, reason, timestamp
            FROM aegis_trust_history
            WHERE module_name = ?
            ORDER BY id ASC
            LIMIT ?
        """, (module, limit)).fetchall()
        conn.close()
        return [
            {
                "old_score": r["old_score"],
                "new_score": r["new_score"],
                "delta": r["delta"],
                "reason": r["reason"],
                "timestamp": r["timestamp"],
            }
            for r in rows
        ]

    # -- tier-based capability checks --------------------------------------

    def can_suggest(self, module: str) -> bool:
        return self.get_trust(module) >= 0.25

    def can_monitor(self, module: str) -> bool:
        return self.get_trust(module) >= 0.50

    def can_execute(self, module: str) -> bool:
        return self.get_trust(module) >= 0.75

    def is_autonomous(self, module: str) -> bool:
        return self.get_trust(module) == 1.0

    # -- policy listing ----------------------------------------------------

    def list_policies(self) -> list[dict[str, Any]]:
        conn = self._conn()
        rows = conn.execute(
            "SELECT module_name, trust_score, allowed, network_allowed FROM aegis_policies"
        ).fetchall()
        conn.close()
        return [
            {
                "module": r["module_name"],
                "trust_score": r["trust_score"],
                "tier": TrustTier.from_score(r["trust_score"]),
                "allowed": bool(r["allowed"]),
                "network_allowed": bool(r["network_allowed"]),
            }
            for r in rows
        ]
