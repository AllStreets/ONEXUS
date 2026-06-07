from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from nexus import __version__
from nexus.config import NexusConfig
from nexus.kernel.engram import Engram
from nexus.kernel.chronicle import Chronicle
from nexus.kernel.aegis import Aegis
from nexus.kernel.pulse import Pulse
from nexus.kernel.cortex import Cortex
from nexus.modules.council import CouncilModule
from nexus.modules.specter import SpecterModule
from nexus.modules.autonomic import AutonomicModule
from nexus.modules.oracle import OracleModule
from nexus.modules.wraith import WraithModule
from nexus.modules.legacy import LegacyModule
from nexus.modules.consciousness import ConsciousnessModule
from nexus.modules.sentry import SentryModule
from nexus.modules.echo import EchoModule

from nexus.api.routes.messages import router as messages_router
from nexus.api.routes.modules import router as modules_router
from nexus.api.routes.memory import router as memory_router
from nexus.api.routes.chronicle import router as chronicle_router
from nexus.api.routes.trust import router as trust_router
from nexus.api.routes.events import router as events_router
from nexus.api.routes.system import router as system_router
from nexus.api.routes.dashboard import router as dashboard_router
from nexus.api.routes.providers import router as providers_router
from nexus.api.routes.replay import router as replay_router
from nexus.api.routes.federation import router as federation_router
from nexus.api.routes.multimodal import router as multimodal_router
from nexus.api.routes.agents import router as agents_router


class KernelState:
    """Holds all kernel components for injection into route handlers."""

    def __init__(
        self,
        config: NexusConfig,
        cortex: Cortex,
        engram: Engram,
        chronicle: Chronicle,
        aegis: Aegis,
        pulse: Pulse,
        provider_router=None,
        llm_client=None,
    ) -> None:
        self.config = config
        self.cortex = cortex
        self.engram = engram
        self.chronicle = chronicle
        self.aegis = aegis
        self.pulse = pulse
        self.provider_router = provider_router
        self.llm_client = llm_client


def _init_kernel(config: NexusConfig) -> KernelState:
    """Initialize all kernel components from a config."""
    engram = Engram(config.db_path)
    engram.init_db()

    chronicle = Chronicle(str(config.db_path))
    chronicle.init_db()

    aegis = Aegis(str(config.db_path))
    aegis.init_db()

    pulse = Pulse()

    cortex = Cortex(
        engram=engram,
        chronicle=chronicle,
        aegis=aegis,
        pulse=pulse,
        config=config,
    )

    # Register kernel component policies in Aegis (trust tracking)
    # Kernel components start at EXECUTOR tier (0.80) -- core infrastructure
    for kernel_name in ["cortex", "engram", "chronicle", "aegis", "pulse"]:
        aegis.set_policy(kernel_name, allowed=True, network=False, initial_trust=0.80)

    # Register all cognitive modules
    # Modules start at ADVISOR tier (0.30) -- above the 0.25 routing floor
    # so they can be routed to immediately and earn their way up
    for ModuleClass in [CouncilModule, SpecterModule, AutonomicModule,
                        OracleModule, WraithModule, LegacyModule,
                        ConsciousnessModule, SentryModule, EchoModule]:
        module = ModuleClass()
        cortex.register_module(module)
        aegis.set_policy(module.name, allowed=True, initial_trust=0.30)

    # Initialize provider router — always available, providers registered on demand
    from nexus.inference.router import ProviderRouter
    from nexus.inference.llm import LLMClient
    from nexus.inference.local import LocalProvider

    provider_router = ProviderRouter(default=config.default_provider)

    # Register local provider (always available as fallback)
    local = LocalProvider(base_url=f"http://localhost:{config.llm_port}")
    provider_router.register(local)

    # Register cloud providers if configured via env
    if config.openai_api_key:
        try:
            from nexus.inference.openai_provider import OpenAIProvider
            provider_router.register(
                OpenAIProvider(api_key=config.openai_api_key, model=config.openai_model)
            )
        except Exception:
            pass

    if config.anthropic_api_key:
        try:
            from nexus.inference.anthropic_provider import AnthropicProvider
            provider_router.register(
                AnthropicProvider(api_key=config.anthropic_api_key, model=config.anthropic_model)
            )
        except Exception:
            pass

    llm_client = LLMClient(router=provider_router)

    async def _llm_handler(msg: str) -> str:
        return await llm_client.chat(
            system="You are Nexus, an autonomous intelligence operating system. Be helpful, precise, and concise.",
            user=msg,
        )

    cortex.set_llm(_llm_handler)

    return KernelState(
        config=config,
        cortex=cortex,
        engram=engram,
        chronicle=chronicle,
        aegis=aegis,
        pulse=pulse,
        provider_router=provider_router,
        llm_client=llm_client,
    )


