# NEXUS Phase 4 — Safety UX (backend) Implementation Plan (Phase 4 of 7)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the **backend layer** that powers the user-visible safety UX — install review and first-use prompt — without sacrificing anything we discussed. After Phase 4:

- Every tool call from an agent (built-in or catalog) routes through `aegis.check_capability()` before execution.
- A `Verdict.PROMPT` suspends the call, surfaces a `PermissionRequest` on a `PermissionInbox`, and resumes when the user answers (Allow once / Always in workspace / Always everywhere / Deny).
- Catalog agents can be **installed** via `nexus.agents.installer.install(...)` — manifest is validated, an install plan is shown, the user confirms, and the manifest lands at `~/.nexus/agents/<slug>/manifest.json` and is registered with Aegis.
- CLI: `onexus agent install/uninstall/permissions list/grant/revoke`.
- A minimal REST surface (`/api/permissions/*` + `/api/agents/install`) so Phase 5 surfaces can consume the backend.

Phase 4 is backend only. The actual UI panels — install review modal, first-use prompt slide-up, Settings → Security — are Phase 5.

**Architecture:**
- `nexus.kernel.aegis.PermissionRequest` — frozen dataclass; the in-flight ask.
- `nexus.kernel.aegis.PermissionInbox` — async mailbox; agents push, surfaces await/answer.
- `nexus.agents.installer.InstallPlan` — pydantic; groups manifest capabilities by class for review.
- `nexus.agents.installer.install(source, *, aegis, plan_callback=None)` — validates, gates on `plan_callback`, persists, registers.
- `InProcessAgent` + `MCPAgent` — `call_tool()` now consults Aegis before invoking; raises `PermissionDenied` on DENY, suspends on PROMPT.
- CLI extends with `onexus agent ...` subcommands.
- API gains `/api/permissions/pending`, `/api/permissions/decide`, `/api/agents/install`.

**Tech Stack:** Python 3.11+, pydantic 2, asyncio (mailbox), click (CLI), FastAPI (REST). No new deps.

**Related spec:** `docs/superpowers/specs/2026-06-06-nexus-agent-os-design.md` — §5.3 (MCP client), §5.4 (Capability filter), §9.2 (Install manifest review), §9.3 (First-use prompt), §16.1 (CLI).

**Prior phase:** `phase-3-workspaces` tag.

---

## Pre-flight

- Branch from `phase-3-workspaces` into `nexus-phase-4` (worktree `.worktrees/nexus-phase-4`).
- Baseline = **866 passing** (Phase 3 final). 28 baseline failures + 65 collection errors out of scope.
- `source .venv/bin/activate` at the start of each Bash invocation.

**File structure additions:**

```
nexus/
├── kernel/
│   └── aegis.py                (modify — add PermissionRequest + PermissionInbox)
├── agents/
│   ├── in_process_agent.py     (modify — gate call_tool through aegis)
│   ├── mcp_agent.py            (modify — gate call_tool through aegis)
│   └── installer.py            (new) — install/uninstall flow
├── api/routes/
│   ├── permissions.py          (new) — REST: pending, decide
│   └── installer.py            (new) — REST: /api/agents/install
└── cli.py                      (modify — onexus agent subcommands)

tests/
├── kernel/test_permission_inbox.py     (new)
├── agents/test_installer.py             (new)
├── agents/test_in_process_agent_gating.py  (new)
├── agents/test_mcp_agent_gating.py      (new)
├── cli/test_agent_commands.py           (new)
└── agents/test_phase_4_smoke.py         (new)
```

---

## Task 1 · `PermissionRequest` + `PermissionInbox`

**Why:** When a tool call gets `Verdict.PROMPT`, the runtime needs a way to (a) surface the ask, (b) suspend the call, (c) receive the user's decision, (d) resume. An asyncio-based mailbox is the cleanest primitive.

**Files:**
- Modify: `nexus/kernel/aegis.py` (add new types at module scope)
- Create: `tests/kernel/test_permission_inbox.py`

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for PermissionRequest + PermissionInbox."""
from __future__ import annotations

import asyncio
import pytest

from nexus.kernel.aegis import (
    PermissionRequest,
    PermissionDecision,
    PermissionInbox,
    PermissionScope,
)


def test_permission_request_is_frozen():
    req = PermissionRequest(
        agent_slug="aider",
        capability="fs.write.workspace",
        permission_class="Notable",
        workspace_id="ws-1",
        preview="diff …",
    )
    with pytest.raises(Exception):
        req.agent_slug = "evil"  # frozen — immutable


@pytest.mark.asyncio
async def test_inbox_round_trip():
    """Push a request; reader awaits it; writer answers; reader resumes."""
    inbox = PermissionInbox()

    async def actor():
        req = PermissionRequest(
            agent_slug="aider", capability="fs.write.workspace",
            permission_class="Notable", workspace_id="ws-1", preview="diff",
        )
        # The actor awaits the user's decision
        decision = await inbox.ask(req)
        return decision

    actor_task = asyncio.create_task(actor())
    await asyncio.sleep(0)  # let actor reach `ask`

    pending = inbox.pending()
    assert len(pending) == 1
    ticket_id = pending[0].id

    inbox.answer(ticket_id, PermissionDecision.ALLOW_ONCE)
    result = await actor_task
    assert result is PermissionDecision.ALLOW_ONCE


@pytest.mark.asyncio
async def test_inbox_deny_decision_propagates():
    inbox = PermissionInbox()

    async def actor():
        req = PermissionRequest(
            agent_slug="aider", capability="fs.write.workspace",
            permission_class="Notable", workspace_id="ws-1", preview="…",
        )
        return await inbox.ask(req)

    task = asyncio.create_task(actor())
    await asyncio.sleep(0)
    ticket = inbox.pending()[0]
    inbox.answer(ticket.id, PermissionDecision.DENY)
    assert await task is PermissionDecision.DENY


@pytest.mark.asyncio
async def test_inbox_pending_excludes_answered():
    inbox = PermissionInbox()
    req = PermissionRequest(
        agent_slug="a", capability="x", permission_class="Notable",
        workspace_id=None, preview="",
    )
    task = asyncio.create_task(inbox.ask(req))
    await asyncio.sleep(0)
    assert len(inbox.pending()) == 1
    ticket_id = inbox.pending()[0].id
    inbox.answer(ticket_id, PermissionDecision.ALLOW_ONCE)
    await task
    assert inbox.pending() == []


@pytest.mark.asyncio
async def test_inbox_unknown_ticket_raises():
    inbox = PermissionInbox()
    with pytest.raises(KeyError):
        inbox.answer("nonexistent-id", PermissionDecision.ALLOW_ONCE)


def test_permission_scope_values():
    """The four scope values must match the spec's first-use prompt options."""
    assert PermissionScope.ONCE.value == "once"
    assert PermissionScope.ALWAYS_IN_WORKSPACE.value == "always_in_workspace"
    assert PermissionScope.ALWAYS_EVERYWHERE.value == "always_everywhere"
    assert PermissionScope.NEVER.value == "never"
