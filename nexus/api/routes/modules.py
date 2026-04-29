from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from nexus.api.models import (
    ModuleDetailResponse,
    ModuleInfo,
    ModuleListResponse,
    PolicyActionResponse,
)

router = APIRouter(prefix="/api/modules", tags=["modules"])


def _get_kernel(request: Request):
    return request.app.state.kernel


def _build_module_info(kernel, name: str) -> ModuleInfo:
    """Build a ModuleInfo from kernel state for a given module name."""
    module = kernel.cortex._modules.get(name)
    if module is None:
        raise HTTPException(status_code=404, detail=f"Module '{name}' not found")

    policies = {p["module"]: p for p in kernel.aegis.list_policies()}
    policy = policies.get(name, {})

    return ModuleInfo(
        name=module.name,
        description=module.description,
        version=module.version,
        requires_network=module.requires_network,
        allowed=policy.get("allowed", False),
        trust=policy.get("trust", 0),
        network_allowed=policy.get("network_allowed", False),
    )


@router.get("", response_model=ModuleListResponse)
async def list_modules(request: Request) -> ModuleListResponse:
    """List all registered modules with status and trust."""
    kernel = _get_kernel(request)
    modules = []
    for name in kernel.cortex.list_modules():
        try:
            modules.append(_build_module_info(kernel, name))
        except HTTPException:
            continue
    return ModuleListResponse(modules=modules, count=len(modules))


@router.get("/{name}", response_model=ModuleDetailResponse)
async def get_module(name: str, request: Request) -> ModuleDetailResponse:
    """Get module details and trust score."""
    kernel = _get_kernel(request)
    info = _build_module_info(kernel, name)
    return ModuleDetailResponse(module=info)


@router.post("/{name}/allow", response_model=PolicyActionResponse)
async def allow_module(name: str, request: Request) -> PolicyActionResponse:
    """Enable a module."""
    kernel = _get_kernel(request)
    if name not in kernel.cortex._modules:
        raise HTTPException(status_code=404, detail=f"Module '{name}' not found")
    kernel.aegis.set_policy(name, allowed=True)
    kernel.chronicle.log("api", "module_allowed", {"module": name})
    return PolicyActionResponse(module=name, action="allow", success=True)


@router.post("/{name}/deny", response_model=PolicyActionResponse)
async def deny_module(name: str, request: Request) -> PolicyActionResponse:
    """Disable a module."""
    kernel = _get_kernel(request)
    if name not in kernel.cortex._modules:
        raise HTTPException(status_code=404, detail=f"Module '{name}' not found")
    kernel.aegis.set_policy(name, allowed=False)
    kernel.chronicle.log("api", "module_denied", {"module": name})
    return PolicyActionResponse(module=name, action="deny", success=True)
