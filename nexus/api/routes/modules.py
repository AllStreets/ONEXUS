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
        trust=policy.get("trust_score", 0),
        network_allowed=policy.get("network_allowed", False),
    )


_KERNEL_COMPONENTS = {
    "cortex": ("Message routing and orchestration engine", "1.0.0"),
    "engram": ("Persistent memory and vector storage", "1.0.0"),
    "chronicle": ("Structured event logging and audit trail", "1.0.0"),
    "aegis": ("Trust scoring and permissions engine", "1.0.0"),
    "pulse": ("Real-time event bus and pub/sub system", "1.0.0"),
}


@router.get("", response_model=ModuleListResponse)
async def list_modules(request: Request) -> ModuleListResponse:
    """List all registered modules with status and trust."""
    kernel = _get_kernel(request)
    policies = {p["module"]: p for p in kernel.aegis.list_policies()}
    modules = []

    # Kernel components
    for name, (desc, ver) in _KERNEL_COMPONENTS.items():
        policy = policies.get(name, {})
        modules.append(ModuleInfo(
            name=name,
            description=desc,
            version=ver,
            requires_network=False,
            allowed=policy.get("allowed", True),
            trust=policy.get("trust_score", 0),
            network_allowed=policy.get("network_allowed", False),
        ))

    # Cognitive modules
    for name in kernel.cortex.list_modules():
        try:
            modules.append(_build_module_info(kernel, name))
        except HTTPException:
            continue

    # Runnable agents from catalog
    catalog = getattr(request.app.state, "agent_catalog", None)
    if catalog:
        for agent in catalog.list_agents(runnable_only=True):
            agent_key = f"agent.{agent.slug}"
            policy = policies.get(agent_key, {})
            modules.append(ModuleInfo(
                name=agent_key,
                description=agent.tagline[:80] if agent.tagline else agent.name,
                version="mcp",
                requires_network=True,
                allowed=policy.get("allowed", True),
                trust=policy.get("trust_score", 0),
                network_allowed=policy.get("network_allowed", False),
            ))

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