```

- [ ] **Step 2: Run; verify failure**

```bash
pytest tests/kernel/test_permission_inbox.py -v
```

Expected: ImportError on `PermissionRequest` / `PermissionInbox`.

- [ ] **Step 3: Add to `nexus/kernel/aegis.py`**

Append to the top of the file (after existing imports + module-level enums):

```python
import uuid
from enum import Enum as _Enum
```

(`Enum` is already imported; aliased here just to show the pattern — use the existing import.)

Add these module-level types (place AFTER `CapabilityDecision` and before the `PermissionDenied` class):

```python
class PermissionScope(str, Enum):
    """The user's choice when answering a first-use prompt (spec §9.3)."""
    ONCE = "once"
    ALWAYS_IN_WORKSPACE = "always_in_workspace"
    ALWAYS_EVERYWHERE = "always_everywhere"
    NEVER = "never"


class PermissionDecision(str, Enum):
    """The shape the inbox returns once the user has decided."""
    ALLOW_ONCE = "allow_once"
    ALLOW_ALWAYS_IN_WORKSPACE = "allow_always_in_workspace"
    ALLOW_ALWAYS_EVERYWHERE = "allow_always_everywhere"
    DENY = "deny"


@dataclass(frozen=True)
class PermissionRequest:
    agent_slug: str
    capability: str
    permission_class: str  # "Routine" / "Notable" / "Sensitive" / "Privileged"
    workspace_id: str | None
    preview: str = ""
    target: str | None = None  # path, URL, or command being requested
```

Then add the `PermissionInbox` class:

```python
class _PendingTicket:
    """One in-flight permission ask — pairs a request with the future that the asker is awaiting."""
    __slots__ = ("id", "request", "future")

    def __init__(self, request: PermissionRequest, future: "asyncio.Future[PermissionDecision]"):
        self.id = uuid.uuid4().hex[:12]
        self.request = request
        self.future = future


class PermissionInbox:
    """Async mailbox: agents push requests; surfaces await/answer them."""

    def __init__(self):
        self._tickets: dict[str, _PendingTicket] = {}

    async def ask(self, request: PermissionRequest) -> PermissionDecision:
        """Push a request and suspend until the user answers."""
        import asyncio
        loop = asyncio.get_running_loop()
        future: "asyncio.Future[PermissionDecision]" = loop.create_future()
        ticket = _PendingTicket(request, future)
        self._tickets[ticket.id] = ticket
        try:
            return await future
        finally:
            self._tickets.pop(ticket.id, None)

    def pending(self) -> list["_PendingView"]:
        """Snapshot of currently-pending tickets (for surfaces to render)."""
        return [_PendingView(t.id, t.request) for t in self._tickets.values()]

    def answer(self, ticket_id: str, decision: PermissionDecision) -> None:
        """Resolve a pending ticket."""
        ticket = self._tickets.get(ticket_id)
        if ticket is None:
            raise KeyError(f"unknown permission ticket: {ticket_id!r}")
        if not ticket.future.done():
            ticket.future.set_result(decision)


@dataclass(frozen=True)
class _PendingView:
    """Public read-only view of a pending ticket (for surfaces)."""
    id: str
    request: PermissionRequest
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/kernel/test_permission_inbox.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Full regression**

```bash
pytest --continue-on-collection-errors --tb=no -q 2>&1 | tail -3
```

Expected: 872 passing (866 + 6 new), 28 failed (baseline).

- [ ] **Step 6: Commit**

```bash
git add nexus/kernel/aegis.py tests/kernel/test_permission_inbox.py
git commit -m "feat(aegis): add PermissionRequest + PermissionInbox async mailbox"
```

---

## Task 2 · Gate `InProcessAgent.call_tool` through Aegis

**Why:** Spec §5.4. Every tool call must route through `aegis.check_capability()` before invocation. Phase 1 added the `aegis` kwarg to InProcessAgent but didn't use it; now we wire it.

**Files:**
- Modify: `nexus/agents/in_process_agent.py`
- Create: `tests/agents/test_in_process_agent_gating.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests that InProcessAgent gates tool calls through Aegis.check_capability."""
from __future__ import annotations

import asyncio
import pytest

from nexus.agents.in_process_agent import InProcessAgent
from nexus.agents.manifest import Manifest
from nexus.kernel.aegis import (
    Aegis,
    PermissionDecision,
    PermissionInbox,
    PermissionDenied,
)
from nexus.modules.base import NexusModule


class _NotableWriter(NexusModule):
    """A module whose `handle` tool is class=Notable, scope=fs.write.workspace."""
    name = "writer"
    description = "writes files"
    version = "0.1.0"

    @classmethod
    def manifest(cls):
        return Manifest.model_validate({
            "manifest_version": 1, "slug": "writer", "name": "writer",
            "version": "0.1.0", "system": True,
            "publisher": {"type": "org", "handle": "t"}, "category": "test",
            "identity": {"mark": {"kind": "builtin:writer", "gradient": ["#fff", "#000"]}},
            "intents": [],
            "capabilities": {
                "tools": [{"name": "handle", "class": "Notable",
                           "scope": "fs.write.workspace"}],
                "declared": {"Routine": [], "Notable": ["fs.write.workspace"],
                             "Sensitive": [], "Privileged": []},
            },
            "runtime": {"transport": "in_process"},
            "trust": {"floor": 0.0, "default_tier": "OBSERVER"},
        })

    async def handle(self, message, context):
        return f"wrote: {message}"


class _RoutineHelper(NexusModule):
    """A module whose `handle` tool is class=Routine — should never prompt."""
    name = "helper"
    description = "routine"
    version = "0.1.0"

    @classmethod
    def manifest(cls):
        return Manifest.model_validate({
            "manifest_version": 1, "slug": "helper", "name": "helper",
            "version": "0.1.0", "system": True,
            "publisher": {"type": "org", "handle": "t"}, "category": "test",
            "identity": {"mark": {"kind": "builtin:helper", "gradient": ["#fff", "#000"]}},
            "intents": [],
            "capabilities": {
                "tools": [{"name": "handle", "class": "Routine"}],
                "declared": {"Routine": ["engram.read.workspace"]},
            },
            "runtime": {"transport": "in_process"},
        })

    async def handle(self, message, context):
        return f"helper: {message}"


@pytest.fixture
def aegis(tmp_path):
    a = Aegis(str(tmp_path / "a.db"))
    a.init_db()
    a.register_manifest(_NotableWriter.manifest())
    a.register_manifest(_RoutineHelper.manifest())
    return a


@pytest.mark.asyncio
async def test_routine_tool_is_allowed_silently(aegis):
    agent = InProcessAgent(_RoutineHelper(), aegis=aegis)
    result = await agent.call_tool("handle", {"message": "ping", "context": {}})
    assert result == "helper: ping"


@pytest.mark.asyncio
async def test_notable_tool_with_grant_allowed(aegis):
    agent = InProcessAgent(_NotableWriter(), aegis=aegis)
    aegis.grant("writer", "fs.write.workspace")  # global
    result = await agent.call_tool(
        "handle", {"message": "ok", "context": {}, "workspace_id": "ws-1"},
    )
    assert result == "wrote: ok"


@pytest.mark.asyncio
async def test_notable_tool_without_grant_or_inbox_denied(aegis):
    """Without a grant AND without an inbox to ask, PROMPT raises PermissionDenied."""
    agent = InProcessAgent(_NotableWriter(), aegis=aegis)
    with pytest.raises(PermissionDenied):
        await agent.call_tool("handle", {"message": "x", "context": {}, "workspace_id": "ws-1"})


@pytest.mark.asyncio
async def test_notable_tool_with_inbox_allow_proceeds(aegis):
    """With an inbox attached, PROMPT pushes a ticket; ALLOW resolves it."""
    inbox = PermissionInbox()
    agent = InProcessAgent(_NotableWriter(), aegis=aegis, inbox=inbox)

    async def caller():
        return await agent.call_tool(
            "handle", {"message": "ok", "context": {}, "workspace_id": "ws-1"},
        )

    task = asyncio.create_task(caller())
    await asyncio.sleep(0.01)  # let caller reach the suspend point
    pending = inbox.pending()
    assert len(pending) == 1
    assert pending[0].request.agent_slug == "writer"
    inbox.answer(pending[0].id, PermissionDecision.ALLOW_ONCE)
    result = await task
    assert result == "wrote: ok"


@pytest.mark.asyncio
async def test_notable_tool_with_inbox_deny_raises(aegis):
    inbox = PermissionInbox()
    agent = InProcessAgent(_NotableWriter(), aegis=aegis, inbox=inbox)

    async def caller():
        return await agent.call_tool(
            "handle", {"message": "x", "context": {}, "workspace_id": "ws-1"},
        )

    task = asyncio.create_task(caller())
    await asyncio.sleep(0.01)
    inbox.answer(inbox.pending()[0].id, PermissionDecision.DENY)
    with pytest.raises(PermissionDenied):
        await task


@pytest.mark.asyncio
async def test_allow_always_in_workspace_persists_grant(aegis):
    inbox = PermissionInbox()
    agent = InProcessAgent(_NotableWriter(), aegis=aegis, inbox=inbox)

    async def caller(workspace_id):
        return await agent.call_tool(
            "handle", {"message": "ok", "context": {}, "workspace_id": workspace_id},
        )

    task = asyncio.create_task(caller("ws-1"))
    await asyncio.sleep(0.01)
    inbox.answer(inbox.pending()[0].id, PermissionDecision.ALLOW_ALWAYS_IN_WORKSPACE)
    assert await task == "wrote: ok"

    # Second call in same workspace must not prompt
    result = await agent.call_tool("handle", {"message": "again", "context": {}, "workspace_id": "ws-1"})
    assert result == "wrote: again"
    assert inbox.pending() == []
```

