"""
General — the built-in default module.
Handles any user message by forwarding to the LLM with a system prompt.
Falls back to a static response when no LLM is available.
"""
from __future__ import annotations

from typing import Any
from nexus.modules.base import NexusModule

SYSTEM_PROMPT = """You are Nexus, an autonomous intelligence operating system. You are helpful, precise, and concise. You answer questions directly without unnecessary preamble."""


class GeneralModule(NexusModule):
    name = "general"
    description = "General-purpose conversation and question answering"
    version = "0.1.0"

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        llm = context.get("llm")
        if llm is None:
            return f"[Nexus] Received: {message} (no LLM connected — running in offline mode)"
        response = await llm(message)
        return response
