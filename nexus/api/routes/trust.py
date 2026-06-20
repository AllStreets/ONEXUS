from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from nexus.api.models import (
    TrustAdjustRequest,
    TrustAdjustResponse,
    TrustAllResponse,
    TrustDetailResponse,
    TrustHistoryEntry,
    TrustScoreResponse,
)

router = APIRouter(prefix="/api/trust", tags=["trust"])


def _get_kernel(request: Request):
    return request.app.state.kernel


@router.get("", response_model=TrustAllResponse)
async def get_all_trust(request: Request) -> TrustAllResponse:
    """Get trust scores for all modules."""
    kernel = _get_kernel(request)
    policies = kernel.aegis.list_policies()
    scores = [
        TrustScoreResponse(
            module=p["module"],
            trust=p["trust_score"],
            allowed=p["allowed"],
            network_allowed=p["network_allowed"],
        )
        for p in policies
    ]
    return TrustAllResponse(scores=scores)


@router.get("/{module}", response_model=TrustDetailResponse)
async def get_trust_detail(module: str, request: Request) -> TrustDetailResponse:
    """Get a single module's trust score and history."""
    kernel = _get_kernel(request)
    policies = {p["module"]: p for p in kernel.aegis.list_policies()}
    policy = policies.get(module)
    if policy is None:
        raise HTTPException(status_code=404, detail=f"Module '{module}' has no trust record")

    history_raw = kernel.aegis.get_trust_history(module)
    history = [
        TrustHistoryEntry(
            timestamp=e["timestamp"],
            delta=e["delta"],
            new_trust=e["new_score"],
            reason=e["reason"],
        )
        for e in history_raw
    ]

    return TrustDetailResponse(
        module=module,
        trust=policy["trust_score"],
        allowed=policy["allowed"],
        network_allowed=policy["network_allowed"],
        history=history,
    )


@router.post("/{module}/revoke")
async def revoke_trust(module: str, request: Request) -> dict:
    """Hard-revoke a module's trust — drop it to 0.0 immediately (mirrors the
    `nexus revoke` CLI). This is the user-facing "I no longer trust this agent"
    control surfaced in the trust sheet: below 0.50 Aegis collapses every grant,
    so a revoked agent must re-earn trust before any Notable capability auto-grants
    again. The decision is written to Chronicle and broadcast on Pulse, so the
    revoke shows up live in the kernel scene and audit trail."""
    kernel = _get_kernel(request)
    policies = {p["module"]: p for p in kernel.aegis.list_policies()}
    before = policies.get(module, {}).get("trust_score")
    # set_trust(0.0) — unlike aegis.revoke() this also runs the trust-collapse
    # path that deletes every standing grant, which is what "revoke trust" means
    # to a user. Emits aegis.trust_change on Pulse + logs to Chronicle.
    kernel.aegis.set_trust(module, 0.0)
    after = kernel.aegis.get_trust(module)
    kernel.chronicle.log("api", "trust_revoked", {
        "module": module, "trust_before": before, "trust_after": after,
    })
    return {"module": module, "trust": after, "revoked": True}


@router.post("/{module}/adjust", response_model=TrustAdjustResponse)
async def adjust_trust(
    module: str, body: TrustAdjustRequest, request: Request
) -> TrustAdjustResponse:
    """Manually adjust a module's trust score."""
    kernel = _get_kernel(request)

    # Verify module exists in policies
    policies = {p["module"]: p for p in kernel.aegis.list_policies()}
    if module not in policies:
        raise HTTPException(status_code=404, detail=f"Module '{module}' has no trust record")

    current_trust = kernel.aegis.get_trust(module)
    new_trust = max(0.0, min(1.0, current_trust + body.delta))
    kernel.aegis.set_trust(module, new_trust)
    kernel.chronicle.log("api", "trust_adjusted", {
        "module": module,
        "delta": body.delta,
        "new_trust": new_trust,
        "reason": body.reason,
    })

    return TrustAdjustResponse(
        module=module,
        new_trust=new_trust,
        delta=body.delta,
        reason=body.reason,
    )