- [ ] **Step 2: Run; verify failures**

```bash
pytest tests/agents/test_in_process_agent_gating.py -v
```

Expected: most tests fail — `call_tool` doesn't gate yet.

- [ ] **Step 3: Modify `nexus/agents/in_process_agent.py`**

Update the class:

```python
"""
InProcessAgent — adapter that wraps a NexusModule and gates every
tool call through Aegis.check_capability() before invocation.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from nexus.modules.base import NexusModule

if TYPE_CHECKING:
    from nexus.kernel.aegis import Aegis, PermissionInbox


class InProcessAgent:
    def __init__(
        self,
        module: NexusModule,
        *,
        aegis: "Aegis | None" = None,
        inbox: "PermissionInbox | None" = None,
    ):
        self._module = module
        self._aegis = aegis
        self._inbox = inbox
        self._paused = False
        self._manifest = type(module).manifest()
        self._tools_by_name = {t["name"]: t for t in module.tools()}

    @property
    def slug(self) -> str:
        return self._manifest.slug

    @property
    def is_paused(self) -> bool:
        return self._paused

    def pause(self) -> None:
        self._paused = True

    def wake(self) -> None:
        self._paused = False

    async def call_tool(self, tool_name: str, args: dict[str, Any]) -> Any:
        if self._paused:
            raise RuntimeError(
                f"agent {self.slug!r} is paused; switch to its workspace to wake it"
            )
        if tool_name not in self._tools_by_name:
            raise KeyError(
                f"agent {self.slug!r} has no tool {tool_name!r}; "
                f"declared: {list(self._tools_by_name)}"
            )

        # Gate through Aegis if attached
        if self._aegis is not None:
            await self._gate(tool_name, args)

        # Dispatch
        if tool_name == "handle":
            message = args.get("message", "")
            context = args.get("context", {})
            return await self._module.handle(message, context)

        method = getattr(self._module, tool_name, None)
        if method is None:
            raise AttributeError(
                f"agent {self.slug!r} declares tool {tool_name!r} but the "
                f"module has no method by that name"
            )
        # Strip workspace_id from kwargs before forwarding to the module method
        method_args = {k: v for k, v in args.items() if k != "workspace_id"}
        return await method(**method_args)

    # ── gating ───────────────────────────────────────────────────────────

    async def _gate(self, tool_name: str, args: dict[str, Any]) -> None:
        from nexus.kernel.aegis import (
            PermissionDenied,
            PermissionRequest,
            PermissionDecision,
            Verdict,
        )

        tool = self._tools_by_name[tool_name]
        scope = tool.get("scope")
        if scope is None:
            return  # Routine tool with no declared scope — silent allow

        workspace_id = args.get("workspace_id")
        decision = self._aegis.check_capability(
            self.slug, scope, workspace_id=workspace_id,
        )

        if decision.verdict is Verdict.ALLOW:
            return
        if decision.verdict is Verdict.DENY:
            raise PermissionDenied(self.slug, f"{tool_name}:{scope}")

        # Verdict.PROMPT — surface to inbox if attached, else deny
        if self._inbox is None:
            raise PermissionDenied(self.slug, f"{tool_name}:{scope}:no_inbox")

        request = PermissionRequest(
            agent_slug=self.slug,
            capability=scope,
            permission_class=decision.permission_class.value if decision.permission_class else "Notable",
            workspace_id=workspace_id,
            preview=str(args.get("message", ""))[:200],
        )
        user_decision = await self._inbox.ask(request)
        await self._apply_decision(user_decision, scope, workspace_id)

    async def _apply_decision(self, decision, capability, workspace_id) -> None:
        from nexus.kernel.aegis import PermissionDecision, PermissionDenied
        if decision is PermissionDecision.DENY:
            raise PermissionDenied(self.slug, f"{capability}:user_denied")
        if decision is PermissionDecision.ALLOW_ONCE:
            return
        if decision is PermissionDecision.ALLOW_ALWAYS_IN_WORKSPACE:
            self._aegis.grant(self.slug, capability, workspace_id=workspace_id)
            return
        if decision is PermissionDecision.ALLOW_ALWAYS_EVERYWHERE:
            self._aegis.grant(self.slug, capability)  # workspace_id=None → global
            return
        raise RuntimeError(f"unhandled decision: {decision!r}")
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/agents/test_in_process_agent_gating.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Existing InProcessAgent tests still pass**

```bash
pytest tests/agents/test_in_process_agent.py tests/agents/test_foundation_integration.py -v 2>&1 | tail -15
```

Expected: same pass count as before. The existing tests don't pass `aegis` to InProcessAgent — when aegis is None, gating is skipped, preserving prior behaviour.

- [ ] **Step 6: Full regression**

```bash
pytest --continue-on-collection-errors --tb=no -q 2>&1 | tail -3
```

Expected: 878 passing (872 + 6 new), 28 failed (baseline).

- [ ] **Step 7: Commit**

```bash
git add nexus/agents/in_process_agent.py tests/agents/test_in_process_agent_gating.py
git commit -m "feat(in-process-agent): gate call_tool through aegis with inbox-based prompts"
```

---

## Task 3 · Gate `MCPAgent.call_tool` through Aegis

**Why:** Same as Task 2 but for the subprocess adapter — every MCP tool call gates through Aegis.

**Files:**
- Modify: `nexus/agents/mcp_agent.py`
- Create: `tests/agents/test_mcp_agent_gating.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests that MCPAgent gates tool calls through Aegis.check_capability."""
from __future__ import annotations

import asyncio
import sys

import pytest

from nexus.agents.manifest import Manifest
from nexus.agents.mcp_agent import MCPAgent
from nexus.kernel.aegis import (
    Aegis,
    PermissionDenied,
    PermissionDecision,
    PermissionInbox,
)


def _echo_manifest(command: list[str], capability_class: str = "Routine",
                   scope: str | None = None) -> Manifest:
    tool = {"name": "echo", "class": capability_class}
    declared: dict[str, list[str]] = {"Routine": [], "Notable": [],
                                       "Sensitive": [], "Privileged": []}
    if scope is not None:
        tool["scope"] = scope
        declared[capability_class].append(scope)
    return Manifest.model_validate({
        "manifest_version": 1, "slug": "echoer", "name": "echoer",
        "version": "0.1.0", "system": False,
        "publisher": {"type": "org", "handle": "test"}, "category": "test",
        "identity": {"mark": {"kind": "svg", "gradient": ["#fff", "#000"]}},
        "intents": [],
        "capabilities": {"tools": [tool], "declared": declared},
        "runtime": {"transport": "stdio", "command": command[0], "args": command[1:]},
    })


@pytest.fixture
def fake_server_path(tmp_path):
    path = tmp_path / "echo_server.py"
    path.write_text(
        "import asyncio\n"
        "from mcp.server import Server\n"
        "from mcp.server.stdio import stdio_server\n"
        "from mcp.types import Tool, TextContent\n"
        "srv = Server('echoer')\n"
        "@srv.list_tools()\n"
        "async def list_tools():\n"
        "    return [Tool(name='echo', description='echo', inputSchema={'type':'object','properties':{'message':{'type':'string'}}})]\n"
        "@srv.call_tool()\n"
        "async def call_tool(name, arguments):\n"
        "    return [TextContent(type='text', text=f\"echo:{arguments.get('message','')}\")]\n"
        "async def main():\n"
        "    async with stdio_server() as (r, w):\n"
        "        await srv.run(r, w, srv.create_initialization_options())\n"
        "asyncio.run(main())\n"
    )
    return path


@pytest.mark.asyncio
async def test_routine_mcp_tool_passes_through(tmp_path, fake_server_path):
    aegis = Aegis(str(tmp_path / "a.db"))
    aegis.init_db()
    manifest = _echo_manifest([sys.executable, str(fake_server_path)])
    aegis.register_manifest(manifest)
    agent = MCPAgent(manifest, aegis=aegis)
    await agent.start()
    try:
        result = await agent.call_tool("echo", {"message": "hi"})
        assert "echo:hi" in str(result)
    finally:
        await agent.stop()


@pytest.mark.asyncio
async def test_notable_mcp_tool_without_grant_denied(tmp_path, fake_server_path):
    aegis = Aegis(str(tmp_path / "a.db"))
    aegis.init_db()
    manifest = _echo_manifest(
        [sys.executable, str(fake_server_path)],
        capability_class="Notable", scope="fs.write.workspace",
    )
    aegis.register_manifest(manifest)
    agent = MCPAgent(manifest, aegis=aegis)
    await agent.start()
    try:
        with pytest.raises(PermissionDenied):
            await agent.call_tool("echo", {"message": "hi"})
    finally:
        await agent.stop()


@pytest.mark.asyncio
async def test_notable_mcp_tool_with_inbox_allow_proceeds(tmp_path, fake_server_path):
    aegis = Aegis(str(tmp_path / "a.db"))
    aegis.init_db()
    inbox = PermissionInbox()
    manifest = _echo_manifest(
        [sys.executable, str(fake_server_path)],
        capability_class="Notable", scope="fs.write.workspace",
    )
    aegis.register_manifest(manifest)
    agent = MCPAgent(manifest, aegis=aegis, inbox=inbox)
    await agent.start()
    try:
        async def caller():
            return await agent.call_tool("echo", {"message": "hi"})
        task = asyncio.create_task(caller())
        await asyncio.sleep(0.05)
        ticket = inbox.pending()[0]
        inbox.answer(ticket.id, PermissionDecision.ALLOW_ONCE)
        result = await task
        assert "echo:hi" in str(result)
    finally:
        await agent.stop()
```

- [ ] **Step 2: Run; verify failures**

```bash
pytest tests/agents/test_mcp_agent_gating.py -v
```

Expected: failures because MCPAgent doesn't take `aegis` or gate.

- [ ] **Step 3: Modify `nexus/agents/mcp_agent.py`**

Find `MCPAgent.__init__` and `call_tool`. Replace with:

```python
    def __init__(
        self,
        manifest: Manifest,
        *,
        aegis: "Aegis | None" = None,
        inbox: "PermissionInbox | None" = None,
    ):
        self._manifest = manifest
        self._aegis = aegis
        self._inbox = inbox
        # ... preserve all existing attribute initialization ...
        # (keep the existing _stack/_session/_process state)
```

Add the gating logic by reusing the same helper pattern as InProcessAgent. To avoid duplication, factor `_gate()` into a tiny shared helper. Create a new module-level helper in `nexus/agents/_gating.py`:

```python
"""Shared capability-check gating used by both InProcessAgent and MCPAgent."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from nexus.kernel.aegis import Aegis, PermissionInbox
    from nexus.agents.manifest import Manifest


