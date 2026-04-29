"""
NEXUS TUI panel renderers -- each produces a Rich renderable for its region.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.columns import Columns
from rich.console import Group

from nexus.tui.theme import trust_bar, trust_color, trust_tier_name


class StatusBar:
    """Top status bar showing system health indicators."""

    def render(self, health: dict[str, Any]) -> Panel:
        version = health.get("version", "0.1.0")
        llm_status = health.get("llm_status", "offline")
        module_count = health.get("module_count", 0)
        provider = health.get("provider", "local")
        uptime = health.get("uptime", "0:00:00")

        llm_color = "nexus.success" if llm_status == "online" else "nexus.danger"

        bar = Text()
        bar.append("  NEXUS ", style="bold nexus.primary")
        bar.append(f"v{version}", style="nexus.text.dim")
        bar.append("  ", style="")

        # Separator
        bar.append("\u2502 ", style="nexus.text.dim")

        bar.append("LLM: ", style="nexus.text.dim")
        bar.append(f"{llm_status}", style=llm_color)
        bar.append("  ", style="")

        bar.append("\u2502 ", style="nexus.text.dim")

        bar.append("Provider: ", style="nexus.text.dim")
        bar.append(f"{provider}", style="nexus.text")
        bar.append("  ", style="")

        bar.append("\u2502 ", style="nexus.text.dim")

        bar.append("Modules: ", style="nexus.text.dim")
        bar.append(f"{module_count}", style="nexus.primary")
        bar.append("  ", style="")

        bar.append("\u2502 ", style="nexus.text.dim")

        bar.append("Uptime: ", style="nexus.text.dim")
        bar.append(f"{uptime}", style="nexus.text")

        return Panel(
            bar,
            border_style="nexus.primary",
            height=3,
        )


class ModulePanel:
    """Renders the active modules list with trust score bars."""

    def render(self, modules: list[str], trust_scores: dict[str, int]) -> Panel:
        # Build two sections: module list and trust bars
        content = Text()

        # Active Modules header
        content.append(" ACTIVE MODULES\n", style="bold nexus.primary")
        content.append(" \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n", style="nexus.text.dim")

        if not modules:
            content.append("  (none loaded)\n", style="nexus.text.dim")
        else:
            # Sort modules by trust score descending
            sorted_mods = sorted(modules, key=lambda m: trust_scores.get(m, 0), reverse=True)
            for mod in sorted_mods[:12]:
                score = trust_scores.get(mod, 0)
                color = trust_color(score)
                content.append(f"  {mod:<12}", style="nexus.text")
                content.append(f"[{score:>3}]\n", style=color)

        content.append("\n", style="")

        # Trust Scores header
        content.append(" TRUST SCORES\n", style="bold nexus.primary")
        content.append(" \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n", style="nexus.text.dim")

        if trust_scores:
            # Show top modules by trust, with bars
            sorted_by_trust = sorted(trust_scores.items(), key=lambda x: x[1], reverse=True)
            for mod, score in sorted_by_trust[:8]:
                color = trust_color(score)
                bar = trust_bar(score, width=10)
                content.append(f"  {bar}", style=color)
                content.append(f" {score:>3}", style=color)
                content.append(f"  {mod}\n", style="nexus.text.dim")
        else:
            content.append("  (no scores)\n", style="nexus.text.dim")

        return Panel(
            content,
            border_style="nexus.border",
            title="[nexus.secondary]Modules[/]",
            title_align="left",
        )


class ConversationPanel:
    """Renders the scrollable conversation history."""

    def render(self, messages: list[dict[str, str]], current_input: str = "") -> Panel:
        content = Text()

        content.append(" CONVERSATION\n", style="bold nexus.primary")
        content.append(" \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n", style="nexus.text.dim")

        if not messages:
            content.append("  Type a message below to begin.\n", style="nexus.text.dim")

        # Show the last N messages that fit
        visible = messages[-30:] if len(messages) > 30 else messages
        for msg in visible:
            role = msg.get("role", "system")
            text = msg.get("text", "")
            module = msg.get("module", "")

            if role == "user":
                content.append("  > ", style="nexus.primary")
                content.append(f"{text}\n", style="nexus.text")
            elif role == "response":
                if module:
                    content.append(f"  [{module}] ", style="nexus.secondary")
                content.append(f"{text}\n", style="nexus.text")
            elif role == "system":
                content.append(f"  {text}\n", style="nexus.text.dim")
            elif role == "error":
                content.append(f"  {text}\n", style="nexus.danger")

        # Input prompt
        content.append("\n", style="")
        content.append("  > ", style="bold nexus.primary")
        content.append(current_input, style="nexus.text")
        content.append("\u2588", style="nexus.primary")  # cursor block

        return Panel(
            content,
            border_style="nexus.border",
            title="[nexus.secondary]Conversation[/]",
            title_align="left",
        )


class PulsePanel:
    """Renders live Pulse event feed."""

    def render(self, events: list[dict[str, Any]]) -> Panel:
        content = Text()

        content.append(" PULSE EVENTS\n", style="bold nexus.primary")
        content.append(" \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n", style="nexus.text.dim")

        if not events:
            content.append("  (waiting for events)\n", style="nexus.text.dim")
        else:
            # Show the most recent events (max 50, but display last ~8 for the panel)
            visible = events[-8:]
            for evt in visible:
                ts = evt.get("timestamp", "")
                # Parse and format timestamp to HH:MM:SS
                try:
                    if "T" in ts:
                        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        ts_short = dt.strftime("%H:%M:%S")
                    else:
                        ts_short = ts[:8] if len(ts) >= 8 else ts
                except Exception:
                    ts_short = ts[:8] if ts else "??:??:??"

                topic = evt.get("topic", "unknown")
                source = evt.get("source", "")

                # Color by topic prefix
                if "error" in topic or "denied" in topic:
                    color = "nexus.danger"
                elif "trust" in topic or "aegis" in topic:
                    color = "nexus.warning"
                elif "cortex" in topic:
                    color = "nexus.primary"
                else:
                    color = "nexus.text.dim"

                content.append(f"  {ts_short} ", style="nexus.text.dim")
                content.append(f"{source}", style=color)
                content.append(".", style="nexus.text.dim")
                content.append(f"{topic}\n", style=color)

        return Panel(
            content,
            border_style="nexus.border",
            title="[nexus.secondary]Pulse[/]",
            title_align="left",
        )


class ChroniclePanel:
    """Renders recent Chronicle audit log entries."""

    def render(self, entries: list[dict[str, Any]]) -> Panel:
        content = Text()

        content.append(" CHRONICLE\n", style="bold nexus.primary")
        content.append(" \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n", style="nexus.text.dim")

        if not entries:
            content.append("  (no entries yet)\n", style="nexus.text.dim")
        else:
            visible = entries[:8]  # Already sorted DESC by Chronicle.query
            for entry in visible:
                ts = entry.get("timestamp", "")
                try:
                    if "T" in ts:
                        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        ts_short = dt.strftime("%H:%M:%S")
                    else:
                        ts_short = ts[:8] if len(ts) >= 8 else ts
                except Exception:
                    ts_short = ts[:8] if ts else "??:??:??"

                source = entry.get("source", "unknown")
                action = entry.get("action", "unknown")
                payload = entry.get("payload", {})

                # Status indicator
                if "error" in action or "denied" in action:
                    status = "[DENIED]"
                    color = "nexus.danger"
                elif "route" in action:
                    target = payload.get("target", "")
                    status = f"[{target}]" if target else "[OK]"
                    color = "nexus.primary"
                elif "response" in action:
                    status = "[OK]"
                    color = "nexus.success"
                elif "trust" in action:
                    status = f"[{payload.get('new_trust', '?')}]"
                    color = "nexus.warning"
                else:
                    status = "[OK]"
                    color = "nexus.text.dim"

                content.append(f"  {ts_short} ", style="nexus.text.dim")
                content.append(f"{source}", style="nexus.text")
                content.append(" -> ", style="nexus.text.dim")
                content.append(f"{action} ", style="nexus.text")
                content.append(f"{status}\n", style=color)

        return Panel(
            content,
            border_style="nexus.border",
            title="[nexus.secondary]Chronicle[/]",
            title_align="left",
        )
