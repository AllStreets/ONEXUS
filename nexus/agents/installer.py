"""
Agent installer — validates a manifest, builds an InstallPlan that
surfaces what the agent will be able to do (grouped by permission class),
and writes the manifest to ~/.nexus/agents/<slug>/.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from nexus.agents.manifest import Manifest, PermissionClass

if TYPE_CHECKING:
    from nexus.kernel.aegis import Aegis


@dataclass(frozen=True)
class PlanGroup:
    permission_class: str
    capabilities: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class InstallPlan:
    """A structured 'what you'll grant' summary derived from a manifest."""
    slug: str
    name: str
    tagline: str
    version: str
    publisher: str
    license: str
    is_system: bool
    has_privileged: bool
    groups: list[PlanGroup]
    raw_manifest: dict

    def short_summary(self) -> str:
        lines = [f"{self.name} v{self.version} by {self.publisher}"]
        if self.tagline:
            lines.append(self.tagline)
        for g in self.groups:
            if g.capabilities:
                lines.append(f"  [{g.permission_class}] {', '.join(g.capabilities)}")
        return "\n".join(lines)


def plan_from_manifest_dict(data: dict) -> InstallPlan:
    manifest = Manifest.model_validate(data)
    declared = manifest.capabilities.declared
    groups = [
        PlanGroup("Routine", list(declared.routine)),
        PlanGroup("Notable", list(declared.notable)),
        PlanGroup("Sensitive", list(declared.sensitive)),
        PlanGroup("Privileged", list(declared.privileged)),
    ]
    return InstallPlan(
        slug=manifest.slug,
        name=manifest.name,
        tagline=manifest.tagline,
        version=manifest.version,
        publisher=manifest.publisher.handle,
        license=manifest.license,
        is_system=manifest.system,
        has_privileged=bool(declared.privileged),
        groups=groups,
        raw_manifest=data,
    )


def plan_from_manifest_path(path: str | Path) -> InstallPlan:
    return plan_from_manifest_dict(json.loads(Path(path).read_text()))


# ── persistence ────────────────────────────────────────────────────────────


def install_root(data_dir: Path) -> Path:
    """Return ~/.nexus/agents/ given the configured data_dir."""
    return Path(data_dir) / "agents"


def install_from_plan(plan: InstallPlan, data_dir: Path, *, aegis: "Aegis | None" = None) -> Path:
    """Persist the manifest to ~/.nexus/agents/<slug>/manifest.json and
    register it with Aegis if provided. Returns the manifest path."""
    target_dir = install_root(data_dir) / plan.slug
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "manifest.json"
    target.write_text(json.dumps(plan.raw_manifest, indent=2))
    if aegis is not None:
        aegis.register_manifest(Manifest.model_validate(plan.raw_manifest))
    return target


def uninstall(slug: str, data_dir: Path) -> bool:
    """Remove ~/.nexus/agents/<slug>/ entirely. Returns True if deleted."""
    import shutil
    target_dir = install_root(data_dir) / slug
    if not target_dir.exists():
        return False
    shutil.rmtree(target_dir)
    return True


def installed_slugs(data_dir: Path) -> list[str]:
    root = install_root(data_dir)
    if not root.exists():
        return []
    return sorted(p.name for p in root.iterdir() if (p / "manifest.json").exists())


def load_installed_manifest(slug: str, data_dir: Path) -> Manifest | None:
    path = install_root(data_dir) / slug / "manifest.json"
    if not path.exists():
        return None
    return Manifest.from_path(path)
