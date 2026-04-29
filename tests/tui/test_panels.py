"""Tests for nexus.tui.panels -- verify each panel renders without errors."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from rich.panel import Panel
from rich.text import Text
from rich.console import Console

from nexus.tui.panels import (
    StatusBar,
    ModulePanel,
    ConversationPanel,
    PulsePanel,
    ChroniclePanel,
)
from nexus.tui.theme import NEXUS_THEME


@pytest.fixture
def console():
    """Console that captures output to a string buffer."""
    return Console(theme=NEXUS_THEME, file=None, force_terminal=True, width=100)


def _render_to_string(console: Console, renderable) -> str:
    """Render a Rich object to a string via the console."""
    with console.capture() as capture:
        console.print(renderable)
    return capture.get()


class TestStatusBar:
    def test_renders_panel(self, console):
        bar = StatusBar()
        result = bar.render({
            "version": "0.1.0",
            "llm_status": "online",
            "module_count": 51,
            "provider": "local",
            "uptime": "0:05:32",
        })
        assert isinstance(result, Panel)

    def test_renders_with_defaults(self, console):
        bar = StatusBar()
        result = bar.render({})
        assert isinstance(result, Panel)
        output = _render_to_string(console, result)
        assert "NEXUS" in output

    def test_offline_status(self, console):
        bar = StatusBar()
        result = bar.render({"llm_status": "offline"})
        output = _render_to_string(console, result)
        assert "offline" in output

    def test_online_status(self, console):
        bar = StatusBar()
        result = bar.render({"llm_status": "online"})
        output = _render_to_string(console, result)
        assert "online" in output


class TestModulePanel:
    def test_renders_panel(self, console):
        panel = ModulePanel()
        result = panel.render(
            modules=["oracle", "atlas", "vex"],
            trust_scores={"oracle": 52, "atlas": 50, "vex": 47},
        )
        assert isinstance(result, Panel)

    def test_renders_with_no_modules(self, console):
        panel = ModulePanel()
        result = panel.render(modules=[], trust_scores={})
        assert isinstance(result, Panel)
        output = _render_to_string(console, result)
        assert "none loaded" in output

    def test_renders_trust_bars(self, console):
        panel = ModulePanel()
        result = panel.render(
            modules=["oracle"],
            trust_scores={"oracle": 80},
        )
        output = _render_to_string(console, result)
        # Should contain the module name
        assert "oracle" in output
        # Should contain block characters for trust bar
        assert "\u2588" in output

    def test_sorts_by_trust_descending(self, console):
        panel = ModulePanel()
        result = panel.render(
            modules=["low", "high", "mid"],
            trust_scores={"low": 10, "high": 90, "mid": 50},
        )
        output = _render_to_string(console, result)
        # high should appear before low in the rendered output
        high_pos = output.index("high")
        low_pos = output.index("low")
        assert high_pos < low_pos

    def test_many_modules_truncated(self, console):
        panel = ModulePanel()
        modules = [f"mod{i}" for i in range(20)]
        scores = {f"mod{i}": i * 5 for i in range(20)}
        result = panel.render(modules=modules, trust_scores=scores)
        assert isinstance(result, Panel)


class TestConversationPanel:
    def test_renders_panel(self, console):
        panel = ConversationPanel()
        result = panel.render(messages=[], current_input="")
        assert isinstance(result, Panel)

    def test_renders_empty_state(self, console):
        panel = ConversationPanel()
        result = panel.render(messages=[], current_input="")
        output = _render_to_string(console, result)
        assert "Type a message" in output

    def test_renders_user_message(self, console):
        panel = ConversationPanel()
        messages = [{"role": "user", "text": "hello world"}]
        result = panel.render(messages=messages, current_input="")
        output = _render_to_string(console, result)
        assert "hello world" in output

    def test_renders_response_with_module(self, console):
        panel = ConversationPanel()
        messages = [
            {"role": "user", "text": "scan"},
            {"role": "response", "text": "scanning...", "module": "oracle"},
        ]
        result = panel.render(messages=messages, current_input="")
        output = _render_to_string(console, result)
        assert "oracle" in output
        assert "scanning" in output

    def test_renders_current_input(self, console):
        panel = ConversationPanel()
        result = panel.render(messages=[], current_input="partial typ")
        output = _render_to_string(console, result)
        assert "partial typ" in output

    def test_renders_error_message(self, console):
        panel = ConversationPanel()
        messages = [{"role": "error", "text": "Something went wrong"}]
        result = panel.render(messages=messages, current_input="")
        output = _render_to_string(console, result)
        assert "Something went wrong" in output

    def test_truncates_long_history(self, console):
        panel = ConversationPanel()
        messages = [{"role": "user", "text": f"msg {i}"} for i in range(50)]
        result = panel.render(messages=messages, current_input="")
        assert isinstance(result, Panel)


class TestPulsePanel:
    def test_renders_panel(self, console):
        panel = PulsePanel()
        result = panel.render(events=[])
        assert isinstance(result, Panel)

    def test_renders_empty_state(self, console):
        panel = PulsePanel()
        result = panel.render(events=[])
        output = _render_to_string(console, result)
        assert "waiting for events" in output

    def test_renders_events(self, console):
        panel = PulsePanel()
        events = [
            {
                "timestamp": "2026-04-29T14:32:01+00:00",
                "topic": "cortex.route",
                "source": "cortex",
            },
            {
                "timestamp": "2026-04-29T14:32:05+00:00",
                "topic": "aegis.trust_change",
                "source": "aegis",
            },
        ]
        result = panel.render(events=events)
        output = _render_to_string(console, result)
        assert "cortex" in output

    def test_renders_many_events_truncated(self, console):
        panel = PulsePanel()
        events = [
            {
                "timestamp": f"2026-04-29T14:{i:02d}:00+00:00",
                "topic": f"topic.{i}",
                "source": f"src{i}",
            }
            for i in range(20)
        ]
        result = panel.render(events=events)
        assert isinstance(result, Panel)

    def test_handles_bad_timestamp(self, console):
        panel = PulsePanel()
        events = [{"timestamp": "bad", "topic": "test", "source": "x"}]
        result = panel.render(events=events)
        assert isinstance(result, Panel)


class TestChroniclePanel:
    def test_renders_panel(self, console):
        panel = ChroniclePanel()
        result = panel.render(entries=[])
        assert isinstance(result, Panel)

    def test_renders_empty_state(self, console):
        panel = ChroniclePanel()
        result = panel.render(entries=[])
        output = _render_to_string(console, result)
        assert "no entries yet" in output

    def test_renders_entries(self, console):
        panel = ChroniclePanel()
        entries = [
            {
                "timestamp": "2026-04-29T14:32:01+00:00",
                "source": "cortex",
                "action": "route",
                "payload": {"target": "oracle"},
            },
            {
                "timestamp": "2026-04-29T14:31:58+00:00",
                "source": "aegis",
                "action": "trust_change",
                "payload": {"new_trust": 52},
            },
        ]
        result = panel.render(entries=entries)
        output = _render_to_string(console, result)
        assert "cortex" in output
        assert "route" in output

    def test_renders_denied_action(self, console):
        panel = ChroniclePanel()
        entries = [
            {
                "timestamp": "2026-04-29T14:30:00+00:00",
                "source": "cortex",
                "action": "permission_denied",
                "payload": {"module": "wraith"},
            },
        ]
        result = panel.render(entries=entries)
        output = _render_to_string(console, result)
        assert "DENIED" in output

    def test_renders_response_action(self, console):
        panel = ChroniclePanel()
        entries = [
            {
                "timestamp": "2026-04-29T14:30:00+00:00",
                "source": "cortex",
                "action": "response",
                "payload": {"module": "general"},
            },
        ]
        result = panel.render(entries=entries)
        output = _render_to_string(console, result)
        assert "OK" in output

    def test_handles_bad_timestamp(self, console):
        panel = ChroniclePanel()
        entries = [
            {
                "timestamp": "invalid",
                "source": "test",
                "action": "test",
                "payload": {},
            },
        ]
        result = panel.render(entries=entries)
        assert isinstance(result, Panel)
