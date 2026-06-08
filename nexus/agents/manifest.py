"""
Agent manifest v1 — typed model + JSON Schema export.

Every NEXUS agent (built-in or third-party) declares its identity,
intents, capabilities, and runtime via this manifest. Cortex reads
`intents`; Aegis reads `capabilities`; the runtime reads `runtime`;
the surfaces read `identity`.

See docs/superpowers/specs/2026-06-06-nexus-agent-os-design.md §6.
"""
from __future__ import annotations

import json
import re
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


_SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")


class PermissionClass(str, Enum):
    ROUTINE = "Routine"
    NOTABLE = "Notable"
    SENSITIVE = "Sensitive"
    PRIVILEGED = "Privileged"


class TrustTierName(str, Enum):
    OBSERVER = "OBSERVER"
    ADVISOR = "ADVISOR"
    MONITOR = "MONITOR"
    EXECUTOR = "EXECUTOR"
    AUTONOMOUS = "AUTONOMOUS"


class Publisher(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["org", "individual"]
    handle: str
    url: str | None = None


class IdentityMark(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str = Field(description='"svg" or "builtin:<slug>"')
    path: str | None = None
    gradient: list[str] = Field(default_factory=list, max_length=4)


class Identity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mark: IdentityMark


class IntentDecl(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    patterns: list[str] = Field(default_factory=list)
    semantic_signals: list[str] = Field(default_factory=list)
    weight: float = Field(default=1.0, ge=0.0, le=2.0)


class ToolDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: str
    permission_class: PermissionClass = Field(alias="class")
    scope: str | None = None


class DeclaredCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    routine: list[str] = Field(default_factory=list, alias="Routine")
    notable: list[str] = Field(default_factory=list, alias="Notable")
    sensitive: list[str] = Field(default_factory=list, alias="Sensitive")
    privileged: list[str] = Field(default_factory=list, alias="Privileged")

    def all(self) -> list[str]:
        return [*self.routine, *self.notable, *self.sensitive, *self.privileged]

    def for_class(self, cls: PermissionClass) -> list[str]:
        return {
            PermissionClass.ROUTINE: self.routine,
            PermissionClass.NOTABLE: self.notable,
            PermissionClass.SENSITIVE: self.sensitive,
            PermissionClass.PRIVILEGED: self.privileged,
        }[cls]


class Capabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tools: list[ToolDescriptor] = Field(default_factory=list)
    declared: DeclaredCapabilities = Field(default_factory=DeclaredCapabilities)


class RuntimeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transport: Literal["stdio", "sse", "in_process"]
    command: str = ""
    args: list[str] = Field(default_factory=list)
    env_keys: list[str] = Field(default_factory=list)


class TrustConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    floor: float = Field(default=0.0, ge=0.0, le=1.0)
    default_tier: TrustTierName = TrustTierName.OBSERVER


class Compatibility(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nexus_version: str = ">=1.0.0"


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid")

    github: str | None = None
    huggingface: str | None = None
    homepage: str | None = None


class Manifest(BaseModel):
    """The v1 agent manifest."""
    model_config = ConfigDict(extra="forbid")

    manifest_version: Literal[1]
    slug: str = Field(pattern=r"^[a-z][a-z0-9-]{0,63}$")
    name: str
    tagline: str = ""
    version: str
    system: bool = False
    publisher: Publisher
    category: str
    tags: list[str] = Field(default_factory=list)
    license: str = "Unknown"
    source: Source = Field(default_factory=Source)
    identity: Identity
    intents: list[IntentDecl] = Field(default_factory=list)
    capabilities: Capabilities = Field(default_factory=Capabilities)
    runtime: RuntimeConfig
    trust: TrustConfig = Field(default_factory=TrustConfig)
    compatibility: Compatibility = Field(default_factory=Compatibility)

    # ── validators ────────────────────────────────────────────────────────

    @field_validator("slug")
    @classmethod
    def _slug_kebab(cls, v: str) -> str:
        if not _SLUG_RE.match(v):
            raise ValueError(
                f"slug must be kebab-case, start with a lowercase letter, "
                f"and be 1–64 chars; got {v!r}"
            )
        return v

    @model_validator(mode="after")
    def _tool_scopes_declared(self) -> "Manifest":
        """Every tool.scope must appear in capabilities.declared[its_class]."""
        for tool in self.capabilities.tools:
            if tool.scope is None:
                continue
            declared = self.capabilities.declared.for_class(tool.permission_class)
            if tool.scope not in declared:
                raise ValueError(
                    f"tool {tool.name!r} references scope {tool.scope!r} which "
                    f"is not declared under {tool.permission_class.value}"
                )
        return self

    # ── convenience helpers ───────────────────────────────────────────────

    @classmethod
    def from_path(cls, path: str | Path) -> "Manifest":
        data = json.loads(Path(path).read_text())
        return cls.model_validate(data)

    def tool(self, name: str) -> ToolDescriptor | None:
        for t in self.capabilities.tools:
            if t.name == name:
                return t
        return None

    def declares(self, capability: str) -> PermissionClass | None:
        """Which class does this manifest declare a capability under (if any)?"""
        d = self.capabilities.declared
        for cls in PermissionClass:
            if capability in d.for_class(cls):
                return cls
        return None
