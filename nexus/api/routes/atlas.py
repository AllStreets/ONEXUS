"""Atlas graph API (N2.3) -- force-layout data for the Aurora graph view.

Nodes are atlas_facts with effective (decayed) confidence; edges are
atlas_edges. Reads the active-workspace Engram only by default; the global
view requires the same Prism Sensitive gate.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/atlas", tags=["atlas"])


@router.get("/graph")
async def graph(request: Request) -> dict:
    kernel = request.app.state.kernel
    atlas = kernel.engram.atlas
    now = datetime.now(timezone.utc)
    conn = atlas._conn()
    try:
        facts = conn.execute(
            "SELECT id, subject, relation, object, fact_class, confidence, "
            "observed_at, last_confirmed_at, source_ref FROM atlas_facts"
        ).fetchall()
        edges = conn.execute(
            "SELECT src_id, dst_id, label FROM atlas_edges").fetchall()
    finally:
        conn.close()

    nodes = []
    for r in facts:
        eff = atlas.effective_confidence(
            float(r["confidence"]), r["last_confirmed_at"], r["fact_class"], now)
        nodes.append({
            "id": r["id"], "subject": r["subject"], "relation": r["relation"],
            "object": r["object"], "fact_class": r["fact_class"],
            "confidence": round(eff, 6),
            "stored_confidence": float(r["confidence"]),
            "decayed": eff < float(r["confidence"]) * 0.85,
            "observed_at": r["observed_at"],
            "last_confirmed_at": r["last_confirmed_at"],
            "source_ref": r["source_ref"],
        })
    out_edges = [{"src": e["src_id"], "dst": e["dst_id"], "label": e["label"]}
                 for e in edges]
    return {"nodes": nodes, "edges": out_edges,
            "count": len(nodes), "edge_count": len(out_edges)}
