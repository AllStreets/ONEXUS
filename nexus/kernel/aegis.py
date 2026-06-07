"""
Aegis -- trust and permissions engine for Nexus.
Graduated 0.0-1.0 floating-point trust with asymmetric outcome adjustment.
Trust tiers: OBSERVER, ADVISOR, MONITOR, EXECUTOR, AUTONOMOUS.
"""
from __future__ import annotations

import sqlite3
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from urllib.parse import urlparse

from nexus.agents.manifest import Manifest, PermissionClass


class Verdict(str, Enum):
    ALLOW = "ALLOW"
    PROMPT = "PROMPT"
    DENY = "DENY"


@dataclass(frozen=True)
class CapabilityDecision:
    verdict: Verdict
    reason: str
    permission_class: PermissionClass | None = None


class PermissionDenied(Exception):
    def __init__(self, module: str, action: str):
        self.module = module
        self.action = action
        super().__init__(f"Permission denied: {module} cannot perform {action}")


def _is_within(child, parent) -> bool:
    """True if child is parent or a descendant of parent."""
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


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
            self._chronicle.log("aegis", event, data)
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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS aegis_grants (
                agent_slug   TEXT NOT NULL,
                capability   TEXT NOT NULL,
                workspace_id TEXT,
                granted_at   TEXT NOT NULL,
                PRIMARY KEY (agent_slug, capability, workspace_id)
            )
        """)
        conn.commit()
        conn.close()

    # -- policy management -------------------------------------------------

    def set_policy(self, module: str, allowed: bool = True, network: bool = False,
                   initial_trust: float | None = None) -> None:
        conn = self._conn()
        if initial_trust is not None:
            conn.execute("""
                INSERT INTO aegis_policies (module_name, trust_score, allowed, network_allowed)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(module_name) DO UPDATE SET
                    allowed = excluded.allowed,
                    network_allowed = excluded.network_allowed
            """, (module, initial_trust, int(allowed), int(network)))
        else:
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
        """Immediately set trust to 0.0 and log the revocation.

        Note: this bypasses ``set_trust`` and therefore does NOT trigger
        the trust-collapse grant cleanup. If you want both trust reset
        AND grant revocation, call ``set_trust(module, 0.0)`` instead.
        """
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

    # ── manifest registry ────────────────────────────────────────────────

    def register_manifest(self, manifest: Manifest) -> None:
        """Register an agent's manifest so check_capability can read it."""
        if not hasattr(self, "_manifests"):
            self._manifests: dict[str, Manifest] = {}
        self._manifests[manifest.slug] = manifest
        # Seed trust at the manifest's floor if not set yet
        if self.get_trust(manifest.slug) == 0.0 and manifest.trust.floor > 0:
            self.set_trust(manifest.slug, manifest.trust.floor)

    def get_manifest(self, slug: str) -> Manifest | None:
        return getattr(self, "_manifests", {}).get(slug)

    # ── grant storage (SQLite-backed, aegis_grants table) ────────────────

    def grant(
        self,
        agent_slug: str,
        capability: str,
        workspace_id: str | None = None,
    ) -> None:
        """Record an explicit user grant. workspace_id=None means global."""
        conn = self._conn()
        conn.execute(
            "INSERT OR REPLACE INTO aegis_grants "
            "(agent_slug, capability, workspace_id, granted_at) VALUES (?, ?, ?, ?)",
            (agent_slug, capability, workspace_id, self._now()),
        )
        conn.commit()
        conn.close()
        self._log_chronicle("permission_granted", {
            "agent": agent_slug,
            "capability": capability,
            "workspace_id": workspace_id,
        })

    def revoke_grant(
        self,
        agent_slug: str,
        capability: str | None = None,
        workspace_id: str | None = None,
    ) -> None:
        """Revoke one capability or, if capability is None, all grants for this agent in this scope.

        Renamed from `revoke` to avoid colliding with the existing one-arg
        `revoke(module)` which resets trust to 0.0.
        """
        conn = self._conn()
        if capability is None:
            conn.execute(
                "DELETE FROM aegis_grants WHERE agent_slug = ? AND "
                "((workspace_id IS NULL AND ? IS NULL) OR workspace_id = ?)",
                (agent_slug, workspace_id, workspace_id),
            )
        else:
            conn.execute(
                "DELETE FROM aegis_grants WHERE agent_slug = ? AND capability = ? AND "
                "((workspace_id IS NULL AND ? IS NULL) OR workspace_id = ?)",
                (agent_slug, capability, workspace_id, workspace_id),
            )
        conn.commit()
        conn.close()
        self._log_chronicle("permission_revoked", {
            "agent": agent_slug,
            "capability": capability,
            "workspace_id": workspace_id,
        })

    def _has_grant(self, agent_slug: str, capability: str, workspace_id: str | None) -> bool:
        conn = self._conn()
        row = conn.execute(
            "SELECT 1 FROM aegis_grants WHERE agent_slug = ? AND capability = ? AND "
            "(workspace_id = ? OR workspace_id IS NULL) LIMIT 1",
            (agent_slug, capability, workspace_id),
        ).fetchone()
        conn.close()
        return row is not None

    # ── direct trust setter + collapse revocation ───────────────────────

    def set_trust(self, agent_slug: str, score: float) -> None:
        """Set an agent's trust score directly (admin/testing). Clamped to [0,1].

        If the new score falls below 0.50, all in-memory grants for the
        agent are revoked and a `trust_collapse` event is logged.
        """
        score = max(0.0, min(1.0, score))
        conn = self._conn()
        self._ensure_module(conn, agent_slug)
        row = conn.execute(
            "SELECT trust_score FROM aegis_policies WHERE module_name = ?",
            (agent_slug,),
        ).fetchone()
        old_score = float(row["trust_score"])
        conn.execute(
            "UPDATE aegis_policies SET trust_score = ? WHERE module_name = ?",
            (score, agent_slug),
        )
        self._record_history(
            conn, agent_slug, old_score, score, score - old_score, "set_trust",
        )
        conn.commit()
        conn.close()

        # Trust collapse: revoke every grant
        if score < 0.50:
            conn = self._conn()
            removed = conn.execute(
                "SELECT capability, workspace_id FROM aegis_grants WHERE agent_slug = ?",
                (agent_slug,),
            ).fetchall()
            conn.execute("DELETE FROM aegis_grants WHERE agent_slug = ?", (agent_slug,))
            conn.commit()
            conn.close()
            if removed:
                self._log_chronicle("trust_collapse", {
                    "agent": agent_slug,
                    "score": score,
                    "revoked": [
                        {"capability": r["capability"], "workspace_id": r["workspace_id"]}
                        for r in removed
                    ],
                })

    # ── the arbiter ─────────────────────────────────────────────────────

    def check_capability(
        self,
        agent_slug: str,
        capability: str,
        workspace_id: str | None = None,
    ) -> CapabilityDecision:
        """Decide whether `agent_slug` may use `capability` in `workspace_id`.

        Algorithm:
          1. Find the manifest. No manifest → DENY.
          2. Find which class the manifest declares this capability under.
             Not declared → DENY (undeclared).
          3. Routine → always ALLOW.
          4. If user has an explicit grant for this scope → ALLOW.
          5. Notable + trust ≥ 0.75 (EXECUTOR) → ALLOW (auto-grant).
          6. Privileged → never auto-grant; PROMPT (effectively requires Settings).
          7. Otherwise → PROMPT.
        """
        manifest = self.get_manifest(agent_slug)
        if manifest is None:
            return CapabilityDecision(
                Verdict.DENY,
                f"no manifest registered for agent {agent_slug!r}",
            )

        cls = manifest.declares(capability)
        if cls is None:
            return CapabilityDecision(
                Verdict.DENY,
                f"capability {capability!r} undeclared in manifest",
            )

        # Routine — silent forever
        if cls is PermissionClass.ROUTINE:
            return CapabilityDecision(Verdict.ALLOW, "routine", cls)

        # Explicit grant trumps everything below
        if self._has_grant(agent_slug, capability, workspace_id):
            return CapabilityDecision(Verdict.ALLOW, "explicit grant", cls)

        trust = self.get_trust(agent_slug)

        # Trust-gated auto-grant for Notable
        if cls is PermissionClass.NOTABLE and trust >= 0.75:
            return CapabilityDecision(
                Verdict.ALLOW,
                f"executor tier auto-grant (trust={trust:.2f})",
                cls,
            )

        # Privileged — never granted from a check
        if cls is PermissionClass.PRIVILEGED:
            return CapabilityDecision(
                Verdict.PROMPT,
                "privileged capabilities require Settings → Security",
                cls,
            )

        return CapabilityDecision(
            Verdict.PROMPT,
            f"{cls.value.lower()} capability requires user approval",
            cls,
        )

    # ── filesystem broker ───────────────────────────────────────────────

    def fs(
        self,
        agent_slug: str,
        path,
        *,
        mode: str = "r",
        workspace_roots: list = None,
        workspace_id: str | None = None,
    ):
        """Mediated file access for an agent.

        Returns an open file handle (context manager) or raises
        PermissionDenied. Logs every call to Chronicle.
        """
        from pathlib import Path

        target = Path(path).resolve()
        roots = [Path(r).resolve() for r in (workspace_roots or [])]

        # 1. Containment: must be under at least one root
        if not any(_is_within(target, r) for r in roots):
            self._log_chronicle("fs_access_denied", {
                "agent": agent_slug, "path": str(target),
                "mode": mode, "reason": "outside_workspace_roots",
                "workspace_id": workspace_id,
            })
            raise PermissionDenied(agent_slug, f"fs:{mode}:{target}")

        # 2. Capability — "x" is exclusive-create (write-like); "+" upgrades any mode to read+write.
        cap = "fs.write.workspace" if any(c in mode for c in ("w", "a", "x", "+")) else "fs.read.workspace"
        decision = self.check_capability(agent_slug, cap, workspace_id=workspace_id)
        if decision.verdict.value != "ALLOW":
            self._log_chronicle("fs_access_denied", {
                "agent": agent_slug, "path": str(target),
                "mode": mode, "reason": decision.reason,
                "workspace_id": workspace_id,
            })
            raise PermissionDenied(agent_slug, f"fs:{mode}:{target}")

        self._log_chronicle("fs_access", {
            "agent": agent_slug, "path": str(target),
            "mode": mode, "workspace_id": workspace_id,
        })
        return open(target, mode)

    # ── network gateway ─────────────────────────────────────────────────

    DEFAULT_RATE_LIMIT_PER_MIN = 60

    def set_rate_limit(self, agent_slug: str, per_minute: int) -> None:
        if not hasattr(self, "_rate_limits"):
            self._rate_limits: dict[str, int] = {}
        self._rate_limits[agent_slug] = per_minute

    def _rate_limit(self, agent_slug: str) -> int:
        return getattr(self, "_rate_limits", {}).get(agent_slug, self.DEFAULT_RATE_LIMIT_PER_MIN)

    def _request_log(self, agent_slug: str) -> deque:
        if not hasattr(self, "_req_log"):
            self._req_log: dict[str, deque] = {}
        return self._req_log.setdefault(agent_slug, deque())

    def _check_rate_limit(self, agent_slug: str) -> bool:
        """Return True if a request is allowed; False if rate-limited."""
        log = self._request_log(agent_slug)
        now = time.monotonic()
        cutoff = now - 60.0
        while log and log[0] < cutoff:
            log.popleft()
        if len(log) >= self._rate_limit(agent_slug):
            return False
        log.append(now)
        return True

    async def network(
        self,
        agent_slug: str,
        url: str,
        *,
        method: str = "GET",
        workspace_id: str | None = None,
        **httpx_kwargs,
    ):
        """Outbound HTTP for an agent. Returns an httpx.Response.

        Raises PermissionDenied if the agent's manifest doesn't declare
        the URL's domain, if the user hasn't granted it, if the agent
        is over its rate limit, or if Aegis is otherwise denying.
        """
        import httpx as _httpx

        domain = urlparse(url).hostname or ""
        capability = f"network.outbound.{domain}"

        decision = self.check_capability(agent_slug, capability, workspace_id=workspace_id)
        if decision.verdict.value != "ALLOW":
            self._log_chronicle("network_request_denied", {
                "agent": agent_slug, "url": url, "method": method,
                "reason": decision.reason, "workspace_id": workspace_id,
            })
            raise PermissionDenied(agent_slug, f"network:{method}:{url}")

        if not self._check_rate_limit(agent_slug):
            self._log_chronicle("network_request_denied", {
                "agent": agent_slug, "url": url, "method": method,
                "reason": "rate_limit",
                "limit_per_minute": self._rate_limit(agent_slug),
                "workspace_id": workspace_id,
            })
            raise PermissionDenied(agent_slug, f"network:rate_limit:{url}")

        async with _httpx.AsyncClient() as client:
            resp = await client.request(method, url, **httpx_kwargs)

        self._log_chronicle("network_request", {
            "agent": agent_slug, "url": url, "method": method,
            "status": resp.status_code,
            "bytes_in": len(resp.content),
            "workspace_id": workspace_id,
        })
        return resp

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
