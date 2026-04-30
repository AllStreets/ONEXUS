"""
MCP resource definitions for NEXUS.

Exposes read-only views into system state as MCP resources
that clients can subscribe to or poll.
"""
from __future__ import annotations

import json
from typing import Any


# ---------------------------------------------------------------------------
# Resource catalogue
# ---------------------------------------------------------------------------

RESOURCE_DEFINITIONS: list[dict[str, Any]] = [
    {
        "uri": "nexus://modules",
        "name": "NEXUS Modules",
        "description": "List of all registered modules with description and version.",
        "mimeType": "application/json",
    },
    {
        "uri": "nexus://agents",
        "name": "NEXUS Agents",
        "description": "List of all registered agents with trust tiers and capabilities.",
        "mimeType": "application/json",
    },
    {
        "uri": "nexus://trust",
        "name": "Trust Scores",
        "description": "Current Aegis trust scores and permission state for all modules.",
        "mimeType": "application/json",
    },
    {
        "uri": "nexus://config",
        "name": "System Configuration",
        "description": "Current NEXUS configuration (sensitive fields redacted).",
        "mimeType": "application/json",
    },
]


def get_resource_definitions() -> list[dict[str, Any]]:
    """Return raw resource definitions (always available)."""
    return RESOURCE_DEFINITIONS


# ---------------------------------------------------------------------------
# Resource handlers
# ---------------------------------------------------------------------------

class ResourceHandlers:
    """Resolves MCP resource URIs to live system data.

    Requires a kernel_context dict containing live instances of:
        cortex, engram, chronicle, aegis, pulse, config
    """

    def __init__(self, kernel_context: dict[str, Any]) -> None:
        self._ctx = kernel_context
        self._dispatch: dict[str, Any] = {
            "nexus://modules": self._read_modules,
            "nexus://agents": self._read_agents,
            "nexus://trust": self._read_trust,
            "nexus://config": self._read_config,
        }

    async def read(self, uri: str) -> str:
        """Return JSON string for the given resource URI."""
        handler = self._dispatch.get(uri)
        if handler is None:
            return json.dumps({"error": f"Unknown resource: {uri}"})
        try:
            return await handler()
        except Exception as exc:
            return json.dumps({"error": f"Failed to read {uri}: {exc}"})

    # ------------------------------------------------------------------
    # Individual readers
    # ------------------------------------------------------------------

    async def _read_modules(self) -> str:
        cortex = self._ctx.get("cortex")
        if cortex is None:
            return json.dumps({"modules": []})

        modules = []
        for name, mod in sorted(cortex._modules.items()):
            if hasattr(mod, "analyze"):
                continue  # agents handled separately
            modules.append({
                "name": name,
                "description": mod.description,
                "version": mod.version,
                "requires_network": getattr(mod, "requires_network", False),
            })
        return json.dumps({"count": len(modules), "modules": modules})

    async def _read_agents(self) -> str:
        cortex = self._ctx.get("cortex")
        aegis = self._ctx.get("aegis")
        if cortex is None:
            return json.dumps({"agents": []})

        agents = []
        for name, mod in sorted(cortex._modules.items()):
            if not hasattr(mod, "analyze"):
                continue
            entry: dict[str, Any] = {
                "name": name,
                "description": mod.description,
                "version": mod.version,
                "requires_network": getattr(mod, "requires_network", False),
                "watch_events": getattr(mod, "watch_events", []),
                "coordination_targets": getattr(mod, "coordination_targets", []),
            }
            if aegis:
                entry["trust"] = aegis.get_trust(name)
                entry["tier"] = aegis.get_tier(name)
            agents.append(entry)
        return json.dumps({"count": len(agents), "agents": agents})

    async def _read_trust(self) -> str:
        aegis = self._ctx.get("aegis")
        if aegis is None:
            return json.dumps({"policies": []})
        policies = aegis.list_policies()
        return json.dumps({"count": len(policies), "policies": policies})

    async def _read_config(self) -> str:
        config = self._ctx.get("config")
        if config is None:
            return json.dumps({"error": "No configuration loaded."})

        # Expose non-sensitive fields only
        safe: dict[str, Any] = {
            "data_dir": str(config.data_dir),
            "model_name": config.model_name,
            "llm_port": config.llm_port,
            "log_level": config.log_level,
            "default_provider": config.default_provider,
            "openai_model": config.openai_model,
            "anthropic_model": config.anthropic_model,
        }

        # Indicate whether API keys are configured without exposing them
        safe["openai_api_key_set"] = bool(config.openai_api_key)
        safe["anthropic_api_key_set"] = bool(config.anthropic_api_key)
        safe["telegram_configured"] = bool(config.telegram_token)
        safe["discord_configured"] = bool(config.discord_token)

        return json.dumps(safe)
