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
from nexus.modules.sigil import SigilModule
from nexus.modules.atlas import AtlasModule
from nexus.modules.chronos import ChronosModule
from nexus.modules.prism import PrismModule

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

    # Wire Chronicle into Aegis so every trust change / grant / revoke gets
    # logged to the immutable audit log. Without this Aegis silently no-ops
    # its _log_chronicle calls and the cockpit's trust card never sees
    # aegis.trust_change events to refresh from.
    aegis = Aegis(str(config.db_path), chronicle=chronicle)
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
                        ConsciousnessModule, SentryModule, EchoModule,
                        SigilModule, AtlasModule, ChronosModule,
                        PrismModule]:
        module = ModuleClass()
        cortex.register_module(module)
        aegis.set_policy(module.name, allowed=True, initial_trust=0.30)

    # N1 wiring: live gate events and built-in manifests for check_capability.
    # (The emergency routing bypass needs a running event loop to subscribe,
    # so it is attached in the app lifespan startup below.)
    aegis.set_pulse(pulse)
    cortex.register_builtin_manifests()

    # Initialize provider router — always available, providers registered on demand
    from nexus.inference.router import ProviderRouter
    from nexus.inference.llm import LLMClient
    from nexus.inference.local import LocalProvider
    from nexus.inference.ollama import OllamaProvider

    provider_router = ProviderRouter(default=config.default_provider)

    # Register Ollama FIRST so it's preferred over the llama.cpp local
    # provider when both are running — Ollama is what most users on a Mac
    # actually install and ONEXUS-Agents-Catalog ranks it as the easiest
    # on-device runtime. Falls back silently if Ollama isn't running.
    # Honour the user's last local-model choice (persisted by the model
    # switcher in Settings → Providers); fall back to the default model.
    from nexus.api.routes.providers import read_active_local_model
    _saved_model = read_active_local_model(config.data_dir)
    ollama = OllamaProvider(model=_saved_model) if _saved_model else OllamaProvider()
    provider_router.register(ollama)

    # Register the llama.cpp-compatible local provider as a secondary
    # fallback (port 8384 by default — see config.llm_port).
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
        # N1 wiring: emergency routing bypass (Sigil -> Specter). Subscribing
        # to Pulse requires a running event loop, hence here and not in
        # _init_kernel. Idempotent.
        kernel.cortex.attach_emergency_bypass()
        # Startup: initialize modules
        await kernel.cortex.initialize_modules()
        kernel.chronicle.log("api", "server_start", {"version": __version__})

        # Wire kernel Pulse events into the mood engine so /api/mood/current
        # reflects live kernel state (Phase 5 T10).
        from nexus.workspaces.mood import MoodSignals as _MoodSignals

        signals = getattr(app.state, "mood_signals", None) or _MoodSignals()
        app.state.mood_signals = signals

        async def _on_cortex_route(msg):
            _signals = app.state.mood_signals
            target = (msg.payload or {}).get("target")
            if target:
                import dataclasses
                updated = dataclasses.replace(_signals, active_agent=target)
                app.state.mood_signals = updated

        async def _on_trust_change(msg):
            _signals = app.state.mood_signals
            score = (msg.payload or {}).get("new_score")
            if score is not None and score < 0.5:
                import dataclasses
                updated = dataclasses.replace(_signals, trust_collapsed=True)
                app.state.mood_signals = updated

        kernel.pulse.subscribe("cortex.route", _on_cortex_route)
        kernel.pulse.subscribe("aegis.trust_change", _on_trust_change)

        # Keep the agent catalog fresh: re-read it from disk every 5 minutes so
        # newly-added agents become searchable/launchable without a restart
        # (atomic swap — see AgentCatalog.reload). No-op when the catalog dir
        # hasn't changed; cheap relative to the 5-min interval.
        import asyncio as _asyncio

        async def _catalog_refresher():
            while True:
                await _asyncio.sleep(300)
                cat = getattr(app.state, "agent_catalog", None)
                if cat is None:
                    continue
                try:
                    await _asyncio.to_thread(cat.reload)
                except Exception as exc:  # noqa: BLE001
                    import logging as _log

                    _log.getLogger("nexus.api").warning("catalog reload failed: %s", exc)

        _refresh_task = _asyncio.create_task(_catalog_refresher())

        # N2.2: Dreamweaver overnight distillation. In-process asyncio interval
        # loop (mirrors _catalog_refresher), guarded by dreamweaver_enabled
        # (env NEXUS_DREAMWEAVER=0/false/no or <data_dir>/dreamweaver.kill).
        # Interval defaults to 24h; NEXUS_DREAMWEAVER_INTERVAL_S overrides for
        # tests. Each run publishes a dreamweaver.brief Pulse message so Aurora
        # refreshes the morning-brief card without polling.
        from nexus.synthesis.dreamweaver import Dreamweaver, dreamweaver_enabled
        from nexus.kernel.pulse import Message as _Message

        app.state.dreamweaver = Dreamweaver(
            kernel.config, kernel.engram, kernel.chronicle
        )
        _dw_interval = float(os.environ.get("NEXUS_DREAMWEAVER_INTERVAL_S", "86400"))

        async def _dreamweaver_loop():
            while True:
                await _asyncio.sleep(_dw_interval)
                if not dreamweaver_enabled(kernel.config):
                    continue
                try:
                    brief = await _asyncio.to_thread(app.state.dreamweaver.run_once)
                except Exception as exc:  # noqa: BLE001
                    import logging as _log

                    _log.getLogger("nexus.api").warning("dreamweaver run failed: %s", exc)
                    continue
                if brief.get("skipped") is None:
                    await kernel.pulse.publish(_Message(
                        topic="dreamweaver.brief", source="dreamweaver", payload=brief,
                    ))

        _dreamweaver_task = _asyncio.create_task(_dreamweaver_loop())

        yield
        # Shutdown: drain event bus, log shutdown
        _refresh_task.cancel()
        _dreamweaver_task.cancel()
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

    # Optional per-instance bearer-token gate (HTTP + WebSocket). No-op unless
    # NEXUS_API_TOKEN is set, so the loopback default and the test suite are
    # unchanged; set the env var to lock down a non-loopback deployment.
    from nexus.api.auth import ApiTokenMiddleware

    app.add_middleware(ApiTokenMiddleware)

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

    from nexus.api.routes.provider_keys import router as provider_keys_router, load_keys_into_router
    app.include_router(provider_keys_router)
    # Hydrate any keys saved in a previous run so cloud providers survive restart.
    try:
        load_keys_into_router(kernel)
    except Exception as exc:
        print(f"[onexus] provider-keys hydrate failed: {exc}")
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

    from nexus.api.routes.cockpit import router as cockpit_router
    app.include_router(cockpit_router)

    from nexus.api.routes.workspaces import router as workspaces_router
    app.include_router(workspaces_router)

    from nexus.api.routes.spatial import router as spatial_router
    app.include_router(spatial_router)

    from nexus.api.routes.files import router as files_router
    app.include_router(files_router)

    from nexus.api.routes.codebases import router as codebases_router
    app.include_router(codebases_router)

    from nexus.api.routes.search import router as search_router
    app.include_router(search_router)

    from nexus.api.routes.workshop import router as workshop_router
    app.include_router(workshop_router)

    from nexus.api.routes.chat_history import router as chat_history_router
    app.include_router(chat_history_router)

    from nexus.api.routes.cortex import router as cortex_router
    app.include_router(cortex_router)

    from nexus.api.routes.sigil import router as sigil_router
    app.include_router(sigil_router)

    from nexus.api.routes.chronos import router as chronos_router
    app.include_router(chronos_router)

    from nexus.api.routes.prism import router as prism_router
    app.include_router(prism_router)

    from nexus.api.routes.herald import router as herald_router
    app.include_router(herald_router)

    from nexus.api.routes.serendipity import router as serendipity_router
    app.include_router(serendipity_router)

    from nexus.api.routes.atlas import router as atlas_router
    app.include_router(atlas_router)

    from nexus.api.routes.dreamweaver import router as dreamweaver_router
    app.include_router(dreamweaver_router)

    # Initialize federation if enabled via environment
    import os
    if os.environ.get("NEXUS_FEDERATION_ENABLED", "").lower() in ("1", "true", "yes"):
        try:
            from nexus.federation.security import FederationSecurity
            from nexus.federation.peer import PeerRegistry
            from nexus.federation.protocol import FederationProtocol
            from nexus.federation.discovery import PeerDiscovery
            from nexus.inference.kernel_http_client import KernelHttpClient
            from nexus.agents.manifest import (
                Manifest, Publisher, IdentityMark, Identity, RuntimeConfig,
                Capabilities, DeclaredCapabilities, TrustConfig, Compatibility,
                Source,
            )

            instance_id = os.environ.get(
                "NEXUS_INSTANCE_ID",
                FederationSecurity.generate_instance_id(),
            )
            instance_name = os.environ.get("NEXUS_INSTANCE_NAME", "nexus-local")
            shared_secret = os.environ.get("NEXUS_FEDERATION_SECRET", "")

            # Register a built-in federation manifest so Aegis can gate
            # outbound peer HTTP via check_capability("federation", ...).
            # All peer domains are declared as Routine (auto-allowed).
            fed_manifest = Manifest(
                manifest_version=1,
                slug="federation",
                name="NEXUS Federation",
                tagline="Peer-to-peer federation layer",
                version=__version__,
                system=True,
                publisher=Publisher(type="org", handle="nexus-core"),
                category="system",
                tags=["federation", "system"],
                license="proprietary",
                identity=Identity(mark=IdentityMark(kind="builtin:federation")),
                capabilities=Capabilities(
                    declared=DeclaredCapabilities(**{
                        "Routine": ["network.outbound.localhost",
                                    "federation.sync.workspace"],
                    }),
                ),
                runtime=RuntimeConfig(transport="in_process"),
            )
            kernel.aegis.register_manifest(fed_manifest)
            kernel.aegis.set_policy(
                "federation", allowed=True, network=True, initial_trust=0.80
            )

            fed_http = KernelHttpClient(aegis=kernel.aegis)

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
                http_client=fed_http,
            )

            fed_discovery = PeerDiscovery(
                registry=fed_registry,
                security=fed_security,
                chronicle=kernel.chronicle,
                instance_id=instance_id,
                http_client=fed_http,
            )

            kernel.federation_protocol = fed_protocol
            kernel.federation_discovery = fed_discovery

            # N3.2 — workspace-scoped, allowlist-only, Aegis-gated Atlas sync.
            # The sync engine never touches the network (the kernel-import
            # invariant is enforced on nexus/federation/sync.py); real peer
            # HTTP flows through FederationProtocol._http only.
            from nexus.federation.sync import PeerAllowlist, WorkspaceSyncEngine
            from nexus.workspaces.manager import WorkspaceManager

            fed_allowlist = PeerAllowlist(kernel.config.data_dir / "federation")

            def _engram_for(ws_id: str):
                ws_root = kernel.config.data_dir / "workspaces"
                ws_root.mkdir(parents=True, exist_ok=True)
                mgr = WorkspaceManager(root=ws_root)
                try:
                    ws_dir = mgr.workspace_dir(ws_id)
                except Exception:
                    ws_dir = ws_root / ws_id
                ws_dir.mkdir(parents=True, exist_ok=True)
                eng = Engram(ws_dir / "engram" / "episodic.sqlite")
                (ws_dir / "engram").mkdir(parents=True, exist_ok=True)
                eng.init_db()
                return eng

            fed_sync_engine = WorkspaceSyncEngine(
                instance_id=instance_id,
                aegis=kernel.aegis,
                chronicle=kernel.chronicle,
                allowlist=fed_allowlist,
                engram_for=_engram_for,
            )

            # Kill switch: NEXUS_FEDERATION_SYNC=0/false/no OR
            # <data_dir>/federation-sync.kill disables sync. Default on.
            import pathlib as _pathlib
            _sync_env_on = os.environ.get(
                "NEXUS_FEDERATION_SYNC", "1").lower() not in ("0", "false", "no")
            _sync_kill = (_pathlib.Path(kernel.config.data_dir)
                          / "federation-sync.kill").exists()
            fed_sync_engine.set_sync_enabled(_sync_env_on and not _sync_kill)

            kernel.federation_allowlist = fed_allowlist
            kernel.federation_sync_engine = fed_sync_engine

            kernel.chronicle.log("federation", "initialized", {
                "instance_id": instance_id,
                "instance_name": instance_name,
                "sync_enabled": fed_sync_engine.sync_enabled,
            })
        except Exception:
            pass

    return app


app = create_app()
