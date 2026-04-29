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
from nexus.modules.general import GeneralModule

from nexus.api.routes.messages import router as messages_router
from nexus.api.routes.modules import router as modules_router
from nexus.api.routes.memory import router as memory_router
from nexus.api.routes.chronicle import router as chronicle_router
from nexus.api.routes.trust import router as trust_router
from nexus.api.routes.events import router as events_router
from nexus.api.routes.system import router as system_router
from nexus.api.routes.dashboard import router as dashboard_router
from nexus.api.routes.replay import router as replay_router
from nexus.api.routes.marketplace import router as marketplace_router
from nexus.api.routes.federation import router as federation_router
from nexus.api.routes.multimodal import router as multimodal_router


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
    ) -> None:
        self.config = config
        self.cortex = cortex
        self.engram = engram
        self.chronicle = chronicle
        self.aegis = aegis
        self.pulse = pulse


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

    # Register the general module by default
    general = GeneralModule()
    cortex.register_module(general)
    aegis.set_policy("general", allowed=True)

    # Attempt to wire up LLM — graceful degradation if unavailable
    try:
        from nexus.inference.llm import LLMClient
        from nexus.inference.router import ProviderRouter
        from nexus.inference.local import LocalProvider

        provider_router = ProviderRouter(default=config.default_provider)
        local = LocalProvider(base_url=f"http://localhost:{config.llm_port}")
        provider_router.register(local)

        if config.openai_api_key:
            from nexus.inference.openai_provider import OpenAIProvider
            provider_router.register(
                OpenAIProvider(api_key=config.openai_api_key, model=config.openai_model)
            )

        if config.anthropic_api_key:
            from nexus.inference.anthropic_provider import AnthropicProvider
            provider_router.register(
                AnthropicProvider(api_key=config.anthropic_api_key, model=config.anthropic_model)
            )

        llm_client = LLMClient(router=provider_router)

        async def _llm_handler(msg: str) -> str:
            return await llm_client.chat(
                system="You are Nexus, an autonomous intelligence operating system. Be helpful, precise, and concise.",
                user=msg,
            )

        cortex.set_llm(_llm_handler)
    except Exception:
        # LLM layer unavailable — kernel still works for routing/memory/trust
        pass

    return KernelState(
        config=config,
        cortex=cortex,
        engram=engram,
        chronicle=chronicle,
        aegis=aegis,
        pulse=pulse,
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
        title="NEXUS API",
        version=__version__,
        description="REST + WebSocket API for the NEXUS autonomous intelligence operating system",
        lifespan=lifespan,
    )

    # Store kernel state on the app for access in route handlers
    app.state.kernel = kernel

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
    app.include_router(replay_router)
    app.include_router(marketplace_router)
    app.include_router(federation_router)
    app.include_router(multimodal_router)

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
