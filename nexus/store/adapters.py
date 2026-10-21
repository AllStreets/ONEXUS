"""Let AgentLauncher run store-installed agents without knowing about the store.

StoreAwareCatalog wraps AgentCatalog. For an agent the store installed it reports the
agent as runnable and describes it as an adapter whose `confinement` names the installed
image and the hosts the person approved, with the keys they gave in `secrets`. Every
other call goes to the catalog unchanged, so the launch path, round 2's environment
rules and round 3's confinement all apply as they do for any adapter.
"""
from __future__ import annotations

import dataclasses

from nexus.agents.catalog import AdapterDescriptor, AgentEntry
from nexus.store.state import StoreState


class StoreAwareCatalog:
    def __init__(self, catalog, state: StoreState) -> None:
        self._catalog = catalog
        self._state = state

    def __getattr__(self, name):
        return getattr(self._catalog, name)

    def get_agent(self, slug: str) -> AgentEntry | None:
        entry = self._catalog.get_agent(slug)
        if entry is not None and self._state.get(slug):
            return dataclasses.replace(entry, runnable=True)
        return entry

    def load_adapter(self, entry: AgentEntry) -> AdapterDescriptor | None:
        rec = self._state.get(entry.slug)
        if rec is None:
            return self._catalog.load_adapter(entry)
        command = rec.command[0] if rec.command else ""
        return AdapterDescriptor(
            name=entry.slug, transport="stdio", command=command,
            args=rec.command[1:] + rec.args,
            env={name: {} for name in rec.env_names},
            capabilities={"tools": list(rec.tools)},
            trust_floor=entry.trust_floor or 0.3,
            default_tier="ADVISOR",
            confinement={"image": rec.image, "command": command or None,
                         "hosts": list(rec.hosts), "entrypoint": not rec.command},
            secrets=self._state.secrets_for(entry.slug),
        )
