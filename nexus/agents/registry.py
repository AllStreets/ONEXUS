"""
BuiltinRegistry — discovers and loads built-in agent manifests.

Phase 2 uses the explicit `from_modules([...])` constructor — the
controlling code knows which 10 built-ins to load. A later phase may
add auto-discovery via a plugin entry point.
"""
from __future__ import annotations

from typing import Iterable, Iterator, TYPE_CHECKING

from nexus.agents.manifest import Manifest
from nexus.modules.base import NexusModule

if TYPE_CHECKING:
    from nexus.kernel.aegis import Aegis


class BuiltinRegistry:
    def __init__(self, entries: list[tuple[Manifest, type[NexusModule]]]):
        self._entries = entries

    # ── construction ────────────────────────────────────────────────────

    @classmethod
    def from_modules(cls, module_classes: Iterable[type[NexusModule]]) -> "BuiltinRegistry":
        """Build a registry from explicit module classes. Calls .manifest()
        on each — if any raises NotImplementedError, the build fails fast.
        """
        entries: list[tuple[Manifest, type[NexusModule]]] = []
        for module_cls in module_classes:
            manifest = module_cls.manifest()  # raises if not implemented
            entries.append((manifest, module_cls))
        return cls(entries)

    # ── queries ─────────────────────────────────────────────────────────

    def slugs(self) -> list[str]:
        return [m.slug for m, _ in self._entries]

    def manifests(self) -> Iterator[Manifest]:
        for m, _ in self._entries:
            yield m

    def pairs(self) -> Iterator[tuple[Manifest, type[NexusModule]]]:
        yield from self._entries

    def __len__(self) -> int:
        return len(self._entries)

    # ── side effects ────────────────────────────────────────────────────

    def register_all(self, aegis: "Aegis") -> None:
        """Register every built-in manifest with Aegis."""
        for manifest, _ in self._entries:
            aegis.register_manifest(manifest)
