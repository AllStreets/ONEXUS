"""
MCP prompt definitions for NEXUS.

Pre-built prompts that route user intent to the right combination
of NEXUS agents, giving MCP clients useful starting workflows.
"""
from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Prompt catalogue
# ---------------------------------------------------------------------------

PROMPT_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "analyze_code",
        "description": (
            "Perform a multi-module code analysis. Routes to Specter (adversarial/security), "
            "Council (multi-perspective review), and Oracle (pattern detection) in sequence."
        ),
        "arguments": [
            {
                "name": "code",
                "description": "The source code to analyse.",
                "required": True,
            },
            {
                "name": "language",
                "description": "Programming language (e.g. 'python', 'javascript').",
                "required": False,
            },
            {
                "name": "focus",
                "description": "Focus area: 'security', 'quality', 'refactor', or 'all' (default).",
                "required": False,
            },
        ],
    },
    {
        "name": "security_scan",
        "description": (
            "Run a security-focused scan. Routes to Specter (adversarial analysis) "
            "for vulnerability detection and stress testing."
        ),
        "arguments": [
            {
                "name": "target",
                "description": "The code, API spec, or endpoint description to scan.",
                "required": True,
            },
            {
                "name": "scan_type",
                "description": "Type of scan: 'code', 'api', or 'both' (default).",
                "required": False,
            },
        ],
    },
    {
        "name": "summarize",
        "description": (
            "Summarise or expand content using ONEXUS cognitive modules. "
            "Routes to Legacy (knowledge crystallization) for distillation "
            "and Council (multi-perspective synthesis) for expansion."
        ),
        "arguments": [
            {
                "name": "content",
                "description": "The content to summarise or expand.",
                "required": True,
            },
            {
                "name": "mode",
                "description": "Operation mode: 'summarize', 'expand', or 'polish' (default 'summarize').",
                "required": False,
            },
        ],
    },
]


def get_prompt_definitions() -> list[dict[str, Any]]:
    """Return raw prompt definitions (always available)."""
    return PROMPT_DEFINITIONS


# ---------------------------------------------------------------------------
# Prompt handlers
# ---------------------------------------------------------------------------

class PromptHandlers:
    """Builds MCP prompt messages from user arguments.

    Requires a kernel_context dict containing live instances of:
        cortex, engram, chronicle, aegis, pulse, config
    """

    def __init__(self, kernel_context: dict[str, Any]) -> None:
        self._ctx = kernel_context
        self._dispatch: dict[str, Any] = {
            "analyze_code": self._build_analyze_code,
            "security_scan": self._build_security_scan,
            "summarize": self._build_summarize,
        }

    async def get_prompt(
        self, name: str, arguments: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        """Build the message list for a named prompt.

        Returns a list of {role, content} dicts suitable for MCP
        GetPromptResult.messages.
        """
        builder = self._dispatch.get(name)
        if builder is None:
            return [{"role": "user", "content": {"type": "text", "text": f"Unknown prompt: {name}"}}]
        args = arguments or {}
        try:
            return await builder(args)
        except Exception as exc:
            return [{"role": "user", "content": {"type": "text", "text": f"Error building prompt '{name}': {exc}"}}]

    # ------------------------------------------------------------------
    # Builders
    # ------------------------------------------------------------------

    async def _build_analyze_code(self, args: dict[str, str]) -> list[dict[str, Any]]:
        code = args.get("code", "")
        if not code:
            return [{"role": "user", "content": {"type": "text", "text": "Error: 'code' argument is required."}}]

        language = args.get("language", "unknown")
        focus = args.get("focus", "all")

        modules_to_use: list[tuple[str, str]] = []
        if focus in ("security", "all"):
            modules_to_use.append((
                "specter",
                f"Scan this {language} code for security vulnerabilities:\n\n```{language}\n{code}\n```",
            ))
        if focus in ("quality", "all"):
            modules_to_use.append((
                "council",
                f"Review this {language} code for quality and best practices:\n\n```{language}\n{code}\n```",
            ))
        if focus in ("refactor", "all"):
            modules_to_use.append((
                "oracle",
                f"Analyse this {language} code for patterns and refactoring opportunities:\n\n```{language}\n{code}\n```",
            ))

        messages: list[dict[str, Any]] = []
        for module_name, prompt_text in modules_to_use:
            messages.append({
                "role": "user",
                "content": {
                    "type": "text",
                    "text": f"[Route to {module_name}] {prompt_text}",
                },
            })
        return messages

    async def _build_security_scan(self, args: dict[str, str]) -> list[dict[str, Any]]:
        target = args.get("target", "")
        if not target:
            return [{"role": "user", "content": {"type": "text", "text": "Error: 'target' argument is required."}}]

        scan_type = args.get("scan_type", "both")
        messages: list[dict[str, Any]] = []

        if scan_type in ("code", "both"):
            messages.append({
                "role": "user",
                "content": {
                    "type": "text",
                    "text": f"[Route to specter] Scan for security vulnerabilities:\n\n{target}",
                },
            })

        if scan_type in ("api", "both"):
            messages.append({
                "role": "user",
                "content": {
                    "type": "text",
                    "text": f"[Route to specter] Analyse API security:\n\n{target}",
                },
            })

        return messages

    async def _build_summarize(self, args: dict[str, str]) -> list[dict[str, Any]]:
        content = args.get("content", "")
        if not content:
            return [{"role": "user", "content": {"type": "text", "text": "Error: 'content' argument is required."}}]

        mode = args.get("mode", "summarize")

        if mode == "expand":
            return [{
                "role": "user",
                "content": {
                    "type": "text",
                    "text": f"[Route to council] Expand this content into polished prose using multi-perspective synthesis:\n\n{content}",
                },
            }]

        if mode == "polish":
            return [{
                "role": "user",
                "content": {
                    "type": "text",
                    "text": f"[Route to council] Polish and improve this writing:\n\n{content}",
                },
            }]

        # Default: summarize
        return [{
            "role": "user",
            "content": {
                "type": "text",
                "text": f"[Route to legacy] Distill the following content into a concise summary:\n\n{content}",
            },
        }]
