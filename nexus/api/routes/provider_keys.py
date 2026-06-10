"""Provider API-key management — Settings → Providers (cloud) add/remove.

The Aurora UI POSTs an OpenAI or Anthropic API key here; this module:

  1. Persists it to ``{data_dir}/provider_keys.json`` with ``chmod 0600`` so
     only the current user can read it. We don't use macOS Keychain because
     it requires an extra dependency (``keyring``) we don't currently bundle.
     The file is JSON of the shape ``{"openai": "sk-...", "anthropic": "sk-..."}``.

  2. Registers the matching provider in the live ``kernel.provider_router``
     so the key is usable immediately — no restart required.

  3. Logs to chronicle. The key value is NEVER part of any chronicle entry,
     log line, or response body. The list endpoint returns only a tail
     fingerprint (``...1234``) so the user can recognize which key is saved
     without it being readable on screen.

Startup integration: ``load_keys_into_router(kernel)`` is called once at app
startup so saved keys survive restarts.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field


router = APIRouter(prefix="/api/providers/keys", tags=["providers"])


SUPPORTED_PROVIDERS = {"openai", "anthropic"}


# ── Persistence helpers ─────────────────────────────────────────────────────


def _key_path_from_kernel(kernel) -> Path:
    data_dir = Path(kernel.config.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "provider_keys.json"


def _load_keys(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
        if not isinstance(data, dict):
            return {}
        return {k: str(v) for k, v in data.items() if isinstance(v, str) and v}
    except Exception:
        return {}


def _save_keys(path: Path, keys: dict[str, str]) -> None:
    # Write atomically: write to tmp, chmod, rename.
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(keys, indent=2), encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        # chmod isn't critical on filesystems that don't honor it (FAT, etc.);
        # the parent data_dir is already user-scoped on macOS/Linux.
        pass
    os.replace(tmp, path)


def _fingerprint(key: str) -> str:
    """Last 4 chars + prefix marker. Safe to display."""
    if not key:
        return ""
    if len(key) <= 8:
        return "•" * len(key)
    head = key[:3]
    tail = key[-4:]
    return f"{head}…{tail}"


# ── Live router registration ─────────────────────────────────────────────────


def _register_provider_with_key(kernel, provider_type: str, api_key: str) -> None:
    """Drop a provider into kernel.provider_router using the saved key."""
    router_ = getattr(kernel, "provider_router", None)
    if router_ is None:
        return
    if provider_type == "openai":
        try:
            from nexus.inference.openai_provider import OpenAIProvider
        except ImportError:
            raise HTTPException(
                status_code=400,
                detail="openai package not installed (run: pip install openai)",
            )
        router_.register(OpenAIProvider(api_key=api_key, model="gpt-4o-mini"))
    elif provider_type == "anthropic":
        try:
            from nexus.inference.anthropic_provider import AnthropicProvider
        except ImportError:
            raise HTTPException(
                status_code=400,
                detail="anthropic package not installed (run: pip install anthropic)",
            )
        router_.register(AnthropicProvider(api_key=api_key, model="claude-sonnet-4-20250514"))


def load_keys_into_router(kernel) -> None:
    """Called once at startup so saved keys survive a server restart."""
    path = _key_path_from_kernel(kernel)
    keys = _load_keys(path)
    for slug, api_key in keys.items():
        if slug not in SUPPORTED_PROVIDERS:
            continue
        try:
            _register_provider_with_key(kernel, slug, api_key)
        except Exception:
            # Don't let one bad key block startup — the user can re-add via UI.
            continue


# ── Endpoints ────────────────────────────────────────────────────────────────


class SaveKeyBody(BaseModel):
    provider: str = Field(..., description="openai or anthropic")
    api_key: str = Field(..., min_length=8)


@router.get("")
async def list_keys(request: Request) -> dict:
    """Return only fingerprints — never the key itself."""
    kernel = request.app.state.kernel
    path = _key_path_from_kernel(kernel)
    keys = _load_keys(path)
    out: dict[str, dict] = {}
    for slug in SUPPORTED_PROVIDERS:
        key = keys.get(slug, "")
        out[slug] = {
            "configured": bool(key),
            "fingerprint": _fingerprint(key) if key else "",
        }
    return {"keys": out}


@router.post("")
async def save_key(body: SaveKeyBody, request: Request) -> dict:
    slug = body.provider.lower().strip()
    if slug not in SUPPORTED_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail=f"unsupported provider {slug!r}. supported: openai, anthropic",
        )
    api_key = body.api_key.strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="api_key cannot be empty")

    kernel = request.app.state.kernel
    path = _key_path_from_kernel(kernel)
    keys = _load_keys(path)
    keys[slug] = api_key
    _save_keys(path, keys)

    # Register with the live router so the key works immediately.
    _register_provider_with_key(kernel, slug, api_key)

    # Audit log — key VALUE is intentionally not stored here, only the event.
    try:
        kernel.chronicle.log("providers", "key_saved", {
            "provider": slug,
            "fingerprint": _fingerprint(api_key),
        })
    except Exception:
        pass

    return {"provider": slug, "configured": True, "fingerprint": _fingerprint(api_key)}


@router.delete("/{provider}")
async def delete_key(provider: str, request: Request) -> dict:
    slug = provider.lower().strip()
    if slug not in SUPPORTED_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"unsupported provider {slug!r}")

    kernel = request.app.state.kernel
    path = _key_path_from_kernel(kernel)
    keys = _load_keys(path)
    if slug not in keys:
        return {"provider": slug, "configured": False}
    del keys[slug]
    _save_keys(path, keys)

    # Remove from the live router too.
    router_ = getattr(kernel, "provider_router", None)
    if router_ is not None and slug in getattr(router_, "_providers", {}):
        try:
            del router_._providers[slug]
            if getattr(router_, "_default", None) == slug:
                router_._default = next(iter(router_._providers), None)
        except Exception:
            pass

    try:
        kernel.chronicle.log("providers", "key_removed", {"provider": slug})
    except Exception:
        pass

    return {"provider": slug, "configured": False}
