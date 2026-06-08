"""
WorkspaceConfig — the pydantic model for workspace.json.

Every workspace persists its state to workspace.json using this schema.
Covers: filesystem roots, resident agents, routing pins, home tone,
mood biases, and timestamps.

See docs/superpowers/specs/2026-06-06-nexus-agent-os-design.md §7.
"""
from __future__ import annotations

import re
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


_WORKSPACE_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")


class WorkspaceTone(str, Enum):
    INDIGO = "INDIGO"
    MAGENTA = "MAGENTA"
    SAGE = "SAGE"
    PLUM = "PLUM"
    AMBER = "AMBER"


class RoutingPin(BaseModel):
    """Maps one intent OR one category to a preferred agent slug.

    Exactly one of ``intent`` or ``category`` must be provided.
    """
    model_config = ConfigDict(extra="forbid")

    intent: str | None = None
    category: str | None = None
    agent: str

    @model_validator(mode="after")
    def _exactly_one_key(self) -> "RoutingPin":
        has_intent = self.intent is not None
        has_category = self.category is not None
        if has_intent == has_category:  # both set or neither set
            raise ValueError(
                "RoutingPin must specify exactly one of 'intent' or 'category', "
                f"got intent={self.intent!r}, category={self.category!r}"
            )
        return self


class WorkspaceConfig(BaseModel):
    """The persisted configuration for a single workspace (workspace.json)."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    workspace_id: str
    name: str
    tone: WorkspaceTone = WorkspaceTone.INDIGO
    roots: list[str] = Field(default_factory=list)
    resident_agents: list[str] = Field(default_factory=list)
    routing_pins: list[RoutingPin] = Field(default_factory=list)
    mood_biases: dict[str, float] = Field(default_factory=dict)
    created_at: str = ""
    last_active_at: str = ""

    # ── validators ────────────────────────────────────────────────────────

    @field_validator("workspace_id")
    @classmethod
    def _workspace_id_kebab(cls, v: str) -> str:
        if not _WORKSPACE_ID_RE.match(v):
            raise ValueError(
                f"workspace_id must be kebab-case, start with a lowercase letter, "
                f"and be 1–64 chars; got {v!r}"
            )
        return v

    # ── convenience helpers ───────────────────────────────────────────────

    def resolved_roots(self) -> list[Path]:
        """Return filesystem roots as resolved Path objects."""
        return [Path(r).resolve() for r in self.roots]

    def pin_for_intent(self, intent: str) -> str | None:
        """Return the preferred agent slug for a given intent, or None."""
        for pin in self.routing_pins:
            if pin.intent == intent:
                return pin.agent
        return None

    def pin_for_category(self, category: str) -> str | None:
        """Return the preferred agent slug for a given category, or None."""
        for pin in self.routing_pins:
            if pin.category == category:
                return pin.agent
        return None