async def gate_tool_call(
    agent_slug: str,
    manifest: "Manifest",
    tool_name: str,
    args: dict[str, Any],
    aegis: "Aegis | None",
    inbox: "PermissionInbox | None",
) -> None:
    """Check `aegis.check_capability` for this tool call; surface PROMPT to inbox.

    Returns None on ALLOW; raises PermissionDenied on DENY or user-denial.
    """
    if aegis is None:
        return  # no gating when aegis isn't attached (test paths)

    from nexus.kernel.aegis import (
        PermissionDecision,
        PermissionDenied,
        PermissionRequest,
        Verdict,
    )

    tool = manifest.tool(tool_name)
    if tool is None or tool.scope is None:
        return  # Routine tool with no declared scope

    workspace_id = args.get("workspace_id")
    decision = aegis.check_capability(agent_slug, tool.scope, workspace_id=workspace_id)

    if decision.verdict is Verdict.ALLOW:
        return
    if decision.verdict is Verdict.DENY:
        raise PermissionDenied(agent_slug, f"{tool_name}:{tool.scope}")

    # PROMPT
    if inbox is None:
        raise PermissionDenied(agent_slug, f"{tool_name}:{tool.scope}:no_inbox")

    request = PermissionRequest(
        agent_slug=agent_slug,
        capability=tool.scope,
        permission_class=tool.permission_class.value,
        workspace_id=workspace_id,
        preview=str(args.get("message", args))[:200],
    )
    user_decision = await inbox.ask(request)
    if user_decision is PermissionDecision.DENY:
        raise PermissionDenied(agent_slug, f"{tool.scope}:user_denied")
    if user_decision is PermissionDecision.ALLOW_ALWAYS_IN_WORKSPACE:
        aegis.grant(agent_slug, tool.scope, workspace_id=workspace_id)
    elif user_decision is PermissionDecision.ALLOW_ALWAYS_EVERYWHERE:
        aegis.grant(agent_slug, tool.scope)  # global
    # ALLOW_ONCE: do nothing extra; proceed
