"""
ONEXUS TUI -- Rich terminal UI with split-pane layout.

An enhanced alternative to the plain CLI ``onexus run`` command.
Uses Rich Live display with a four-quadrant layout:
  top-left:     module list + trust bars
  top-right:    conversation panel
  bottom-left:  pulse event feed
  bottom-right: chronicle audit log

Header: status bar with system health.
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any

from rich.console import Console
from rich.layout import Layout
from rich.live import Live

from nexus import __version__
from nexus.config import NexusConfig
from nexus.kernel.engram import Engram
from nexus.kernel.chronicle import Chronicle
from nexus.kernel.aegis import Aegis
from nexus.kernel.pulse import Pulse, Message
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
from nexus.inference.llm import LLMClient
from nexus.inference.router import ProviderRouter
from nexus.inference.local import LocalProvider

from nexus.tui.theme import NEXUS_THEME
from nexus.tui.panels import (
    StatusBar,
    ModulePanel,
    ConversationPanel,
    PulsePanel,
    ChroniclePanel,
)
from nexus.tui.input_handler import InputHandler


class NexusTUI:
    """Rich terminal UI for ONEXUS with split-pane layout."""

    def __init__(self, config: NexusConfig) -> None:
        self._config = config
        self._console = Console(theme=NEXUS_THEME)
        self._start_time = time.monotonic()

        # Kernel components
        self._engram = Engram(str(config.db_path))
        self._engram.init_db()
        self._chronicle = Chronicle(str(config.db_path))
        self._chronicle.init_db()
        self._aegis = Aegis(str(config.db_path))
        self._aegis.init_db()
        self._pulse = Pulse()

        self._cortex = Cortex(
            engram=self._engram,
            chronicle=self._chronicle,
            aegis=self._aegis,
            pulse=self._pulse,
            config=config,
        )

        # Register all cognitive modules
        for ModuleClass in [CouncilModule, SpecterModule, AutonomicModule,
                            OracleModule, WraithModule, LegacyModule,
                            ConsciousnessModule, SentryModule, EchoModule]:
            module = ModuleClass()
            self._cortex.register_module(module)
            self._aegis.set_policy(module.name, allowed=True)

        # LLM setup
        self._llm_status = "offline"
        self._provider_name = config.default_provider
        self._router: ProviderRouter | None = None
        self._llm_client: LLMClient | None = None

        # Panel renderers
        self._status_bar = StatusBar()
        self._module_panel = ModulePanel()
        self._conversation_panel = ConversationPanel()
        self._pulse_panel = PulsePanel()
        self._chronicle_panel = ChroniclePanel()

        # State
        self._input_handler = InputHandler()
        self._messages: list[dict[str, str]] = []
        self._pulse_events: list[dict[str, Any]] = []
        self._running = False
        self._processing = False

    async def _setup_llm(self) -> None:
        """Initialize the LLM provider router and check connectivity."""
        self._router = ProviderRouter(default=self._config.default_provider)

        local = LocalProvider(base_url=f"http://localhost:{self._config.llm_port}")
        self._router.register(local)

        if self._config.openai_api_key:
            from nexus.inference.openai_provider import OpenAIProvider
            self._router.register(
                OpenAIProvider(
                    api_key=self._config.openai_api_key,
                    model=self._config.openai_model,
                )
            )

        if self._config.anthropic_api_key:
            from nexus.inference.anthropic_provider import AnthropicProvider
            self._router.register(
                AnthropicProvider(
                    api_key=self._config.anthropic_api_key,
                    model=self._config.anthropic_model,
                )
            )

        self._llm_client = LLMClient(router=self._router)

        # Check local LLM health
        if await local.health():
            self._llm_status = "online"
        elif self._config.default_provider != "local":
            self._llm_status = "online"
            self._provider_name = self._config.default_provider
        else:
            self._llm_status = "offline"

        async def _llm_handler(msg: str) -> str:
            assert self._llm_client is not None
            return await self._llm_client.chat(
                system="You are Nexus, an autonomous intelligence operating system. Be helpful, precise, and concise.",
                user=msg,
            )

        self._cortex.set_llm(_llm_handler)

    def _setup_pulse_listener(self) -> None:
        """Subscribe to all Pulse events for the event feed panel."""
        async def _on_event(msg: Message) -> None:
            ts = datetime.now(timezone.utc).isoformat()
            self._pulse_events.append({
                "timestamp": ts,
                "topic": msg.topic,
                "source": msg.source,
                "payload": msg.payload,
            })
            # Keep bounded
            if len(self._pulse_events) > 50:
                self._pulse_events = self._pulse_events[-50:]

        self._pulse.subscribe("*", _on_event)

    def _build_layout(self) -> Layout:
        """Construct the Rich Layout tree."""
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=12),
        )
        layout["body"].split_row(
            Layout(name="left", ratio=1, minimum_size=22),
            Layout(name="right", ratio=3),
        )
        layout["footer"].split_row(
            Layout(name="bottom_left", ratio=1, minimum_size=22),
            Layout(name="bottom_right", ratio=3),
        )
        return layout

    def _get_health(self) -> dict[str, Any]:
        """Gather current system health data for the status bar."""
        elapsed = time.monotonic() - self._start_time
        hours, remainder = divmod(int(elapsed), 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{hours}:{minutes:02d}:{seconds:02d}"

        modules = self._cortex.list_modules()

        # Count total known module keywords as a proxy for "available" modules
        total_keywords = len(Cortex._MODULE_KEYWORDS)

        return {
            "version": __version__,
            "llm_status": self._llm_status,
            "module_count": total_keywords,
            "provider": self._provider_name,
            "uptime": uptime_str,
        }

    def _get_trust_scores(self) -> dict[str, int]:
        """Fetch trust scores for all modules with policies."""
        policies = self._aegis.list_policies()
        return {p["module"]: p["trust"] for p in policies}

    def _get_chronicle_entries(self) -> list[dict[str, Any]]:
        """Fetch the most recent Chronicle entries."""
        try:
            return self._chronicle.query(limit=10)
        except Exception:
            return []

    def _render(self, layout: Layout) -> Layout:
        """Update all panels in the layout with current state."""
        health = self._get_health()
        modules = self._cortex.list_modules()
        trust_scores = self._get_trust_scores()
        chronicle_entries = self._get_chronicle_entries()

        layout["header"].update(self._status_bar.render(health))
        layout["left"].update(
            self._module_panel.render(modules, trust_scores)
        )
        layout["right"].update(
            self._conversation_panel.render(
                self._messages, self._input_handler.current_input
            )
        )
        layout["bottom_left"].update(
            self._pulse_panel.render(self._pulse_events)
        )
        layout["bottom_right"].update(
            self._chronicle_panel.render(chronicle_entries)
        )
        return layout

    async def _process_message(self, user_input: str) -> None:
        """Send a message through Cortex and record the conversation."""
        self._messages.append({"role": "user", "text": user_input})
        self._processing = True

        try:
            response = await self._cortex.process(user_input)

            # Try to determine which module handled it
            module = ""
            if response.startswith("[") and "]" in response:
                bracket_end = response.index("]")
                module = response[1:bracket_end]
            elif hasattr(self._cortex, "_select_module"):
                module = self._cortex._select_module(user_input)

            self._messages.append({
                "role": "response",
                "text": response,
                "module": module,
            })
        except Exception as exc:
            self._messages.append({
                "role": "error",
                "text": f"Error: {exc}",
            })
        finally:
            self._processing = False

    async def run(self) -> None:
        """Main TUI event loop -- render layout, handle input, update panels."""
        await self._setup_llm()
        self._setup_pulse_listener()

        layout = self._build_layout()

        # Welcome message
        self._messages.append({
            "role": "system",
            "text": f"NEXUS v{__version__} -- Terminal UI active. Type a command or message.",
        })
        if self._llm_status == "offline":
            self._messages.append({
                "role": "system",
                "text": f"LLM offline. Start llama.cpp on port {self._config.llm_port} for local inference.",
            })

        self._running = True

        with Live(
            self._render(layout),
            console=self._console,
            screen=True,
            refresh_per_second=4,
        ) as live:
            while self._running:
                # Read input in a thread to avoid blocking the event loop
                try:
                    key = await asyncio.get_event_loop().run_in_executor(
                        None, self._input_handler.read_key
                    )
                except (EOFError, OSError):
                    break

                result = self._input_handler.handle_key(key)

                if result.exit_requested:
                    self._running = False
                    break

                if result.submitted is not None and result.submitted.strip():
                    user_text = result.submitted.strip()

                    # Handle TUI-specific commands
                    if user_text.lower() in ("exit", "quit"):
                        self._running = False
                        break

                    await self._process_message(user_text)

                # Re-render
                live.update(self._render(layout))

        self._console.print("\n[nexus.text.dim]Session ended.[/]")


def launch_tui(config: NexusConfig | None = None) -> None:
    """Entry point to launch the NEXUS TUI."""
    if config is None:
        config = NexusConfig()

    tui = NexusTUI(config)
    asyncio.run(tui.run())
