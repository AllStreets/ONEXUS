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
import sys
import threading
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

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


# ── Local-model management (Ollama) ──────────────────────────────────────────
# Curated for ONEXUS — an agent OS that fires many tool/function calls. The
# Qwen2.5 family is the standout for tool-calling fidelity; sizes tuned for a
# 64 GB Apple-silicon machine. `note`/`size` are human hints for the picker.
RECOMMENDED_LOCAL_MODELS: list[dict] = [
    {"name": "qwen2.5:32b", "size": "~20 GB", "note": "Top pick — best agentic/tool-calling fidelity", "recommended": True},
    {"name": "qwen2.5:14b", "size": "~9 GB",  "note": "Snappy — great balance for fast tool loops", "recommended": True},
    {"name": "qwen2.5:7b",  "size": "~5 GB",  "note": "Lean — light + quick"},
    {"name": "gpt-oss:20b", "size": "~14 GB", "note": "OpenAI open weights — fast, strong tool use"},
    {"name": "llama3.3:70b","size": "~43 GB", "note": "Max power (Q4) — slower"},
    {"name": "llama3.1:8b", "size": "~5 GB",  "note": "Small default — fallback"},
]


def _active_model_file(kernel) -> Path:
    return Path(kernel.config.data_dir) / "active_local_model"


def read_active_local_model(data_dir) -> str | None:
    """Read the persisted active local model name, if any. Used at boot to
    reconstruct the Ollama provider with the user's last choice."""
    try:
        p = Path(data_dir) / "active_local_model"
        if p.exists():
            v = p.read_text().strip()
            return v or None
    except Exception:
        pass
    return None


def _write_active_local_model(kernel, name: str) -> None:
    try:
        _active_model_file(kernel).write_text(name.strip() + "\n")
    except Exception:
        pass


def _ollama_provider(kernel):
    router_ = kernel.provider_router
    if router_ is None:
        return None
    return router_._providers.get("ollama")


def _pull_state(request: Request) -> dict:
    st = getattr(request.app.state, "ollama_pulls", None)
    if st is None:
        st = {}
        request.app.state.ollama_pulls = st
    return st


class SetModelBody(BaseModel):
    model: str


class PullModelBody(BaseModel):
    model: str
    activate: bool = True   # switch to it once the pull finishes


@router.get("/ollama/models")
async def list_ollama_models(request: Request) -> dict:
    """List installed Ollama models, the active one, the curated recommended
    set, and any in-progress pulls — everything the local-model switcher needs."""
    kernel = _get_kernel(request)
    provider = _ollama_provider(kernel)
    installed: list[str] = []
    active = None
    if provider is not None:
        try:
            installed = await provider.list_models()
        except Exception:
            installed = []
        active = getattr(provider, "model", None)
    installed_set = set(installed)
    recommended = [{**m, "installed": m["name"] in installed_set} for m in RECOMMENDED_LOCAL_MODELS]
    return {
        "installed": installed,
        "active": active,
        "recommended": recommended,
        "pulls": _pull_state(request),
        "ollama_present": _find_ollama_binary() is not None,
    }


@router.post("/ollama/model")
async def set_ollama_model(body: SetModelBody, request: Request) -> dict:
    """Switch the active local model. The previously active model stays
    installed and can be switched back to — only the active selection changes."""
    kernel = _get_kernel(request)
    provider = _ollama_provider(kernel)
    if provider is None or not hasattr(provider, "set_model"):
        raise HTTPException(status_code=503, detail="Ollama provider not available")
    model = body.model.strip()
    if not model:
        raise HTTPException(status_code=400, detail="model required")
    installed = await provider.list_models()
    if model not in installed:
        raise HTTPException(
            status_code=409,
            detail=f"'{model}' is not installed in Ollama yet. Add it first (it will be pulled).",
        )
    previous = provider.set_model(model)
    _write_active_local_model(kernel, model)
    kernel.chronicle.log("providers", "local_model_switched", {"from": previous, "to": model})
    return {"active": model, "previous": previous}


