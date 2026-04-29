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
            trust=p["trust"],
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

    history_raw = kernel.aegis.trust_history(module)
    history = [TrustHistoryEntry(**entry) for entry in history_raw]

    return TrustDetailResponse(
        module=module,
        trust=policy["trust"],
        allowed=policy["allowed"],
        network_allowed=policy["network_allowed"],
        history=history,
    )


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

    new_trust = kernel.aegis.adjust_trust(module, body.delta, body.reason)
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
