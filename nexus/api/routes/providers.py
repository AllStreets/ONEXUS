"""
Provider management — register, list, remove, and switch LLM providers at runtime.

Supports:
  - openai     (GPT-4o, GPT-4o-mini, o3, etc.)
  - anthropic  (Claude Opus, Sonnet, Haiku)
  - local      (llama.cpp, Ollama, vLLM — any OpenAI-compatible local server)
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from nexus.api.models import (
    RegisterProviderRequest,
    RegisterProviderResponse,
    ProviderInfoResponse,
    ProviderListResponse,
    RemoveProviderResponse,
)

router = APIRouter(prefix="/api/providers", tags=["providers"])


def _get_kernel(request: Request):
    return request.app.state.kernel


@router.get("", response_model=ProviderListResponse)
async def list_providers(request: Request) -> ProviderListResponse:
    """List all registered inference providers and their health status."""
    kernel = _get_kernel(request)
    router_ = kernel.provider_router
    if router_ is None:
        return ProviderListResponse(providers=[], default="none")

    health = await router_.health()
    providers = []
    for name, is_healthy in health.items():
        providers.append(ProviderInfoResponse(
            name=name,
            healthy=is_healthy,
            is_default=(name == router_._default),
        ))

    return ProviderListResponse(
        providers=providers,
        default=router_._default,
    )


@router.post("", response_model=RegisterProviderResponse)
async def register_provider(
    request: Request,
    body: RegisterProviderRequest,
) -> RegisterProviderResponse:
    """Register a new inference provider at runtime.

    Supported providers:
      - "openai"    — requires api_key, optional model (default: gpt-4o-mini)
      - "anthropic" — requires api_key, optional model (default: claude-sonnet-4-20250514)
      - "local"     — optional base_url (default: http://localhost:8384)
    """
    kernel = _get_kernel(request)
    router_ = kernel.provider_router
    if router_ is None:
        raise HTTPException(status_code=503, detail="Provider router not initialized")

    provider_type = body.provider.lower().strip()

    if provider_type == "openai":
        if not body.api_key:
            raise HTTPException(status_code=400, detail="api_key required for OpenAI provider")
        try:
            from nexus.inference.openai_provider import OpenAIProvider
        except ImportError:
            raise HTTPException(status_code=400, detail="openai package not installed (pip install openai)")
        model = body.model or "gpt-4o-mini"
        provider = OpenAIProvider(api_key=body.api_key, model=model)
        router_.register(provider)

    elif provider_type == "anthropic":
        if not body.api_key:
            raise HTTPException(status_code=400, detail="api_key required for Anthropic provider")
        try:
            from nexus.inference.anthropic_provider import AnthropicProvider
        except ImportError:
            raise HTTPException(status_code=400, detail="anthropic package not installed (pip install anthropic)")
        model = body.model or "claude-sonnet-4-20250514"
        provider = AnthropicProvider(api_key=body.api_key, model=model)
        router_.register(provider)

    elif provider_type == "local":
        from nexus.inference.local import LocalProvider
        base_url = body.base_url or f"http://localhost:{kernel.config.llm_port}"
        provider = LocalProvider(base_url=base_url)
        router_.register(provider)

    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown provider type '{provider_type}'. Supported: openai, anthropic, local",
        )

    if body.set_default:
        router_._default = provider_type

    kernel.chronicle.log("providers", "provider_registered", {
        "provider": provider_type,
        "model": body.model,
        "set_default": body.set_default,
    })

    return RegisterProviderResponse(
        provider=provider_type,
        registered=True,
        is_default=(router_._default == provider_type),
        message=f"{provider_type} provider registered"
            + (f" with model {body.model}" if body.model else "")
            + (" (set as default)" if body.set_default else ""),
    )


@router.delete("/{provider_name}", response_model=RemoveProviderResponse)
async def remove_provider(
    request: Request,
    provider_name: str,
) -> RemoveProviderResponse:
    """Remove a registered provider. Cannot remove the current default."""
    kernel = _get_kernel(request)
    router_ = kernel.provider_router
    if router_ is None:
        raise HTTPException(status_code=503, detail="Provider router not initialized")

    name = provider_name.lower().strip()

    if name not in router_._providers:
        raise HTTPException(status_code=404, detail=f"Provider '{name}' not registered")

    was_default = (name == router_._default)
    del router_._providers[name]

    # If we removed the default, pick another or clear it
    if was_default:
        if router_._providers:
            router_._default = next(iter(router_._providers))
        else:
            router_._default = None

    kernel.chronicle.log("providers", "provider_removed", {"provider": name})

    return RemoveProviderResponse(
        provider=name,
        removed=True,
        message=f"{name} provider removed",
    )


@router.post("/default/{provider_name}")
async def set_default_provider(
    request: Request,
    provider_name: str,
):
    """Switch the default inference provider."""
    kernel = _get_kernel(request)
    router_ = kernel.provider_router
    if router_ is None:
        raise HTTPException(status_code=503, detail="Provider router not initialized")

    name = provider_name.lower().strip()

    if name not in router_._providers:
        raise HTTPException(status_code=404, detail=f"Provider '{name}' not registered. Register it first.")

    old_default = router_._default
    router_._default = name

    kernel.chronicle.log("providers", "default_changed", {
        "from": old_default,
        "to": name,
    })

    return {"default": name, "previous": old_default}


def _find_ollama_binary() -> str | None:
    """Locate the ``ollama`` executable.

    A GUI app's PATH is often minimal, so we also probe the common install
    prefixes (Ollama's own installer drops it under ~/.local/bin).
    """
    candidates = [
        shutil.which("ollama"),
        str(Path.home() / ".local" / "bin" / "ollama"),
        "/usr/local/bin/ollama",
        "/opt/homebrew/bin/ollama",
        "/usr/bin/ollama",
    ]
    return next((c for c in candidates if c and Path(c).exists()), None)


@router.post("/ollama/restart")
async def restart_ollama(request: Request) -> dict:
    """Start (or restart) the local Ollama server.

    Desktop convenience: when the user has quit Ollama, this brings the
    local-inference slot back without leaving the app. Locates the binary,
    terminates any running ``ollama serve``, and spawns a fresh detached one.
    """
    binary = _find_ollama_binary()
    if binary is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "ollama binary not found (looked on PATH, ~/.local/bin, "
                "/usr/local/bin, /opt/homebrew/bin). Install Ollama from ollama.com."
            ),
        )

    # Best-effort terminate any running `ollama serve` so this is a true restart.
    killed = False
    try:
        result = subprocess.run(  # noqa: S603, S607
            ["pkill", "-f", "ollama serve"], capture_output=True, timeout=5
        )
        killed = result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        pass

    try:
        subprocess.Popen(  # noqa: S603
            [binary, "serve"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"failed to start ollama: {exc}") from exc

    kernel = getattr(request.app.state, "kernel", None)
    chronicle = getattr(kernel, "chronicle", None) if kernel is not None else None
    if chronicle is not None:
        chronicle.log("providers", "ollama_restart", {"binary": binary, "killed_existing": killed})

    return {
        "started": True,
        "binary": binary,
        "killed_existing": killed,
        "message": "Ollama restarted" if killed else "Ollama started",
    }
