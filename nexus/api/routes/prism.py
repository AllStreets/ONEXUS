"""Prism cross-domain synthesis API (N2.1) -- Aegis-gated cross-partition read.

Cross-workspace synthesis requires the `engram.read.global` Sensitive
capability, which Aegis always prompts for absent an explicit grant. When
ungated this route returns {gated: True, findings: []} rather than reading
every partition silently.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Query, Request

from nexus.config import NexusConfig
from nexus.kernel.engram import Engram
from nexus.modules.prism import CrossDomainSynthesizer
from nexus.workspaces.manager import WorkspaceManager

router = APIRouter(prefix="/api/prism", tags=["prism"])


def _manager(request: Request) -> WorkspaceManager:
    mgr = getattr(request.app.state, "workspace_manager", None)
    if mgr is not None:
        return mgr
    kernel = getattr(request.app.state, "kernel", None)
    data_dir = Path(kernel.config.data_dir) if kernel else Path(NexusConfig().data_dir)
    ws_root = data_dir / "workspaces"
    ws_root.mkdir(parents=True, exist_ok=True)
    mgr = WorkspaceManager(root=ws_root)
    request.app.state.workspace_manager = mgr
    return mgr


def _load_partitions(mgr: WorkspaceManager):
    partitions = []
    for ws in mgr.list():
        db = mgr.workspace_dir(ws.workspace_id) / "engram" / "episodic.sqlite"
        if not db.exists():
            continue
        eng = Engram(db)
        conn = eng.atlas._conn()
        try:
            rows = conn.execute(
                "SELECT id, subject, relation, object, confidence, source_ref "
                "FROM atlas_facts").fetchall()
        except Exception:
            rows = []
        finally:
            conn.close()
        partitions.append((ws.workspace_id, [
            {"id": r["id"], "subject": r["subject"], "relation": r["relation"],
             "object": r["object"], "confidence": float(r["confidence"]),
             "source_ref": r["source_ref"]} for r in rows]))
    return partitions


@router.get("/synthesis")
async def synthesis(request: Request,
                    mode: str = Query(default="recurring",
                                      pattern="^(recurring|contradictions)$")) -> dict:
    kernel = request.app.state.kernel
    decision = kernel.aegis.check_capability("prism", "engram.read.global")
    if decision.verdict.value != "ALLOW":
        return {"gated": True, "reason": decision.reason, "findings": [],
                "partitions": [], "mode": mode}

    mgr = _manager(request)
    partitions = _load_partitions(mgr)
    synth = CrossDomainSynthesizer()
    findings = (synth.contradictions(partitions) if mode == "contradictions"
                else synth.recurring_entities(partitions))
    kernel.chronicle.log("prism", "synthesis", {
        "mode": "contradictions" if mode == "contradictions" else "recurring_entities",
        "partitions": [w for w, _ in partitions], "findings": len(findings),
    })
    return {"gated": False, "mode": mode, "findings": findings,
            "partitions": [w for w, _ in partitions]}
