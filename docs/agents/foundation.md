# Agent Runtime Foundation (Phase 1)

The minimum runtime surface every NEXUS agent — built-in or third-party —
goes through. See the full design at
`docs/superpowers/specs/2026-06-06-nexus-agent-os-design.md`
(§4 Kernel, §5 Agent Runtime, §6 Manifest, §9 Safety Model).

## Manifest

`nexus.agents.manifest.Manifest` — pydantic v2 model. The JSON Schema export
lives at `nexus/schemas/manifest.v1.json` (regenerate with
`python -m nexus.agents._schema_export`).

```python
from nexus.agents.manifest import Manifest
m = Manifest.from_path("/path/to/manifest.json")
```

Validation rules enforced by the model:

- `manifest_version` must equal `1`.
- `slug` must be kebab-case (`^[a-z][a-z0-9-]{0,63}$`) — both the pydantic
  validator and the JSON Schema `pattern` enforce this.
- Every `capabilities.tools[].scope` (if present) must appear in
  `capabilities.declared[its_class]` — a tool can only point at a scope its
  manifest already declares under the same permission class.

## Permission classes

`nexus.agents.manifest.PermissionClass` —
`ROUTINE / NOTABLE / SENSITIVE / PRIVILEGED`.

A tool descriptor names its class via `"class": "Notable"` in the JSON
(aliased to `permission_class` in Python). The class drives every Aegis
decision (spec §9):

| Class | Approval moment | Auto-grant at Executor (≥ 0.75)? |
|---|---|---|
| Routine | install | always (silent) |
| Notable | first-use prompt | yes, within declared scope |
| Sensitive | first-use prompt + 30-day re-confirm | no — always prompts |
| Privileged | Settings → Security only | no — never automatic |

## Aegis

The kernel's permission arbiter. Three new public surfaces (alongside the
existing trust + policy methods):

```python
from nexus.kernel.aegis import Aegis, Verdict, CapabilityDecision, PermissionDenied

aegis = Aegis(db_path)
aegis.init_db()
aegis.register_manifest(my_agent_manifest)

# Capability check — returns CapabilityDecision(verdict=ALLOW|PROMPT|DENY, reason, permission_class)
d = aegis.check_capability("aider", "fs.write.workspace", workspace_id="client-work")

# Filesystem broker — context-managed handle, raises PermissionDenied
with aegis.fs("aider", path, mode="r", workspace_roots=[root], workspace_id="ws") as f:
    data = f.read()

# Network gateway — async, returns httpx.Response, raises PermissionDenied
resp = await aegis.network("aider", "https://api.openai.com/...", method="POST",
                           workspace_id="ws", json={...})
```

### Grants

- `aegis.grant(agent_slug, capability, workspace_id=None)` —
  workspace_id=None records a global grant.
- `aegis.revoke_grant(agent_slug, capability=None, workspace_id=None)` —
  capability=None revokes every grant for that agent in that scope.
- A global grant (workspace_id=None) is honoured in any workspace.

The existing one-arg `aegis.revoke(module)` is preserved (resets trust to
0.0) but does NOT trigger the in-memory grant cleanup; use
`aegis.set_trust(module, 0.0)` if you want both.

### Trust collapse

`aegis.set_trust(slug, score)` writes the score directly and, if the new
score is below `0.50`, revokes every in-memory grant for that agent
across all workspaces. A `trust_collapse` event is written to Chronicle
with the list of revoked capabilities.

### Rate limiting

- `aegis.set_rate_limit(agent_slug, per_minute)` — per-agent rate limit
  for `aegis.network()`. Default: `Aegis.DEFAULT_RATE_LIMIT_PER_MIN`
  (60 rpm).
- A sliding 60-second window is enforced; over-limit requests raise
  `PermissionDenied` and log `network_request_denied` with
  `reason="rate_limit"`.

### Chronicle event names

| Event | Source |
|---|---|
| `permission_granted` | `grant()` |
| `permission_revoked` | `revoke_grant()` |
| `trust_collapse` | `set_trust()` when score < 0.50 |
| `fs_access` | `fs()` on success |
| `fs_access_denied` | `fs()` on containment OR capability failure |
| `network_request` | `network()` on success |
| `network_request_denied` | `network()` on capability OR rate-limit failure |

## Agent adapters

Both adapters expose the same surface:

```python
agent.slug                              # str
agent.is_paused                         # bool
agent.pause(); agent.wake()
await agent.call_tool(name, args)       # -> Any
```

### `nexus.agents.in_process_agent.InProcessAgent`

