# Safety UX Backend (Phase 4)

The backend that powers the user-visible safety surfaces — install
review and first-use prompt — built but not yet rendered. Phase 5
turns these primitives into Aurora UI panels.

## The flow

1. **An agent tries to do something Notable or Sensitive.** Its tool
   call reaches `InProcessAgent.call_tool` or `MCPAgent.call_tool`,
   which delegate to the shared `nexus.agents._gating.gate_tool_call`.

2. **Gating consults Aegis.**
   `aegis.check_capability(slug, scope, workspace_id)` returns ALLOW
   / PROMPT / DENY.

3. **On PROMPT**, the gate pushes a `PermissionRequest` to the
   `PermissionInbox` and suspends the call on an `asyncio.Future`.

4. **A surface** (CLI, REST, future UI) reads `inbox.pending()`,
   shows the request to the user, and calls
   `inbox.answer(ticket_id, decision)`.

5. **The gate resumes.** If the decision was
   `ALLOW_ALWAYS_IN_WORKSPACE` or `ALLOW_ALWAYS_EVERYWHERE`, the gate
   calls `aegis.grant(...)` so the next call skips the prompt.

## Install flow

```python
from nexus.agents.installer import (
    plan_from_manifest_path, install_from_plan, uninstall,
)

plan = plan_from_manifest_path("path/to/manifest.json")
print(plan.short_summary())   # show user what will be granted
install_from_plan(plan, data_dir, aegis=aegis)
```

The plan groups declared capabilities by class so a surface can
render four colour-coded blocks (Routine / Notable / Sensitive /
Privileged) per the spec atlas (§9.1, §10.5).

## CLI

```
onexus agent install <manifest-path> [--dry-run] [--yes]
onexus agent uninstall <slug> [--yes]
onexus agent list
```

`--dry-run` shows the install plan without persisting. `--yes` skips
the interactive confirmation.

## REST

```
GET  /api/permissions/pending     → { "pending": [PendingView] }
POST /api/permissions/decide      { ticket_id, decision }      → { "ok": true }
POST /api/agents/install          { manifest, confirm }        → { plan, installed }
```

`PendingView` fields: `id`, `agent_slug`, `capability`,
`permission_class`, `workspace_id`, `preview`, `target`.

`decision` accepts: `allow_once` / `allow_always_in_workspace` /
`allow_always_everywhere` / `deny`.

## Public types

| Name | Module | Purpose |
|---|---|---|
| `PermissionRequest` | `nexus.kernel.aegis` | Frozen dataclass; the ask |
| `PermissionDecision` | `nexus.kernel.aegis` | Enum: ALLOW_ONCE, ALLOW_ALWAYS_IN_WORKSPACE, ALLOW_ALWAYS_EVERYWHERE, DENY |
| `PermissionScope` | `nexus.kernel.aegis` | UI-facing scope label (once / always_in_workspace / always_everywhere / never) |
| `PermissionInbox` | `nexus.kernel.aegis` | `ask(req) → await`, `pending()`, `answer(id, decision)` |
| `InstallPlan` | `nexus.agents.installer` | Manifest grouped by class for review |
| `gate_tool_call` | `nexus.agents._gating` | Shared by InProcessAgent + MCPAgent; `defer_on_no_workspace` lets the InProcess path delegate to deeper aegis.fs/network gates when no workspace context is provided |

## What's NOT in Phase 4

- UI panels (install review modal, first-use prompt slide-up,
  Settings → Security) — Phase 5.
- WebSocket push of pending tickets — Phase 5.
- Federation rewire through `aegis.network()` — Phase 6.
- LLM providers routing through `aegis.network()` — Phase 6.