```

Then in `MCPAgent.call_tool`, before the existing `self._session.call_tool(...)` line, add:

```python
        from nexus.agents._gating import gate_tool_call
        await gate_tool_call(
            self.slug, self._manifest, tool_name, args, self._aegis, self._inbox,
        )
```

ALSO refactor `InProcessAgent._gate` (from Task 2) to delegate to the same helper — this keeps the gating logic in one place. In `nexus/agents/in_process_agent.py`, replace the body of `_gate` with:

```python
    async def _gate(self, tool_name: str, args: dict) -> None:
        from nexus.agents._gating import gate_tool_call
        await gate_tool_call(
            self.slug, self._manifest, tool_name, args, self._aegis, self._inbox,
        )
```

And delete the now-unused `_apply_decision` helper.

- [ ] **Step 4: Run all relevant tests**

```bash
pytest tests/agents/test_in_process_agent_gating.py tests/agents/test_mcp_agent_gating.py tests/agents/test_in_process_agent.py tests/agents/test_mcp_agent.py -v 2>&1 | tail -20
```

Expected: all pass. The shared `gate_tool_call` helper preserves both code paths.

- [ ] **Step 5: Full regression**

```bash
pytest --continue-on-collection-errors --tb=no -q 2>&1 | tail -3
```

Expected: 881 passing (878 + 3 new), 28 failed (baseline).

- [ ] **Step 6: Commit**

```bash
git add nexus/agents/mcp_agent.py nexus/agents/in_process_agent.py nexus/agents/_gating.py \
        tests/agents/test_mcp_agent_gating.py
git commit -m "feat(mcp-agent): gate call_tool through aegis via shared helper"
```

---

## Task 4 · `InstallPlan` + install validator

**Why:** Before persisting a third-party manifest, the user reviews what permissions the agent will request. The validator produces a structured plan grouped by class.

**Files:**
- Create: `nexus/agents/installer.py`
- Create: `tests/agents/test_installer.py`

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for InstallPlan and the install validator."""
from __future__ import annotations

import json

import pytest

from nexus.agents.installer import (
    InstallPlan,
    PlanGroup,
    plan_from_manifest_dict,
    plan_from_manifest_path,
)


def _valid_manifest_dict() -> dict:
    return {
        "manifest_version": 1,
        "slug": "browser-use",
        "name": "browser-use",
        "tagline": "Drives a real browser to do real things.",
        "version": "0.1.0",
        "system": False,
        "publisher": {"type": "org", "handle": "browser-use",
                      "url": "https://github.com/browser-use/browser-use"},
        "category": "browser-automation",
        "license": "Apache-2.0",
        "identity": {"mark": {"kind": "svg", "gradient": ["#fff", "#000"]}},
        "intents": [],
        "capabilities": {
            "tools": [
                {"name": "navigate", "class": "Notable",
                 "scope": "network.outbound.google.com"},
                {"name": "screenshot", "class": "Notable",
                 "scope": "fs.write.workspace"},
                {"name": "open_window", "class": "Sensitive",
                 "scope": "hardware.screen"},
            ],
            "declared": {
                "Routine": ["fs.read.workspace"],
                "Notable": ["network.outbound.google.com", "fs.write.workspace"],
                "Sensitive": ["hardware.screen"],
                "Privileged": [],
            },
        },
        "runtime": {"transport": "stdio", "command": "browser-use-mcp"},
    }


def test_plan_groups_by_class():
    plan = plan_from_manifest_dict(_valid_manifest_dict())
    by_class = {g.permission_class: g for g in plan.groups}
    assert "Routine" in by_class
    assert "Notable" in by_class
    assert "Sensitive" in by_class
    assert "fs.read.workspace" in by_class["Routine"].capabilities
    assert "fs.write.workspace" in by_class["Notable"].capabilities
    assert "hardware.screen" in by_class["Sensitive"].capabilities


def test_plan_skips_privileged_when_third_party():
    """A non-system manifest declaring Privileged must surface a warning."""
    d = _valid_manifest_dict()
    d["capabilities"]["declared"]["Privileged"] = ["engram.read.global"]
    plan = plan_from_manifest_dict(d)
    assert plan.has_privileged is True
    # Privileged caps still appear in the plan, but with the warning flag
    priv = next(g for g in plan.groups if g.permission_class == "Privileged")
    assert "engram.read.global" in priv.capabilities


def test_plan_records_publisher_and_license():
    plan = plan_from_manifest_dict(_valid_manifest_dict())
    assert plan.publisher == "browser-use"
    assert plan.license == "Apache-2.0"


def test_plan_summary_describes_each_class():
    plan = plan_from_manifest_dict(_valid_manifest_dict())
    summary = plan.short_summary()
    assert "Routine" in summary or "routine" in summary.lower()
    assert "Notable" in summary or "notable" in summary.lower()


def test_plan_from_path_round_trip(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(_valid_manifest_dict()))
    plan = plan_from_manifest_path(path)
    assert plan.slug == "browser-use"


def test_plan_rejects_invalid_manifest():
    with pytest.raises(Exception):
        plan_from_manifest_dict({"manifest_version": 1, "slug": "Bad Slug"})
```

- [ ] **Step 2: Run; verify failure**

```bash
pytest tests/agents/test_installer.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `nexus/agents/installer.py`**

```python
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
```

- [ ] **Step 4: Run**

```bash
pytest tests/agents/test_installer.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Regression**

```bash
pytest --continue-on-collection-errors --tb=no -q 2>&1 | tail -3
```

Expected: 887 passing (881 + 6 new), 28 failed (baseline).

- [ ] **Step 6: Commit**

```bash
git add nexus/agents/installer.py tests/agents/test_installer.py
git commit -m "feat(installer): add InstallPlan validator + persistence + Aegis registration"
```

---

## Task 5 · CLI · `onexus agent install/uninstall/permissions`

**Why:** The user-facing entrypoint for the install flow + permission management.

