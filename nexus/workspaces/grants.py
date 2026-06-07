"""
GrantsStore — per-workspace SQLite-backed permission grants table.

Each workspace owns a ``grants.sqlite`` that records the "always allow
in this workspace" overrides for agent capabilities.  These grants layer
on top of Aegis's global trust tier: an Executor-tier agent may still
need an explicit grant for Privileged capabilities, and a grant in one
workspace does not carry to another.

Schema
------
grants(id, agent_slug, capability, scope, granted_at, granted_by)

See docs/superpowers/specs/2026-06-06-nexus-agent-os-design.md §7 and
the Aegis capability section (§4.5).
"""
from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Grant:
    """A single capability grant record."""

    __slots__ = ("grant_id", "agent_slug", "capability", "scope", "granted_at", "granted_by")

    def __init__(
        self,
        grant_id: str,
        agent_slug: str,
        capability: str,
        scope: str,
        granted_at: str,
        granted_by: str,
    ) -> None:
        self.grant_id = grant_id
        self.agent_slug = agent_slug
        self.capability = capability
        self.scope = scope
        self.granted_at = granted_at
        self.granted_by = granted_by

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"Grant(agent={self.agent_slug!r}, capability={self.capability!r}, "
            f"scope={self.scope!r})"
        )

    def to_dict(self) -> dict:
        return {
            "grant_id": self.grant_id,
            "agent_slug": self.agent_slug,
            "capability": self.capability,
            "scope": self.scope,
            "granted_at": self.granted_at,
            "granted_by": self.granted_by,
        }


class GrantsStore:
    """SQLite-backed per-workspace grants table.

    Parameters
    ----------
    db_path:
        Path to the ``grants.sqlite`` file.  The file (and its parent
        directory) are created automatically on first use.
    """

    def __init__(self, db_path: Path | str) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

    # ── internal ──────────────────────────────────────────────────────────

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path), timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    # ── lifecycle ─────────────────────────────────────────────────────────

    def init_db(self) -> None:
        """Create the grants table if it does not already exist."""
        conn = self._conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS grants (
                grant_id    TEXT PRIMARY KEY,
                agent_slug  TEXT NOT NULL,
                capability  TEXT NOT NULL,
                scope       TEXT NOT NULL DEFAULT '',
                granted_at  TEXT NOT NULL,
                granted_by  TEXT NOT NULL DEFAULT 'user',
                UNIQUE (agent_slug, capability, scope)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_grants_agent
            ON grants(agent_slug)
        """)
        conn.commit()
        conn.close()

    # ── public API ────────────────────────────────────────────────────────

    def grant(
        self,
        agent_slug: str,
        capability: str,
        scope: str = "",
        granted_by: str = "user",
    ) -> Grant:
        """Add or update a capability grant.

        If a grant already exists for the same (agent_slug, capability,
        scope) triple it is returned unchanged (idempotent).

        Returns the persisted Grant.
        """
        existing = self.get(agent_slug, capability, scope)
        if existing is not None:
            return existing

        gid = uuid.uuid4().hex[:16]
        now = _now_iso()
        conn = self._conn()
        conn.execute(
            """
            INSERT OR IGNORE INTO grants
                (grant_id, agent_slug, capability, scope, granted_at, granted_by)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (gid, agent_slug, capability, scope, now, granted_by),
        )
        conn.commit()
        conn.close()
        # Re-fetch in case INSERT OR IGNORE skipped (race)
        result = self.get(agent_slug, capability, scope)
        assert result is not None
        return result

    def revoke(self, agent_slug: str, capability: str, scope: str = "") -> bool:
        """Remove a grant.  Returns True if a row was deleted."""
        conn = self._conn()
        cur = conn.execute(
            "DELETE FROM grants WHERE agent_slug=? AND capability=? AND scope=?",
            (agent_slug, capability, scope),
        )
        conn.commit()
        deleted = cur.rowcount > 0
        conn.close()
        return deleted

    def revoke_all(self, agent_slug: str) -> int:
        """Remove ALL grants for an agent.  Returns number of rows deleted."""
        conn = self._conn()
        cur = conn.execute(
            "DELETE FROM grants WHERE agent_slug=?",
            (agent_slug,),
        )
        conn.commit()
        count = cur.rowcount
        conn.close()
        return count

    def has(self, agent_slug: str, capability: str, scope: str = "") -> bool:
        """Return True if a matching grant exists."""
        return self.get(agent_slug, capability, scope) is not None

    def get(self, agent_slug: str, capability: str, scope: str = "") -> Grant | None:
        """Return the Grant for (agent_slug, capability, scope) or None."""
        conn = self._conn()
        row = conn.execute(
            "SELECT * FROM grants WHERE agent_slug=? AND capability=? AND scope=?",
            (agent_slug, capability, scope),
        ).fetchone()
        conn.close()
        if row is None:
            return None
        return Grant(
            grant_id=row["grant_id"],
            agent_slug=row["agent_slug"],
            capability=row["capability"],
            scope=row["scope"],
            granted_at=row["granted_at"],
            granted_by=row["granted_by"],
        )

    def list_for_agent(self, agent_slug: str) -> list[Grant]:
        """Return all grants for an agent, ordered by capability."""
        conn = self._conn()
        rows = conn.execute(
            "SELECT * FROM grants WHERE agent_slug=? ORDER BY capability, scope",
            (agent_slug,),
        ).fetchall()
        conn.close()
        return [
            Grant(
                grant_id=r["grant_id"],
                agent_slug=r["agent_slug"],
                capability=r["capability"],
                scope=r["scope"],
                granted_at=r["granted_at"],
                granted_by=r["granted_by"],
            )
            for r in rows
        ]

    def list_all(self) -> list[Grant]:
        """Return all grants in the store, ordered by agent_slug."""
        conn = self._conn()
        rows = conn.execute(
            "SELECT * FROM grants ORDER BY agent_slug, capability, scope"
        ).fetchall()
        conn.close()
        return [
            Grant(
                grant_id=r["grant_id"],
                agent_slug=r["agent_slug"],
                capability=r["capability"],
                scope=r["scope"],
                granted_at=r["granted_at"],
                granted_by=r["granted_by"],
            )
            for r in rows
        ]