@router.post("/ollama/pull")
async def pull_ollama_model(body: PullModelBody, request: Request) -> dict:
    """Add a local model: `ollama pull <model>` in the background. When it
    finishes (and activate=True) it becomes the active model, replacing the
    current one. Poll GET /ollama/models for `pulls[model].status`."""
    binary = _find_ollama_binary()
    if binary is None:
        raise HTTPException(status_code=404, detail="ollama binary not found — install Ollama from ollama.com")
    kernel = _get_kernel(request)
    provider = _ollama_provider(kernel)
    model = body.model.strip()
    if not model:
        raise HTTPException(status_code=400, detail="model required")
    pulls = _pull_state(request)
    if pulls.get(model, {}).get("status") == "pulling":
        return {"model": model, "status": "pulling", "already": True}
    pulls[model] = {"status": "pulling", "detail": ""}

    def _run():
        try:
            res = subprocess.run([binary, "pull", model], capture_output=True, text=True, timeout=3600)  # noqa: S603
            if res.returncode == 0:
                pulls[model] = {"status": "done", "detail": ""}
                if body.activate and provider is not None and hasattr(provider, "set_model"):
                    prev = provider.set_model(model)
                    _write_active_local_model(kernel, model)
                    try:
                        kernel.chronicle.log("providers", "local_model_switched",
                                             {"from": prev, "to": model, "via": "pull"})
                    except Exception:
                        pass
            else:
                pulls[model] = {"status": "error", "detail": (res.stderr or res.stdout or "pull failed")[-400:]}
        except subprocess.TimeoutExpired:
            pulls[model] = {"status": "error", "detail": "pull timed out (>1h)"}
        except Exception as exc:  # noqa: BLE001
            pulls[model] = {"status": "error", "detail": str(exc)[-400:]}

    threading.Thread(target=_run, daemon=True).start()
    try:
        kernel.chronicle.log("providers", "local_model_pull_started", {"model": model, "activate": body.activate})
    except Exception:
        pass
    return {"model": model, "status": "pulling", "activate": body.activate}


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


def _ollama_app_path() -> Path | None:
    """Return the macOS Ollama ``.app`` bundle if the binary lives inside one.

    The binary at ~/.local/bin/ollama is usually a symlink into
    ``/Applications/Ollama.app/Contents/Resources/ollama``. Launching the
    bundle (instead of a bare ``ollama serve``) starts the menu-bar app the
    user recognises — it shows its icon and appears by name in Activity
    Monitor, where a headless ``ollama serve`` is easy to miss.
    """
    binary = _find_ollama_binary()
    if binary is None:
        return None
    try:
        resolved = Path(binary).resolve()
    except OSError:
        return None
    for parent in resolved.parents:
        if parent.suffix == ".app":
            return parent
    return None


@router.post("/ollama/restart")
async def restart_ollama(request: Request) -> dict:
    """Start (or restart) local Ollama.

    Desktop convenience: when the user has quit Ollama, this brings the
    local-inference slot back without leaving the app. On macOS it launches the
    Ollama menu-bar app (visible, with its icon); elsewhere it spawns a headless
    ``ollama serve``. Either way any running ``ollama serve`` is terminated
    first so this is a true restart.
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

    # Best-effort terminate any running `ollama serve` so this is a true restart
    # (and so the relaunched app can bind port 11434 cleanly).
    killed = False
    try:
        result = subprocess.run(  # noqa: S603, S607
            ["pkill", "-f", "ollama serve"], capture_output=True, timeout=5
        )
        killed = result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        pass

    app = _ollama_app_path() if sys.platform == "darwin" else None
    launched_via = "app" if app is not None else "serve"
    try:
        if app is not None:
            # `open` returns immediately; the app (re)starts its own server and
            # shows the menu-bar icon.
            subprocess.run(["open", str(app)], capture_output=True, timeout=10)  # noqa: S603, S607
        else:
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
        chronicle.log(
            "providers",
            "ollama_restart",
            {"binary": binary, "killed_existing": killed, "via": launched_via},
        )

    return {
        "started": True,
        "binary": binary,
        "killed_existing": killed,
        "launched_via": launched_via,
        "message": "Ollama restarted" if killed else "Ollama started",
    }
