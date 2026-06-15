"""Federation workspace sync (N3.2).

Workspace-scoped, allowlist-only, Aegis-gated sync of Atlas facts between
NEXUS instances. NETWORK INVARIANT: this module imports neither httpx nor
socket — all real peer HTTP still flows through FederationProtocol /
PeerDiscovery, which route through KernelHttpClient -> aegis.network().
Local tests use LoopbackPeerClient (two in-process kernels, no sockets).
"""
from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any


class PeerAllowlist:
    """Per-workspace allowlist of peer IDs permitted to sync."""

    def __init__(self, data_path: Path):
        self.data_path = Path(data_path)
        self.data_path.mkdir(parents=True, exist_ok=True)
        self._file = self.data_path / "federation_sync_allowlist.json"
        self._allow: dict[str, list[str]] = {}
        self.load()

    def allow(self, peer_id: str, workspace_id: str) -> None:
        self._allow.setdefault(workspace_id, [])
        if peer_id not in self._allow[workspace_id]:
            self._allow[workspace_id].append(peer_id)
        self.save()

    def revoke(self, peer_id: str, workspace_id: str) -> None:
        if workspace_id in self._allow:
            self._allow[workspace_id] = [p for p in self._allow[workspace_id] if p != peer_id]
        self.save()

    def is_allowed(self, peer_id: str, workspace_id: str) -> bool:
        return peer_id in self._allow.get(workspace_id, [])

    def workspaces_for(self, peer_id: str) -> list[str]:
        return [ws for ws, peers in self._allow.items() if peer_id in peers]

    def entries(self) -> list[dict[str, str]]:
        return [{"peer_id": p, "workspace_id": ws}
                for ws, peers in self._allow.items() for p in peers]

    def save(self) -> None:
        self._file.write_text(json.dumps(self._allow, indent=2))

    def load(self) -> None:
        if self._file.exists():
            try:
                self._allow = json.loads(self._file.read_text())
            except json.JSONDecodeError:
                self._allow = {}


InboundHandler = Callable[[str, list[dict[str, Any]]], Awaitable[dict[str, Any]]]


class LoopbackPeerClient:
    """Test transport: routes an outbound sync into a peer's inbound handler."""

    def __init__(self, inbound: InboundHandler):
        self._inbound = inbound

    async def push_atlas(self, workspace_id: str,
                         facts: list[dict[str, Any]]) -> dict[str, Any]:
        return await self._inbound(workspace_id, facts)


class WorkspaceSyncEngine:
    """Workspace-scoped, allowlist-only, Aegis-gated Atlas-fact sync."""

    CAPABILITY = "federation.sync.workspace"

    def __init__(self, *, instance_id, aegis, chronicle, allowlist, engram_for):
        self._instance_id = instance_id
        self._aegis = aegis
        self._chronicle = chronicle
        self._allowlist = allowlist
        self._engram_for = engram_for   # Callable[[workspace_id], Engram]
        self._enabled = True

    def set_sync_enabled(self, value: bool) -> None:
        self._enabled = bool(value)

    @property
    def sync_enabled(self) -> bool:
        return self._enabled

    def _log(self, action, payload):
        if self._chronicle is not None:
            self._chronicle.log("federation", action, payload)

    def _export_atlas(self, workspace_id):
        eng = self._engram_for(workspace_id)
        conn = eng.atlas._conn()
        try:
            rows = conn.execute(
                "SELECT subject, relation, object, confidence, fact_class, "
                "source_ref FROM atlas_facts").fetchall()
        finally:
            conn.close()
        return [{"subject": r["subject"], "relation": r["relation"],
                 "object": r["object"], "confidence": float(r["confidence"]),
                 "fact_class": r["fact_class"], "source_ref": r["source_ref"]}
                for r in rows]

    async def push_workspace(self, peer_id, workspace_id, client):
        if not self._enabled:
            self._log("sync_skipped", {"peer": peer_id, "workspace": workspace_id,
                                      "reason": "kill_switch"})
            return {"pushed": 0, "gated": True, "blocked": "kill_switch"}
        if not self._allowlist.is_allowed(peer_id, workspace_id):
            self._log("sync_denied", {"peer": peer_id, "workspace": workspace_id,
                                     "reason": "not_allowlisted"})
            return {"pushed": 0, "gated": True, "blocked": "not_allowlisted"}
        if self._aegis is not None:
            decision = self._aegis.check_capability("federation", self.CAPABILITY, workspace_id)
            if decision.verdict.value != "ALLOW":
                self._log("sync_denied", {"peer": peer_id, "workspace": workspace_id,
                                         "reason": decision.reason})
                return {"pushed": 0, "gated": True, "blocked": "aegis"}
        facts = self._export_atlas(workspace_id)
        ack = await client.push_atlas(workspace_id, facts)
        self._log("sync_push", {"peer": peer_id, "workspace": workspace_id,
                               "count": len(facts), "ack": ack})
        return {"pushed": len(facts), "gated": False, "blocked": None, "ack": ack}

    async def handle_inbound_atlas(self, workspace_id, facts):
        eng = self._engram_for(workspace_id)
        merged = 0
        for f in facts:
            eng.atlas.observe(f["subject"], f["relation"], f["object"],
                              confidence=float(f.get("confidence", 0.5)),
                              fact_class=f.get("fact_class", "default") or "default",
                              source_ref=f.get("source_ref") or "")
            merged += 1
        self._log("sync_merge", {"workspace": workspace_id, "merged": merged})
        return {"merged": merged}