Wraps a `NexusModule`. Pause is a flag check (no SIGSTOP); call dispatch
is a direct Python call. Built-ins (the 9 cognitive modules) will run
this way in Phase 2.

```python
from nexus.agents.in_process_agent import InProcessAgent
from nexus.modules.council import CouncilModule  # example

agent = InProcessAgent(CouncilModule(), aegis=aegis)
result = await agent.call_tool("handle", {"message": "...", "context": ctx})
agent.pause()   # subsequent call_tool raises RuntimeError until wake()
agent.wake()
```

### `nexus.agents.mcp_agent.MCPAgent`

Wraps a subprocess that speaks MCP over stdio. We launch the process
ourselves (via `anyio.open_process`) so the PID is directly accessible
for SIGSTOP/SIGCONT. Three concurrent coroutines pump stdout↔ClientSession
and stdin↔ClientSession.

```python
from nexus.agents.mcp_agent import MCPAgent

agent = MCPAgent(manifest)
await agent.start()                     # launches subprocess + initializes MCP session
result = await agent.call_tool("echo", {"message": "hi"})
agent.pause()                           # SIGSTOP the subprocess
agent.wake()                            # SIGCONT
await agent.stop()                      # graceful shutdown + reap
```

## Refactored `NexusModule`

`nexus.modules.base.NexusModule` now declares two new surfaces:

```python
class CouncilModule(NexusModule):
    name = "council"
    description = "..."
    version = "0.1.0"

    @classmethod
    def manifest(cls) -> Manifest:
        # Phase 2 will populate the 9 built-ins.
        return Manifest.model_validate({...})

    def tools(self) -> list[dict[str, Any]]:
        # Default: a single Routine "handle" tool. Override for multi-tool modules.
        return super().tools()

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        ...
```

The default `manifest()` raises `NotImplementedError` so a concrete
module can't accidentally forget to declare itself. The default
`tools()` returns one `Routine`-class `handle` tool — enough for any
single-surface module.

## What's NOT in Phase 1

- Workspaces (Phase 3) — `Engram` partitions, `aegis.fs()`
  `workspace_roots` come from the workspace layer.
- Routing changes — `Cortex` still uses the hard-coded `_INTENT_DEFS`; it
  doesn't yet read manifests. Phase 2 wires the 9 built-ins onto
  manifests; the manifest-driven router is part of Phase 2's later
  steps.
- First-use prompt UI / install review UI (Phase 4 + Phase 5).
- LLM providers routing through `aegis.network()` (Phase 6).

Cross-reference:
`docs/superpowers/specs/2026-06-06-nexus-agent-os-design.md`.

---

## Phase 2 — Built-in Migration

All 10 built-in modules (the 9 cognitive modules + `agent_dispatcher`)
now ship with v1 manifests. Cortex's `IntentClassifier` reads intents
from a `BuiltinRegistry` (`nexus.agents.registry.BuiltinRegistry`) at
construction time, falling back to the legacy `_INTENT_DEFS` only when
the registry build fails.

### How a new built-in module joins the registry

1. Add `manifest()` classmethod to the module class:

   ```python
   class MyBuiltin(NexusModule):
       name = "my-builtin"
       description = "..."
       version = "0.1.0"

       @classmethod
       def manifest(cls):
           from nexus.agents.manifest import Manifest
           return Manifest.model_validate({...})

       async def handle(self, message, context):
           ...
   ```

2. Add the module class to `default_builtin_registry()` in
   `nexus/kernel/cortex.py`.

3. Done. Cortex picks up the new intents automatically; Aegis sees the
   manifest after `cortex.register_builtin_manifests()` runs at boot.

### Trust floors per built-in (current)

| Slug | Floor | Tier |
|---|---|---|
| council | 0.50 | MONITOR |
| legacy | 0.50 | MONITOR |
| echo | 0.50 | MONITOR |
| oracle | 0.40 | ADVISOR |
| specter | 0.40 | ADVISOR |
| consciousness | 0.40 | ADVISOR |
| sentry | 0.40 | ADVISOR |
| wraith | 0.35 | ADVISOR |
| autonomic | 0.30 | ADVISOR |
| agents | 0.30 | ADVISOR |

These are the trust scores Aegis seeds for each built-in on first
registration. They can be raised by `record_outcome(success=True)` or
lowered by `record_outcome(success=False)` over time, exactly like
catalog agents.

### Non-Routine capabilities declared by built-ins

| Slug | Notable | Privileged |
|---|---|---|
| autonomic | `process.spawn` | — |
| wraith | `process.spawn` | — |
| agents | `process.spawn`, `inter_agent.call.*` | — |
| echo | — | `engram.read.global` |

Every other built-in is Routine-only.
