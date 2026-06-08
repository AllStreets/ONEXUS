"""
Built-in workspace templates — six canonical starting points.

Templates are structural only: they define tone, a suggested roster of
resident agents, routing pins, and optional mood biases.  They contain
no memory, conversation history, or permission grants.

Usage
-----
    from nexus.workspaces.templates import TEMPLATES, apply_template
    from nexus.workspaces.manager import WorkspaceManager

    mgr = WorkspaceManager(root)
    ws = apply_template("coding", workspace_id="my-code", name="My Coding Room", manager=mgr)

See docs/superpowers/specs/2026-06-06-nexus-agent-os-design.md §7.6.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from nexus.workspaces.config import WorkspaceConfig

if TYPE_CHECKING:
    from nexus.workspaces.manager import WorkspaceManager


# ── template definition ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class WorkspaceTemplate:
    """Structural blueprint for a new workspace.

    Attributes
    ----------
    slug:
        Machine-readable identifier (e.g. ``"coding"``).
    label:
        Human-readable display name (e.g. ``"Coding"``).
    description:
        One-line summary shown in the template picker.
    tone:
        Default home tone (WorkspaceTone value string).
    resident_agents:
        Suggested initial roster of agent slugs.
    routing_pins:
        List of ``{"intent": ..., "agent": ...}`` or
        ``{"category": ..., "agent": ...}`` dicts.
    mood_biases:
        Initial mood bias weights (empty for most templates).
    """

    slug: str
    label: str
    description: str
    tone: str
    resident_agents: list[str] = field(default_factory=list)
    routing_pins: list[dict] = field(default_factory=list)
    mood_biases: dict[str, float] = field(default_factory=dict)


# ── six canonical templates (spec §7.6) ───────────────────────────────────────

TEMPLATES: dict[str, WorkspaceTemplate] = {
    "coding": WorkspaceTemplate(
        slug="coding",
        label="Coding",
        description="Software development workspace with aider, cline, and council.",
        tone="INDIGO",
        resident_agents=["aider", "cline", "council"],
        routing_pins=[{"intent": "CODE", "agent": "aider"}],
        mood_biases={},
    ),
    "design": WorkspaceTemplate(
        slug="design",
        label="Design / Generative",
        description="Creative and generative AI workspace favouring Creative mood.",
        tone="MAGENTA",
        resident_agents=["comfyui", "echo", "sd-webui"],
        routing_pins=[],
        mood_biases={"Creative": 0.6},
    ),
    "research": WorkspaceTemplate(
        slug="research",
        label="Research",
        description="Deep research workspace with council, specter, and browser-use.",
        tone="SAGE",
        resident_agents=["council", "specter", "browser-use"],
        routing_pins=[{"intent": "DELIBERATE", "agent": "council"}],
        mood_biases={"Watchful": 0.5},
    ),
    "writing": WorkspaceTemplate(
        slug="writing",
        label="Writing",
        description="Long-form writing workspace favouring Reflective mood.",
        tone="PLUM",
        resident_agents=["echo", "council", "consciousness"],
        routing_pins=[],
        mood_biases={"Reflective": 0.5},
    ),
    "personal": WorkspaceTemplate(
        slug="personal",
        label="Personal",
        description="Personal assistant workspace with echo and sentry.",
        tone="AMBER",
        resident_agents=["echo", "sentry"],
        routing_pins=[],
        mood_biases={},
    ),
    "blank": WorkspaceTemplate(
        slug="blank",
        label="Blank",
        description="Start from scratch — choose your own tone and agents.",
        tone="INDIGO",
        resident_agents=[],
        routing_pins=[],
        mood_biases={},
    ),
}


# ── helper ────────────────────────────────────────────────────────────────────


def apply_template(
    template_slug: str,
    *,
    workspace_id: str,
    name: str,
    manager: "WorkspaceManager",
    tone_override: str | None = None,
) -> WorkspaceConfig:
    """Create a new workspace from a named template.

    Parameters
    ----------
    template_slug:
        One of the keys in :data:`TEMPLATES` (e.g. ``"coding"``).
    workspace_id:
        Kebab-case ID for the new workspace.
    name:
        Human-readable display name.
    manager:
        A :class:`~nexus.workspaces.manager.WorkspaceManager` instance
        pointing at the workspaces root directory.
    tone_override:
        If provided, overrides the template's default tone.

    Raises
    ------
    KeyError
        If *template_slug* is not one of the six known templates.
    FileExistsError
        If a workspace with *workspace_id* already exists.
    """
    if template_slug not in TEMPLATES:
        available = ", ".join(sorted(TEMPLATES))
        raise KeyError(
            f"Unknown template {template_slug!r}. Available: {available}"
        )

    tmpl = TEMPLATES[template_slug]
    tone = tone_override if tone_override is not None else tmpl.tone

    return manager.create(
        name=name,
        workspace_id=workspace_id,
        tone=tone,
        resident_agents=tmpl.resident_agents,
        pins=tmpl.routing_pins,
        mood_biases=tmpl.mood_biases,
    )