def create_app(config: NexusConfig | None = None) -> FastAPI:
    """Create and return the FastAPI application."""
    if config is None:
        config = NexusConfig()

    kernel = _init_kernel(config)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup: initialize modules
        await kernel.cortex.initialize_modules()
        kernel.chronicle.log("api", "server_start", {"version": __version__})
        yield
        # Shutdown: drain event bus, log shutdown
        await kernel.pulse.drain()
        kernel.chronicle.log("api", "server_stop", {})

    app = FastAPI(
        title="ONEXUS API",
        version=__version__,
        description="REST + WebSocket API for the ONEXUS cognitive operating system",
        lifespan=lifespan,
    )

    # Store kernel state on the app for access in route handlers
    app.state.kernel = kernel

    # Initialize agent catalog + launcher. The dispatcher module is always
    # registered so 'list agents' / 'summon X' route correctly even when the
    # catalog directory is unreadable; the dispatcher reports the reason
    # instead of falling through to the council fallback.
    from nexus.agents.launcher import AgentLauncher
    from nexus.modules.agent_dispatcher import AgentDispatcherModule

    catalog = None
    launcher = None
    unavailable_reason: str | None = None

    _catalog_path = config.agents_catalog_path
    if not _catalog_path:
        import pathlib
        _sibling = pathlib.Path(__file__).resolve().parents[2].parent / "ONEXUS-Agents"
        if _sibling.is_dir():
            _catalog_path = str(_sibling)

    if _catalog_path:
        try:
            from nexus.agents.catalog import AgentCatalog
            catalog = AgentCatalog(_catalog_path)
            for agent in catalog.list_agents(runnable_only=True):
                kernel.aegis.set_policy(
                    f"agent.{agent.slug}", allowed=True,
                    initial_trust=0.30,
                )
            launcher = AgentLauncher(catalog=catalog, kernel=kernel)
        except Exception as exc:
            import logging as _log
            _log.getLogger("nexus.api").warning("Agent catalog unavailable: %s", exc)
            unavailable_reason = f"{type(exc).__name__}: {exc}"
            catalog = None
            launcher = None
    else:
        unavailable_reason = "ONEXUS-Agents directory not found alongside NEXUS."

    app.state.agent_catalog = catalog
    app.state.agent_launcher = launcher

    dispatcher = AgentDispatcherModule(
        catalog=catalog,
        launcher=launcher,
        unavailable_reason=unavailable_reason,
    )
    kernel.cortex.register_module(dispatcher)
    kernel.aegis.set_policy(dispatcher.name, allowed=True, initial_trust=0.30)

    # CORS middleware for dashboard access
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount all route groups
    app.include_router(messages_router)
    app.include_router(modules_router)
    app.include_router(memory_router)
    app.include_router(chronicle_router)
    app.include_router(trust_router)
    app.include_router(events_router)
    app.include_router(system_router)
    app.include_router(dashboard_router)
    app.include_router(providers_router)
    app.include_router(replay_router)
    app.include_router(federation_router)
    app.include_router(multimodal_router)
    app.include_router(agents_router)

    from nexus.api.routes.permissions import router as permissions_router
    from nexus.api.routes.installer import router as installer_router
    app.include_router(permissions_router)
    app.include_router(installer_router)

    from nexus.api.routes.aurora import router as aurora_router
    app.include_router(aurora_router)

    from nexus.api.routes.mood import router as mood_router
    app.include_router(mood_router)

    # Initialize federation if enabled via environment
    import os
    if os.environ.get("NEXUS_FEDERATION_ENABLED", "").lower() in ("1", "true", "yes"):
        try:
            from nexus.federation.security import FederationSecurity
            from nexus.federation.peer import PeerRegistry
            from nexus.federation.protocol import FederationProtocol
            from nexus.federation.discovery import PeerDiscovery

            instance_id = os.environ.get(
                "NEXUS_INSTANCE_ID",
                FederationSecurity.generate_instance_id(),
            )
            instance_name = os.environ.get("NEXUS_INSTANCE_NAME", "nexus-local")
            shared_secret = os.environ.get("NEXUS_FEDERATION_SECRET", "")

            fed_security = FederationSecurity(
                instance_id=instance_id,
                chronicle=kernel.chronicle,
                shared_secret=shared_secret,
            )
            fed_registry = PeerRegistry(data_path=kernel.config.data_dir / "federation")
            fed_registry.load()

            fed_protocol = FederationProtocol(
                instance_id=instance_id,
                instance_name=instance_name,
                version=__version__,
                registry=fed_registry,
                security=fed_security,
                cortex=kernel.cortex,
                chronicle=kernel.chronicle,
                enabled=True,
            )

            fed_discovery = PeerDiscovery(
                registry=fed_registry,
                security=fed_security,
                chronicle=kernel.chronicle,
                instance_id=instance_id,
            )

            kernel.federation_protocol = fed_protocol
            kernel.federation_discovery = fed_discovery

            kernel.chronicle.log("federation", "initialized", {
                "instance_id": instance_id,
                "instance_name": instance_name,
            })
        except Exception:
            pass

    return app


app = create_app()