**Files:**
- Modify: `nexus/cli.py`
- Create: `tests/cli/test_agent_commands.py`

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for the agent CLI subcommands."""
from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from nexus.cli import main


def _manifest_dict() -> dict:
    return {
        "manifest_version": 1,
        "slug": "test-agent",
        "name": "test-agent",
        "version": "0.1.0",
        "system": False,
        "publisher": {"type": "org", "handle": "test"},
        "category": "test",
        "identity": {"mark": {"kind": "svg", "gradient": ["#fff", "#000"]}},
        "intents": [],
        "capabilities": {
            "tools": [{"name": "handle", "class": "Routine"}],
            "declared": {"Routine": ["engram.read.workspace"]},
        },
        "runtime": {"transport": "stdio", "command": "test-agent-mcp"},
    }


def test_agent_install_persists_manifest(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    manifest_file = tmp_path / "manifest.json"
    manifest_file.write_text(json.dumps(_manifest_dict()))

    runner = CliRunner()
    result = runner.invoke(main, ["agent", "install", str(manifest_file), "--yes"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "agents" / "test-agent" / "manifest.json").exists()


def test_agent_install_with_dry_run_shows_plan(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    manifest_file = tmp_path / "manifest.json"
    manifest_file.write_text(json.dumps(_manifest_dict()))

    runner = CliRunner()
    result = runner.invoke(main, ["agent", "install", str(manifest_file), "--dry-run"])
    assert result.exit_code == 0
    assert "test-agent" in result.output
    assert "Routine" in result.output or "routine" in result.output.lower()
    # Dry run must not write
    assert not (tmp_path / "agents" / "test-agent").exists()


def test_agent_uninstall_removes(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    manifest_file = tmp_path / "manifest.json"
    manifest_file.write_text(json.dumps(_manifest_dict()))
    runner = CliRunner()
    runner.invoke(main, ["agent", "install", str(manifest_file), "--yes"])
    result = runner.invoke(main, ["agent", "uninstall", "test-agent", "--yes"])
    assert result.exit_code == 0
    assert not (tmp_path / "agents" / "test-agent").exists()


def test_agent_list_shows_installed(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    manifest_file = tmp_path / "manifest.json"
    manifest_file.write_text(json.dumps(_manifest_dict()))
    runner = CliRunner()
    runner.invoke(main, ["agent", "install", str(manifest_file), "--yes"])
    result = runner.invoke(main, ["agent", "list"])
    assert "test-agent" in result.output
```

- [ ] **Step 2: Run; verify failures**

```bash
pytest tests/cli/test_agent_commands.py -v
```

Expected: `agent` sub-command doesn't exist.

- [ ] **Step 3: Add the `agent` group to `nexus/cli.py`**

Add AFTER the existing `workspace` group:

```python
@main.group()
def agent():
    """Manage installed agents."""
    pass


@agent.command("install")
@click.argument("manifest_source")
@click.option("--dry-run", is_flag=True, help="Show the install plan without persisting.")
@click.option("--yes", is_flag=True, help="Skip the confirmation prompt.")
def agent_install(manifest_source, dry_run, yes):
    """Install a manifest from a local path or URL."""
    from pathlib import Path
    from nexus.agents.installer import plan_from_manifest_path, install_from_plan
    from nexus.config import NexusConfig

    cfg = NexusConfig()
    src = Path(manifest_source)
    if not src.exists():
        click.echo(f"manifest not found: {manifest_source}", err=True)
        raise SystemExit(1)

    plan = plan_from_manifest_path(src)
    click.echo(plan.short_summary())
    if dry_run:
        click.echo("(dry run — nothing was installed)")
        return

    if not yes:
        if not click.confirm("install this agent?"):
            return
    target = install_from_plan(plan, cfg.data_dir)
    click.echo(f"installed: {plan.slug} -> {target}")


@agent.command("uninstall")
@click.argument("slug")
@click.option("--yes", is_flag=True, help="Skip the confirmation prompt.")
def agent_uninstall(slug, yes):
    """Remove an installed agent."""
    from nexus.agents.installer import uninstall as _uninstall
    from nexus.config import NexusConfig

    if not yes:
        if not click.confirm(f"uninstall {slug!r}? this removes all its data."):
            return
    cfg = NexusConfig()
    if _uninstall(slug, cfg.data_dir):
        click.echo(f"uninstalled: {slug}")
    else:
        click.echo(f"not installed: {slug}", err=True)
        raise SystemExit(1)


@agent.command("list")
def agent_list():
    """List installed agents."""
    from nexus.agents.installer import installed_slugs, load_installed_manifest
    from nexus.config import NexusConfig

    cfg = NexusConfig()
    slugs = installed_slugs(cfg.data_dir)
    if not slugs:
        click.echo("no installed agents")
        return
    for slug in slugs:
        m = load_installed_manifest(slug, cfg.data_dir)
        if m is not None:
            click.echo(f"  {slug:24}  v{m.version}  [{m.publisher.handle}]")
```

- [ ] **Step 4: Run**

```bash
pytest tests/cli/test_agent_commands.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Regression**

```bash
pytest --continue-on-collection-errors --tb=no -q 2>&1 | tail -3
```

Expected: 891 passing (887 + 4 new), 28 failed (baseline).

- [ ] **Step 6: Commit**

```bash
git add nexus/cli.py tests/cli/test_agent_commands.py
git commit -m "feat(cli): add onexus agent install/uninstall/list subcommands"
```

---

## Task 6 · REST endpoints — `/api/permissions/*` + `/api/agents/install`

**Why:** Phase 5 surfaces need an HTTP+WebSocket way to consume permission requests and trigger installs.

**Files:**
- Create: `nexus/api/routes/permissions.py`
- Create: `nexus/api/routes/installer.py`
- Modify: `nexus/api/server.py` (wire the new routers if not auto-included)
- Create: `tests/api/test_permissions_routes.py`

- [ ] **Step 1: Inspect the existing API server**

```bash
grep -n "include_router\|app = " nexus/api/server.py | head
```

Note how existing routers are wired so the new ones follow the same pattern.

- [ ] **Step 2: Write the failing tests**

```python
"""Tests for /api/permissions/* and /api/agents/install."""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from nexus.api.server import create_app
from nexus.kernel.aegis import PermissionRequest, PermissionInbox


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    app = create_app()
    return TestClient(app)


def test_permissions_pending_empty(client):
    resp = client.get("/api/permissions/pending")
    assert resp.status_code == 200
    assert resp.json() == {"pending": []}


def test_permissions_decide_unknown_ticket(client):
    resp = client.post(
        "/api/permissions/decide",
        json={"ticket_id": "nonexistent", "decision": "allow_once"},
    )
    assert resp.status_code == 404


def test_agents_install_validates_manifest(client, tmp_path):
    manifest = {
        "manifest_version": 1, "slug": "demo", "name": "demo",
        "version": "0.1.0", "system": False,
        "publisher": {"type": "org", "handle": "test"}, "category": "test",
        "identity": {"mark": {"kind": "svg", "gradient": ["#fff", "#000"]}},
        "intents": [],
        "capabilities": {"tools": [{"name": "handle", "class": "Routine"}],
                         "declared": {"Routine": ["engram.read.workspace"]}},
        "runtime": {"transport": "stdio", "command": "demo-mcp"},
    }
    resp = client.post("/api/agents/install", json={"manifest": manifest, "confirm": False})
    assert resp.status_code == 200
    body = resp.json()
    assert body["plan"]["slug"] == "demo"
    # confirm=False means dry-run; nothing persisted
    assert not (tmp_path / "agents" / "demo").exists()


def test_agents_install_confirm_persists(client, tmp_path):
    manifest = {
        "manifest_version": 1, "slug": "real", "name": "real",
        "version": "0.1.0", "system": False,
        "publisher": {"type": "org", "handle": "test"}, "category": "test",
        "identity": {"mark": {"kind": "svg", "gradient": ["#fff", "#000"]}},
        "intents": [],
        "capabilities": {"tools": [{"name": "handle", "class": "Routine"}],
                         "declared": {"Routine": ["engram.read.workspace"]}},
        "runtime": {"transport": "stdio", "command": "real-mcp"},
    }
    resp = client.post("/api/agents/install", json={"manifest": manifest, "confirm": True})
    assert resp.status_code == 200
    assert (tmp_path / "agents" / "real" / "manifest.json").exists()
```

- [ ] **Step 3: Run; verify failures**

Expected: 404 / 200 on permissions pending should succeed if the router is wired — the install routes are missing.

- [ ] **Step 4: Implement `nexus/api/routes/permissions.py`**

```python
"""REST endpoints for the PermissionInbox."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from nexus.kernel.aegis import PermissionInbox, PermissionDecision


router = APIRouter(prefix="/api/permissions", tags=["permissions"])


def _get_inbox(request: Request) -> PermissionInbox:
    inbox = getattr(request.app.state, "permission_inbox", None)
    if inbox is None:
        # Lazy-init when surfaces haven't attached one yet
        inbox = PermissionInbox()
        request.app.state.permission_inbox = inbox
    return inbox


class PendingView(BaseModel):
    id: str
    agent_slug: str
    capability: str
    permission_class: str
    workspace_id: str | None
    preview: str = ""
    target: str | None = None


class DecideRequest(BaseModel):
    ticket_id: str
    decision: str  # "allow_once" | "allow_always_in_workspace" | "allow_always_everywhere" | "deny"


@router.get("/pending")
async def pending(request: Request) -> dict:
    inbox = _get_inbox(request)
    return {
        "pending": [
            PendingView(
                id=p.id,
                agent_slug=p.request.agent_slug,
                capability=p.request.capability,
                permission_class=p.request.permission_class,
                workspace_id=p.request.workspace_id,
                preview=p.request.preview,
                target=p.request.target,
            ).model_dump()
            for p in inbox.pending()
        ],
    }


@router.post("/decide")
async def decide(request: Request, body: DecideRequest) -> dict:
    inbox = _get_inbox(request)
    try:
        decision = PermissionDecision(body.decision)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"invalid decision: {body.decision!r}")
    try:
        inbox.answer(body.ticket_id, decision)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"ticket not found: {body.ticket_id!r}")
    return {"ok": True}
```

- [ ] **Step 5: Implement `nexus/api/routes/installer.py`**

```python
"""REST endpoint for the agent install flow."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from nexus.agents.installer import plan_from_manifest_dict, install_from_plan
from nexus.config import NexusConfig


router = APIRouter(prefix="/api/agents", tags=["agents"])


class InstallRequest(BaseModel):
    manifest: dict
    confirm: bool = False


@router.post("/install")
async def install(request: Request, body: InstallRequest) -> dict:
    try:
        plan = plan_from_manifest_dict(body.manifest)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"invalid manifest: {exc}")

    plan_payload = {
        "slug": plan.slug,
        "name": plan.name,
        "version": plan.version,
        "publisher": plan.publisher,
        "license": plan.license,
        "tagline": plan.tagline,
        "groups": [
            {"permission_class": g.permission_class, "capabilities": g.capabilities}
            for g in plan.groups
        ],
        "has_privileged": plan.has_privileged,
    }

    if not body.confirm:
        return {"plan": plan_payload, "installed": False}

    cfg = NexusConfig()
    install_from_plan(plan, cfg.data_dir)
    return {"plan": plan_payload, "installed": True}
```

- [ ] **Step 6: Wire the routers in `nexus/api/server.py`**

Find the existing `app.include_router(...)` calls and add:

```python
    from nexus.api.routes.permissions import router as permissions_router
    from nexus.api.routes.installer import router as installer_router
    app.include_router(permissions_router)
    app.include_router(installer_router)
```

- [ ] **Step 7: Run tests**

```bash
pytest tests/api/test_permissions_routes.py -v
```

Expected: 4 passed.

- [ ] **Step 8: Regression**

```bash
pytest --continue-on-collection-errors --tb=no -q 2>&1 | tail -3
```

Expected: 895 passing (891 + 4 new), 28 failed (baseline).

- [ ] **Step 9: Commit**

```bash
git add nexus/api/routes/permissions.py nexus/api/routes/installer.py \
        nexus/api/server.py tests/api/test_permissions_routes.py
git commit -m "feat(api): add /api/permissions/* and /api/agents/install endpoints"
```

---

## Task 7 · End-to-end Phase 4 smoke

**Why:** Prove the whole stack — install validator → manifest persisted → tool call gated → prompt raised → user grants → call proceeds.

**Files:**
- Create: `tests/agents/test_phase_4_smoke.py`

- [ ] **Step 1: Write the test**

```python
"""End-to-end smoke for the safety UX backend."""
from __future__ import annotations

import asyncio
import json

import pytest

from nexus.agents.installer import (
    plan_from_manifest_dict, install_from_plan, load_installed_manifest,
)
from nexus.agents.in_process_agent import InProcessAgent
from nexus.agents.manifest import Manifest
from nexus.kernel.aegis import (
    Aegis, PermissionInbox, PermissionDecision, Verdict,
)
from nexus.modules.base import NexusModule


def _writer_manifest_dict() -> dict:
    return {
        "manifest_version": 1, "slug": "writer", "name": "writer",
        "version": "0.1.0", "system": False,
        "publisher": {"type": "org", "handle": "test"}, "category": "test",
        "identity": {"mark": {"kind": "svg", "gradient": ["#fff", "#000"]}},
        "intents": [],
        "capabilities": {
            "tools": [{"name": "handle", "class": "Notable",
                       "scope": "fs.write.workspace"}],
            "declared": {"Routine": [], "Notable": ["fs.write.workspace"],
                         "Sensitive": [], "Privileged": []},
        },
        "runtime": {"transport": "stdio", "command": "x"},
    }


class _StubWriter(NexusModule):
    """In-process module that emulates the 'writer' manifest above."""
    name = "writer"
    description = "writes"
    version = "0.1.0"

    @classmethod
    def manifest(cls):
        return Manifest.model_validate(_writer_manifest_dict())

    async def handle(self, message, context):
        return f"wrote: {message}"


@pytest.mark.asyncio
async def test_full_install_prompt_grant_call_cycle(tmp_path):
    # 1. Validate manifest as install plan
    plan = plan_from_manifest_dict(_writer_manifest_dict())
    assert plan.slug == "writer"
    assert any("fs.write.workspace" in g.capabilities for g in plan.groups)

    # 2. Persist + register
    aegis = Aegis(str(tmp_path / "aegis.db"))
    aegis.init_db()
    install_from_plan(plan, tmp_path, aegis=aegis)
    assert (tmp_path / "agents" / "writer" / "manifest.json").exists()
    assert load_installed_manifest("writer", tmp_path) is not None

    # 3. Build a gated agent (in-process emulation of the writer)
    inbox = PermissionInbox()
    agent = InProcessAgent(_StubWriter(), aegis=aegis, inbox=inbox)

    # 4. First tool call → suspended in inbox
    async def caller():
        return await agent.call_tool(
            "handle", {"message": "hello", "context": {}, "workspace_id": "ws-1"},
        )

    task = asyncio.create_task(caller())
    await asyncio.sleep(0.05)
    pending = inbox.pending()
    assert len(pending) == 1
    ticket = pending[0]
    assert ticket.request.agent_slug == "writer"
    assert ticket.request.capability == "fs.write.workspace"

    # 5. User grants always-in-workspace
    inbox.answer(ticket.id, PermissionDecision.ALLOW_ALWAYS_IN_WORKSPACE)
    result = await task
    assert result == "wrote: hello"

    # 6. Second call to same workspace: silent (grant persisted)
    result2 = await agent.call_tool(
        "handle", {"message": "again", "context": {}, "workspace_id": "ws-1"},
    )
    assert result2 == "wrote: again"
    assert inbox.pending() == []

    # 7. Call to a different workspace still prompts
    async def caller2():
        return await agent.call_tool(
            "handle", {"message": "elsewhere", "context": {}, "workspace_id": "ws-2"},
        )
    task2 = asyncio.create_task(caller2())
    await asyncio.sleep(0.05)
    assert len(inbox.pending()) == 1
    inbox.answer(inbox.pending()[0].id, PermissionDecision.DENY)
    from nexus.kernel.aegis import PermissionDenied
    with pytest.raises(PermissionDenied):
        await task2
```

- [ ] **Step 2: Run**

```bash
pytest tests/agents/test_phase_4_smoke.py -v
```

Expected: 1 passed (the test is one big lifecycle).

- [ ] **Step 3: Regression**

```bash
pytest --continue-on-collection-errors --tb=no -q 2>&1 | tail -3
```

Expected: 896 passing (895 + 1 new), 28 failed (baseline).

- [ ] **Step 4: Commit**

```bash
git add tests/agents/test_phase_4_smoke.py
git commit -m "test(agents): end-to-end Phase 4 smoke (install + prompt + grant + call)"
```

---

## Task 8 · Docs + tag

**Files:**
- Create: `docs/agents/safety-ux.md`

- [ ] **Step 1: Write the doc**

```markdown
# Safety UX Backend (Phase 4)

## The flow

1. **Agent tries to do something Notable or Sensitive.** Its tool call
   reaches `InProcessAgent.call_tool` or `MCPAgent.call_tool`, which
   delegate to `nexus.agents._gating.gate_tool_call`.

2. **Gating consults Aegis.** `aegis.check_capability(slug, scope, workspace_id)`
   returns ALLOW / PROMPT / DENY.

3. **On PROMPT, the gate pushes a `PermissionRequest`** to the
   `PermissionInbox` and suspends the call (asyncio Future).

4. **A surface** (CLI, REST, Phase-5 UI) renders the pending request,
   gets the user's decision, and calls `inbox.answer(ticket_id, decision)`.

5. **The gate resumes.** If the decision was ALLOW_ALWAYS_IN_WORKSPACE
   or ALLOW_ALWAYS_EVERYWHERE, the gate calls `aegis.grant(...)` so
   the next call skips the prompt.

## Install flow

```python
from nexus.agents.installer import (
    plan_from_manifest_path, install_from_plan, uninstall,
)

plan = plan_from_manifest_path("path/to/manifest.json")
print(plan.short_summary())   # show user what will be granted
install_from_plan(plan, data_dir, aegis=aegis)
```

CLI:

```
onexus agent install <manifest-path> [--dry-run] [--yes]
onexus agent uninstall <slug> [--yes]
onexus agent list
```

REST:

```
GET  /api/permissions/pending
POST /api/permissions/decide  {ticket_id, decision}
POST /api/agents/install      {manifest, confirm}
```

## Public types

| Name | Module | Purpose |
|---|---|---|
| `PermissionRequest` | `nexus.kernel.aegis` | Frozen dataclass; the ask |
| `PermissionDecision` | `nexus.kernel.aegis` | Enum: ALLOW_ONCE, ALLOW_ALWAYS_IN_WORKSPACE, ALLOW_ALWAYS_EVERYWHERE, DENY |
| `PermissionInbox` | `nexus.kernel.aegis` | `ask(req) → await` + `pending()` + `answer(id, decision)` |
| `InstallPlan` | `nexus.agents.installer` | Manifest grouped by class for review |
| `gate_tool_call` | `nexus.agents._gating` | Shared by InProcess + MCP adapters |

## What's NOT in Phase 4

- The UI panels (install review modal, first-use prompt slide-up) — Phase 5.
- Federation rewire through `aegis.network()` — Phase 6.
- LLM providers routing through `aegis.network()` — Phase 6.
```

- [ ] **Step 2: Verify regression baseline**

```bash
pytest --continue-on-collection-errors --tb=no -q 2>&1 | grep -E "^FAILED" | awk '{print $2}' | sort > /tmp/p4_failures.txt
diff .baseline_failures.txt /tmp/p4_failures.txt && echo "[FAILURE SET IDENTICAL TO BASELINE]"
```

- [ ] **Step 3: Commit docs + tag**

```bash
git add docs/agents/safety-ux.md
git commit -m "docs(agents): Phase 4 — safety UX backend"
git tag -a phase-4-safety-ux -m "Phase 4 safety UX backend complete: tool calls gated through Aegis, permission inbox, install flow

- PermissionRequest + PermissionInbox + PermissionDecision (async mailbox)
- gate_tool_call shared helper used by InProcessAgent + MCPAgent
- Tool calls now route through aegis.check_capability; PROMPT suspends, ALLOW proceeds, DENY raises
- ALLOW_ALWAYS_IN_WORKSPACE / ALLOW_ALWAYS_EVERYWHERE persist grants via aegis.grant
- InstallPlan validator + install_from_plan + uninstall
- CLI: onexus agent install/uninstall/list
- REST: /api/permissions/pending, /api/permissions/decide, /api/agents/install
- E2E smoke: full install → prompt → grant → call lifecycle

Suite: 896 passing (866 → 896, +30 net new tests)."
```

Phase 4 is complete. Phase 5 (Aurora surfaces) is unblocked.

---

## Self-Review

| Spec section | Implementing task | Notes |
|---|---|---|
| §5.4 Capability filter on tool calls | Tasks 2, 3 | InProcessAgent + MCPAgent both gate |
| §9.2 Install manifest review | Tasks 4, 5, 6 | InstallPlan + CLI + REST |
| §9.3 First-use prompt (backend) | Tasks 1, 2, 3 | PermissionInbox + gate_tool_call |
| §9.4 Trust-gated automation | Phase 1 already | check_capability auto-grants Notable at Executor |
| §16.1 CLI agent subcommands | Task 5 | install/uninstall/list |

**Open issues for Phase 5:** The UI panels that render `PermissionInbox.pending()` and the install review modal are Phase 5. Phase 5 will also add a WebSocket on `/ws/permissions` for live ticket pushes.
