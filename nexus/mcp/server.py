"""
NEXUS MCP Server -- Model Context Protocol interface.

Exposes NEXUS modules, agents, and kernel operations as MCP tools
so any compliant client (Claude Desktop, Cursor, VS Code, etc.)
can connect and use NEXUS as a tool provider.

Run standalone:
    python -m nexus.mcp.server

Or import and call ``run_server()`` from application code.
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import (
        TextContent,
        Tool,
        Resource,
        Prompt,
        PromptArgument,
        PromptMessage,
        GetPromptResult,
    )
    HAS_MCP = True
except ImportError:
    HAS_MCP = False

from nexus.config import NexusConfig
from nexus.kernel.aegis import Aegis
from nexus.kernel.chronicle import Chronicle
from nexus.kernel.cortex import Cortex
from nexus.kernel.engram import Engram
from nexus.kernel.pulse import Pulse
from nexus.mcp.tools import ToolHandlers, get_tool_definitions
from nexus.mcp.resources import ResourceHandlers, get_resource_definitions
from nexus.mcp.prompts import PromptHandlers, get_prompt_definitions

logger = logging.getLogger("nexus.mcp")


# ---------------------------------------------------------------------------
# Kernel bootstrap
# ---------------------------------------------------------------------------

def _build_kernel(config: NexusConfig | None = None) -> dict[str, Any]:
    """Initialise kernel components and return a context dict.

    All databases are created in ``config.data_dir``. If no config is
    provided a default one is used.
    """
    if config is None:
        config = NexusConfig()

    db_path = str(config.db_path)

    engram = Engram(db_path=Path(db_path))
    engram.init_db()

    chronicle = Chronicle(db_path=db_path)
    chronicle.init_db()

    aegis = Aegis(db_path=db_path)
    aegis.init_db()

    pulse = Pulse()

    cortex = Cortex(
        engram=engram,
        chronicle=chronicle,
        aegis=aegis,
        pulse=pulse,
        config=config,
    )

    # Register all available modules
    _register_modules(cortex, aegis)

    ctx: dict[str, Any] = {
        "cortex": cortex,
        "engram": engram,
        "chronicle": chronicle,
        "aegis": aegis,
        "pulse": pulse,
        "config": config,
    }

    chronicle.log("mcp", "kernel_init", {"data_dir": str(config.data_dir)})
    return ctx


def _register_modules(cortex: Cortex, aegis: Aegis) -> None:
    """Discover and register all built-in modules and agents.

    Each module/agent class is imported and instantiated. Failures are
    logged but do not prevent the server from starting.
    """
    # -- Modules --
    _module_classes: list[tuple[str, str]] = [
        ("nexus.modules.general", "GeneralModule"),
        ("nexus.modules.oracle", "OracleModule"),
        ("nexus.modules.sentry", "SentryModule"),
        ("nexus.modules.atlas", "AtlasModule"),
        ("nexus.modules.cipher", "CipherModule"),
        ("nexus.modules.prism", "PrismModule"),
        ("nexus.modules.wraith", "WraithModule"),
        ("nexus.modules.echo", "EchoModule"),
        ("nexus.modules.herald", "HeraldModule"),
        ("nexus.modules.weave", "WeaveModule"),
        ("nexus.modules.sigil", "SigilModule"),
        ("nexus.modules.specter", "SpecterModule"),
        ("nexus.modules.serendipity", "SerendipityModule"),
        ("nexus.modules.forge", "ForgeModule"),
        ("nexus.modules.collective", "CollectiveModule"),
        ("nexus.modules.legacy", "LegacyModule"),
        ("nexus.modules.council", "CouncilModule"),
        ("nexus.modules.autonomic", "AutonomicModule"),
        ("nexus.modules.dream_loop", "DreamLoopModule"),
        ("nexus.modules.adversarial", "AdversarialModule"),
        ("nexus.modules.tripwire", "TripwireModule"),
        ("nexus.modules.provenance", "ProvenanceModule"),
        ("nexus.modules.sandbox", "SandboxModule"),
        ("nexus.modules.symbiosis", "SymbiosisModule"),
        ("nexus.modules.consciousness", "ConsciousnessModule"),
        ("nexus.modules.ethical_prism", "EthicalPrismModule"),
    ]

    # -- Agents --
    _agent_classes: list[tuple[str, str]] = [
        ("nexus.agents.scribe", "ScribeAgent"),
        ("nexus.agents.vex", "VexAgent"),
        ("nexus.agents.ledger", "LedgerAgent"),
        ("nexus.agents.arbiter", "ArbiterAgent"),
        ("nexus.agents.thesis", "ThesisAgent"),
        ("nexus.agents.scaffold", "ScaffoldAgent"),
        ("nexus.agents.remedy", "RemedyAgent"),
        ("nexus.agents.compass", "CompassAgent"),
        ("nexus.agents.tally", "TallyAgent"),
        ("nexus.agents.redline", "RedlineAgent"),
        ("nexus.agents.carve", "CarveAgent"),
        ("nexus.agents.vigil", "VigilAgent"),
        ("nexus.agents.mandate", "MandateAgent"),
        ("nexus.agents.flux", "FluxAgent"),
        ("nexus.agents.kindle", "KindleAgent"),
        ("nexus.agents.quarry", "QuarryAgent"),
        ("nexus.agents.bastion", "BastionAgent"),
        ("nexus.agents.dispatch", "DispatchAgent"),
        ("nexus.agents.gauge", "GaugeAgent"),
        ("nexus.agents.mnemonic", "MnemonicAgent"),
        ("nexus.agents.sentinel", "SentinelAgent"),
        ("nexus.agents.mint", "MintAgent"),
        ("nexus.agents.axiom", "AxiomAgent"),
        ("nexus.agents.loom", "LoomAgent"),
        ("nexus.agents.rune", "RuneAgent"),
    ]

    for module_path, class_name in _module_classes + _agent_classes:
        try:
            import importlib
            mod = importlib.import_module(module_path)
            cls = getattr(mod, class_name)
            instance = cls()
            cortex.register_module(instance)
            # Ensure a policy row exists so Aegis can track it
            if not aegis.is_allowed(instance.name, "handle"):
                # Default: modules start allowed, trust 50
                aegis.set_policy(instance.name, allowed=True)
                aegis.adjust_trust(instance.name, 50, "initial registration")
        except Exception as exc:
            logger.warning("Failed to register %s.%s: %s", module_path, class_name, exc)


# ---------------------------------------------------------------------------
# MCP Server wiring
# ---------------------------------------------------------------------------

def create_server(config: NexusConfig | None = None) -> tuple[Any, dict[str, Any]]:
    """Create and configure an MCP Server instance.

    Returns (server, kernel_context) so callers can introspect the kernel
    if needed.
    """
    if not HAS_MCP:
        raise RuntimeError(
            "The 'mcp' package is not installed. "
            "Install it with: pip install mcp"
        )

    kernel_ctx = _build_kernel(config)
    tool_handlers = ToolHandlers(kernel_ctx)
    resource_handlers = ResourceHandlers(kernel_ctx)
    prompt_handlers = PromptHandlers(kernel_ctx)

    server = Server("nexus")

    # -- Tools --------------------------------------------------------

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        tools = []
        for defn in get_tool_definitions():
            tools.append(Tool(
                name=defn["name"],
                description=defn["description"],
                inputSchema=defn["inputSchema"],
            ))
        return tools

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        results = await tool_handlers.call(name, arguments)
        return [TextContent(type="text", text=r["text"]) for r in results]

    # -- Resources ----------------------------------------------------

    @server.list_resources()
    async def list_resources() -> list[Resource]:
        resources = []
        for defn in get_resource_definitions():
            resources.append(Resource(
                uri=defn["uri"],
                name=defn["name"],
                description=defn["description"],
                mimeType=defn["mimeType"],
            ))
        return resources

    @server.read_resource()
    async def read_resource(uri: str) -> str:
        return await resource_handlers.read(str(uri))

    # -- Prompts ------------------------------------------------------

    @server.list_prompts()
    async def list_prompts() -> list[Prompt]:
        prompts = []
        for defn in get_prompt_definitions():
            args = []
            for arg_defn in defn.get("arguments", []):
                args.append(PromptArgument(
                    name=arg_defn["name"],
                    description=arg_defn.get("description"),
                    required=arg_defn.get("required", False),
                ))
            prompts.append(Prompt(
                name=defn["name"],
                description=defn["description"],
                arguments=args,
            ))
        return prompts

    @server.get_prompt()
    async def get_prompt(
        name: str, arguments: dict[str, str] | None = None,
    ) -> GetPromptResult:
        raw_messages = await prompt_handlers.get_prompt(name, arguments)
        messages = []
        for msg in raw_messages:
            messages.append(PromptMessage(
                role=msg["role"],
                content=TextContent(
                    type=msg["content"]["type"],
                    text=msg["content"]["text"],
                ),
            ))
        return GetPromptResult(
            description=f"NEXUS prompt: {name}",
            messages=messages,
        )

    return server, kernel_ctx


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def run_server(config: NexusConfig | None = None) -> None:
    """Start the MCP server on stdio transport."""
    server, kernel_ctx = create_server(config)
    logger.info("NEXUS MCP server starting on stdio transport")

    cortex = kernel_ctx["cortex"]
    await cortex.initialize_modules()

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main() -> None:
    """CLI entry point."""
    logging.basicConfig(level=logging.INFO, format="%(name)s | %(message)s")
    asyncio.run(run_server())


if __name__ == "__main__":
    main()
