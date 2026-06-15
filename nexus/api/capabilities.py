"""Truthful capability grounding for agent personas.

Agents answering through an LLM tend to confabulate platform features
("I've opened a PR on your GitHub", "connect your account via OAuth").
This module computes a short, factual system-prompt segment from the live
app state at request time — what providers are actually configured, how
many catalog agents are actually installed, which in-OS tools actually
exist — and ends with an explicit instruction that anything unlisted does
not exist and must not be invented.

Inject via ``ground_persona`` wherever a built-in agent persona is
assembled (the Cortex launcher paths and the conversation stream path).
Injection is idempotent: a persona that already carries the grounding
marker is returned unchanged.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

GROUNDING_MARKER = "== Ground truth about this ONEXUS instance =="


def _provider_names(kernel: Any) -> list[str]:
    router = getattr(kernel, "provider_router", None)
    if router is None:
        return []
    try:
        return sorted(router.list_providers())
    except Exception:
        return []


def _catalog_count(app_state: Any) -> int:
    catalog = getattr(app_state, "agent_catalog", None)
    if catalog is None:
        return 0
    try:
        return int(catalog.count())
    except Exception:
        return 0


def _codebase_root_count(app_state: Any, kernel: Any) -> int:
    registry = getattr(app_state, "codebase_registry", None)
    if registry is None and kernel is not None:
        try:
            from nexus.workspaces.codebases import CodebaseRegistry
            registry = CodebaseRegistry(Path(kernel.config.data_dir))
        except Exception:
            return 0
    if registry is None:
        return 0
    try:
        return len(registry.list())
    except Exception:
        return 0


def build_capability_context(app_state: Any) -> str:
    """Build the truthful capability segment from the live app state.

    Computed per request — never cached — so the listed providers, agent
    counts, and registered codebase roots reflect what exists right now.
    """
    kernel = getattr(app_state, "kernel", None)
    lines = [GROUNDING_MARKER]

    providers = _provider_names(kernel)
    if providers:
        lines.append(f"LLM providers configured: {', '.join(providers)}.")
    else:
        lines.append(
            "No LLM providers are configured; replies come from the "
            "deterministic built-in modules."
        )

    catalog_count = _catalog_count(app_state)
    if catalog_count:
        lines.append(
            f"Agent catalog: {catalog_count} agents installed (the user can "
            f"browse, search, and launch them from the catalog page)."
        )
    else:
        lines.append("No agent catalog is attached to this instance.")

    roots = _codebase_root_count(app_state, kernel)
    lines.append(
        "In-OS tools available to the user: Workshop code execution "
        "(sandboxed Python/JavaScript/shell, per-workspace opt-in), in-OS "
        "web search, file uploads into the conversation, and local codebase "
        f"roots for read-only source browsing and attachment "
        f"({roots} registered)."
    )

    lines.append(
        "Integrations not listed above do not exist in this OS. There is no "
        "GitHub integration, no OAuth or account linking, and no connectors "
        "to external services beyond this list. If the user asks about a "
        "capability that is not listed here, say plainly that it does not "
        "exist yet — never guess, imply, or roleplay that it does."
    )
    return "\n".join(lines)


def ground_persona(persona: str, app_state: Any) -> str:
    """Append the capability grounding to a persona prompt, exactly once."""
    if GROUNDING_MARKER in persona:
        return persona
    return f"{persona}\n\n{build_capability_context(app_state)}"
