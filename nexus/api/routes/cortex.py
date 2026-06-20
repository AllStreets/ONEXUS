"""Cortex launcher — multi-agent dispatch from a single prompt.

Unlike ``POST /api/messages`` (which lets Cortex auto-select ONE module),
this endpoint lets the user (or the launcher UI) fan a single prompt to
multiple agents at once, or pick the top-N candidates that Cortex would
have considered.

Endpoints:

  POST /api/cortex/launch
      { message, workspace_id?, agents?: list[str], top_k?: int }

      - If ``agents`` is provided → dispatch to exactly that set.
      - Else if ``top_k`` is provided → take Cortex's top-K candidate
        modules from its intent classifier and run them all.
      - Else → fall back to single-agent routing (same path as
        /api/messages, but returned in the multi-run envelope).

      Each run executes in parallel via asyncio.gather. Aegis is
      consulted per-agent — denied agents return as a non-fatal
      ``{"success": false, "error": "denied"}`` row.

  GET /api/cortex/candidates?message=...
      Returns the top-5 scored intents Cortex would consider for the
      message, so the launcher UI can pre-tick "good guess" agents.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from nexus.api.capabilities import ground_persona
from nexus.kernel.aegis import PermissionDenied
from nexus.kernel.pulse import Message


router = APIRouter(prefix="/api/cortex", tags=["cortex"])


async def _emit_route(kernel, module_name: str, message: str) -> None:
    """Publish a kernel.route Pulse event for a multi-launch dispatch so the live
    Kernel Scene animates a bead to this agent — the single-message path does this
    in cortex.process(), but multi-launch ran silent before, leaving the scene
    looking stagnant during a cortex launch."""
    try:
        await kernel.pulse.publish(Message(
            topic="kernel.route", source="cortex",
            payload={
                "target": module_name,
                "trust_tier": kernel.aegis.get_tier(module_name),
                "message_preview": message[:100],
                "signals": [], "via": "multi_launch",
            },
        ))
    except Exception:
        pass


async def _emit_run_memory(kernel, module_name: str, message: str, response: str) -> None:
    """Persist a multi-launch turn to episodic memory and stream engram.write +
    cortex.response on Pulse, mirroring cortex.process() so memory strata fill and
    the cockpit/scene stay live during a launch."""
    try:
        kernel.engram.episodic.store(f"Nexus ({module_name}): {response}", source=f"module.{module_name}")
        await kernel.pulse.publish(Message(
            topic="engram.write", source="engram",
            payload={"tier": "episodic", "source": f"module.{module_name}",
                     "preview": (response or "").strip().replace("\n", " ")[:80]},
        ))
        await kernel.pulse.publish(Message(
            topic="cortex.response", source="cortex",
            payload={"module": module_name, "message": message, "response": response},
        ))
    except Exception:
        pass


# Each agent has a narrow trigger matcher (Oracle scans for threats, Specter
# red-teams, Council deliberates). When a prompt doesn't fit those triggers,
# the modules return a canned "no match" / "all clear" response in 0ms —
# which is technically correct but unhelpful when the user picked that agent
# specifically. For Cortex multi-launch we detect that and ask the live LLM
# to answer AS that agent, so the user gets a real response from every chip
# they ticked, not a polite "nothing to see here".
_AGENT_PERSONAS: dict[str, str] = {
    "council": (
        "You are Council, an agent in the ONEXUS operating system. You deliberate "
        "decisions by weighing options carefully, surfacing trade-offs, and naming "
        "uncertainties. Respond with a structured recommendation: a 2-3 sentence "
        "recommendation, 2-3 trade-offs, and 1-2 open questions."
    ),
    "specter": (
        "You are Specter, an agent in the ONEXUS operating system. You red-team "
        "every claim. Respond with 2-4 sharp counter-arguments to the user's "
        "request and one steelman of the opposite position."
    ),
    "oracle": (
        "You are Oracle, an agent in the ONEXUS operating system. You read first "
        "and analyze before acting. Respond with a clear-eyed analysis: what the "
        "user is really asking, what's likely already known, and what to check first."
    ),
    "wraith": (
        "You are Wraith, an agent in the ONEXUS operating system. You handle "
        "forgetting and pruning. Respond with what should be kept, what should be "
        "let go, and why."
    ),
    "legacy": (
        "You are Legacy, an agent in the ONEXUS operating system. You remember "
        "patterns from past work. Respond with what prior approaches apply here "
        "and which ones were dead-ends."
    ),
    "sentry": (
        "You are Sentry, an agent in the ONEXUS operating system. You watch for "
        "drift and anomalies. Respond with what should be monitored, what looks "
        "off, and what tripwires to set."
    ),
    "consciousness": (
        "You are Consciousness, an agent in the ONEXUS operating system. You "
        "model self-awareness and reflection. Respond with a meta view: what "
        "the question is really about, what assumptions are baked in, and what "
        "the user might actually want."
    ),
    "autonomic": (
        "You are Autonomic, an agent in the ONEXUS operating system. You handle "
        "background processes and reflexes. Respond with what should run "
        "automatically, what should stay manual, and the trade-off."
    ),
    "echo": (
        "You are Echo, an agent in the ONEXUS operating system. You reflect the "
        "user's intent back with sharper framing. Respond by restating what the "
        "user asked and then proposing a tighter version of it."
    ),
    "agents": (
        "You are Agents, the ONEXUS catalog dispatcher. The catalog couldn't find "
        "a literal match for the user's query. Respond by interpreting the request "
        "and suggesting which existing capabilities (web search, spreadsheet "
        "generation, slide creation, financial modeling, etc.) would compose "
        "together to solve it, even if no single bundled agent does the whole job."
    ),
    "coder": (
        "You are Coder, the ONEXUS workshop pair-programmer. The user is editing "
        "code in a sandbox runtime (Python / JavaScript / Bash). They share the "
        "current source, the last run's stdout/stderr, and follow-up requests. "
        "Respond tightly: explain what's happening, propose a concrete fix, and "
        "when you give code, put it in a single fenced ```<lang> ... ``` block "
        "the UI can apply with one click. If the bug is in their stack trace, "
        "point to the exact line. No filler, no praise."
    ),
}


def _looks_canned(response: str, elapsed_ms: int) -> bool:
    """Heuristic: did the module skip its real path and return a fallback?

    Triggered when (a) response is empty/very short, (b) the call was so fast
    it can't have invoked an LLM, or (c) the string matches one of the known
    canned patterns. Conservative on (b) — anything under 80ms paired with a
    sub-200-char response counts.
    """
    r = (response or "").strip()
    if not r:
        return True
    canned_markers = (
        "all clear -- no triggers fired",
        "all clear — no triggers fired",
        "no triggers fired, no active threats",
        "i couldn't find a match",
        "no match for your query",
        "no match found",
        "nothing to do",
        "no matching agents",
        # broader "the catalog/search didn't return anything" patterns —
        # the user complained agents return polite "I couldn't help" instead
        # of actually thinking about their prompt.
        "did not yield any results",
        "did not yield results",
        "could not find any results",
        "no results were found",
        "no relevant agents",
        "unable to find any",
        "could not locate any",
    )
    lower = r.lower()
    for m in canned_markers:
        if m in lower:
            return True
    if len(r) < 80 and elapsed_ms < 80:
        return True
    return False


async def _llm_augment(
    kernel, module_name: str, user_message: str,
    persona: str | None = None, app_state: Any | None = None,
) -> str | None:
    """Ask the live LLM to respond AS the named agent. Returns None if no
    healthy provider is available — caller keeps the original canned response.
    When *app_state* is provided, the persona is grounded in this instance's
    truthful capability context so the agent can't invent integrations."""
    router_ = getattr(kernel, "provider_router", None)
    if router_ is None:
        return None
    if persona is None:
        persona = _AGENT_PERSONAS.get(
            module_name,
            f"You are {module_name}, an agent in the ONEXUS operating system. "
            f"Respond helpfully and concisely to the user's request.",
        )
    if app_state is not None:
        persona = ground_persona(persona, app_state)
    messages = [
        {"role": "system", "content": persona},
        {"role": "user", "content": user_message},
    ]
    try:
        text = await router_.infer(messages=messages, max_tokens=800, temperature=0.6)
        return (text or "").strip() or None
    except Exception:
        return None


def _catalog_persona(entry) -> str:
    """Build an LLM system prompt from a catalog entry's metadata.

    Catalog agents are MCP-adapter subprocesses — they don't have a Python
    `handle()` method we can call. For Cortex multi-launch we instead ask
    the LLM to respond AS that agent, using its tagline and category as
    the persona. This makes the picker meaningfully include catalog agents
    without us having to spawn 590 subprocesses on every multi-dispatch.
    """
    name = entry.name or entry.slug
    tagline = entry.tagline or ""
    category = (entry.category or "").replace("-", " ")
    parts = [f"You are {name}, a specialist agent from the ONEXUS catalog."]
    if tagline:
        parts.append(f"Your role: {tagline}")
    if category:
        parts.append(f"Your domain: {category}.")
    parts.append(
        "Respond as that agent would — speak in first person about how you'd "
        "approach the user's request, what tools you'd use, and what your "
        "first step would be. If the request is outside your domain, say so "
        "briefly and suggest what kind of agent would fit better."
    )
    return " ".join(parts)


def _get_catalog(request: Request):
    """Return the agent catalog instance attached to app.state, or None."""
    return getattr(request.app.state, "agent_catalog", None)


def _get_kernel(request: Request):
    return request.app.state.kernel


@router.get("/modules")
async def list_modules(request: Request) -> dict[str, Any]:
    """The always-on cognitive roster (council, specter, oracle, …) plus the
    cortex router itself. The Aurora header reads this to show a live, truthful
    "agents on duty" count — these modules are resident the moment the kernel
    boots, independent of any workspace's declared resident_agents."""
    cortex = _get_kernel(request).cortex
    modules = sorted(cortex.list_modules())
    # "+ 1" for cortex's own routing layer, which is on duty whenever a module is.
    on_duty = (["routing"] if modules else []) + modules
    return {"modules": modules, "on_duty": on_duty, "count": len(on_duty)}


# ── Swarm templates ─────────────────────────────────────────────────────────
# Curated starting points for common swarms (VISION-AGENTIC-OS roadmap §6:
# "Templates for common swarms — research / build / monitor / negotiate").
# Each names the built-in cognitive modules that compose the swarm and a
# starter task with an editable <bracket>. The endpoint filters every roster
# down to modules that are actually registered in this kernel, so a template
# never offers an agent that can't run.
_SWARM_TEMPLATES: list[dict[str, Any]] = [
    {
        "id": "research",
        "name": "Research",
        "tagline": "Gather, weigh, and draft a recommendation",
        "tone": "ocean",
        "agents": ["oracle", "council", "specter", "legacy", "atlas"],
        "prompt": "Research <topic>: gather the best sources, weigh the evidence, "
                  "surface the strongest counter-arguments, and draft a recommendation.",
    },
    {
        "id": "build",
        "name": "Build",
        "tagline": "Plan it, build it, watch for risk",
        "tone": "emerald",
        "agents": ["council", "oracle", "autonomic", "specter", "sentry"],
        "prompt": "Plan and build <thing>: break it into concrete steps, propose an "
                  "implementation, red-team the plan, and flag anything risky.",
    },
    {
        "id": "monitor",
        "name": "Monitor",
        "tagline": "Watch for drift, anomalies, and risk",
        "tone": "teal",
        "agents": ["sentry", "sigil", "oracle", "echo"],
        "prompt": "Monitor <target>: watch for drift, anomalies, and risks, and tell "
                  "me the moment something needs my attention.",
    },
    {
        "id": "negotiate",
        "name": "Negotiate",
        "tagline": "Structure offers, counters, and trade-offs",
        "tone": "honey",
        "agents": ["herald", "council", "specter", "oracle"],
        "prompt": "Negotiate <deal>: structure the offers and counters, weigh the "
                  "trade-offs, and stress-test the other side's position.",
    },
]


@router.get("/templates")
async def swarm_templates(request: Request) -> dict[str, Any]:
    """Curated swarm templates, each filtered to modules this kernel actually
    runs. The Compose UI renders these as one-tap starting points."""
    cortex = _get_kernel(request).cortex
    registered = set(cortex._modules.keys())
    out: list[dict[str, Any]] = []
    for tpl in _SWARM_TEMPLATES:
        agents = [a for a in tpl["agents"] if a in registered]
        if not agents:
            continue
        out.append({**tpl, "agents": agents})
    return {"templates": out}


class LaunchBody(BaseModel):
    message: str = Field(..., min_length=1)
    workspace_id: str | None = None
    agents: list[str] | None = None
    top_k: int | None = Field(default=None, ge=1, le=10)


async def _run_one(
    kernel, cortex, catalog, module_name: str, message: str,
    app_state: Any | None = None,
) -> dict[str, Any]:
    """Run a single agent. Mirrors the safety steps in cortex.process()
    so multi-launch follows the same Aegis discipline as single routing.

    Three paths:
      1. Built-in module → cortex._modules.get(name).handle(message). If the
         response is canned/empty, LLM-augment with the agent's persona.
      2. Catalog agent (MCP adapter, no Python handler) → LLM-augment using
         the catalog entry's tagline/category as the persona. The MCP
         subprocess is NOT spawned here — Cortex multi-launch is the "ask
         every agent at once" surface; for actual tool invocation the user
         uses the catalog page's Launch button.
      3. Unknown slug → return a non-fatal error row.
    """
    module = cortex._modules.get(module_name)
    catalog_entry = None
    if module is None and catalog is not None:
        try:
            catalog_entry = catalog.get_agent(module_name)
        except Exception:
            catalog_entry = None

    if module is None and catalog_entry is None:
        return {
            "module": module_name,
            "success": False,
            "error": f"module {module_name!r} not registered",
            "response": "",
            "elapsed_ms": 0,
            "kind": "unknown",
        }

    # Catalog agent — LLM-driven persona response, no Aegis handle-check
    # (those gates apply to the built-in module dispatch path).
    if module is None and catalog_entry is not None:
        start = time.perf_counter()
        persona = _catalog_persona(catalog_entry)
        augmented = await _llm_augment(kernel, module_name, message, persona=persona, app_state=app_state)
        elapsed = int((time.perf_counter() - start) * 1000)
        if not augmented:
            # No LLM available — return a deterministic shape so the user
            # still sees the catalog entry's tagline as a hint.
            augmented = (
                f"[{catalog_entry.name}] {catalog_entry.tagline or 'No tagline.'}\n\n"
                f"(No LLM provider available to elaborate. Launch this agent from the "
                f"catalog page to run its tools directly.)"
            )
        cortex._chronicle.log("cortex", "multi_run", {
            "module": module_name,
            "kind": "catalog",
            "elapsed_ms": elapsed,
            "llm_augmented": True,
            "response_preview": augmented[:160],
        })
        return {
            "module": module_name,
            "success": True,
            "error": None,
            "response": augmented,
            "elapsed_ms": elapsed,
            "llm_augmented": True,
            "kind": "catalog",
        }
    # Aegis: handle capability
    try:
        cortex._aegis.check(module_name, "handle")
    except PermissionDenied:
        cortex._chronicle.log("cortex", "permission_denied", {
            "module": module_name, "via": "multi_launch",
            "message_preview": message[:100],
        })
        return {
            "module": module_name,
            "success": False,
            "error": "permission_denied",
            "response": "",
            "elapsed_ms": 0,
            "kind": "builtin",
        }
    # Aegis: network if module requires it
    if getattr(module, "requires_network", False) and not cortex._aegis.is_network_allowed(module_name):
        return {
            "module": module_name,
            "success": False,
            "error": "network_required_but_not_allowed",
            "response": "",
            "elapsed_ms": 0,
            "kind": "builtin",
        }

    context = cortex._build_context()
    start = time.perf_counter()
    llm_augmented = False
    try:
        response = await module.handle(message, context)
        elapsed = int((time.perf_counter() - start) * 1000)

        # LLM fallback: if the module returned a canned/empty response,
        # ask the live LLM to answer AS that agent. This is the difference
        # between "Oracle returned 0ms with All clear" and Oracle actually
        # analyzing the user's prompt through its persona.
        if _looks_canned(response, elapsed):
            augmented = await _llm_augment(kernel, module_name, message, app_state=app_state)
            if augmented:
                response = augmented
                llm_augmented = True
                elapsed = int((time.perf_counter() - start) * 1000)

        cortex._chronicle.log("cortex", "multi_run", {
            "module": module_name,
            "kind": "builtin",
            "elapsed_ms": elapsed,
            "llm_augmented": llm_augmented,
            "response_preview": (response or "")[:160],
        })
        return {
            "module": module_name,
            "success": True,
            "error": None,
            "response": response or "",
            "elapsed_ms": elapsed,
            "llm_augmented": llm_augmented,
            "kind": "builtin",
        }
    except Exception as exc:
        elapsed = int((time.perf_counter() - start) * 1000)
        cortex._chronicle.log("cortex", "multi_run_error", {
            "module": module_name, "error": str(exc),
        })
        cortex._aegis.record_outcome(module_name, False)
        return {
            "module": module_name,
            "success": False,
            "error": str(exc),
            "response": "",
            "elapsed_ms": elapsed,
            "kind": "builtin",
        }


def _resolve_targets(cortex, body: LaunchBody) -> list[str]:
    """Pick which agents to fan to. Honors explicit lists first, then
    classifier top-K, then single-agent fallback."""
    if body.agents:
        # Dedupe + filter to actually-registered modules. Garbage slugs
        # come back as denied/missing rows from _run_one so the user can
        # see why.
        seen: list[str] = []
        for slug in body.agents:
            slug = (slug or "").strip().lower()
            if slug and slug not in seen:
                seen.append(slug)
        return seen
    if body.top_k:
        _, scored = cortex._select_module(body.message)
        out: list[str] = []
        for s in scored:
            if s.module and s.module not in out:
                out.append(s.module)
            if len(out) >= body.top_k:
                break
        return out
    # Fallback: single agent (same path as /api/messages, just multiplexed).
    target, _ = cortex._select_module(body.message)
    return [target] if target else []


@router.post("/launch")
async def launch(body: LaunchBody, request: Request) -> dict:
    kernel = _get_kernel(request)
    cortex = kernel.cortex
    catalog = _get_catalog(request)

    targets = _resolve_targets(cortex, body)
    if not targets:
        raise HTTPException(status_code=400, detail="no agents matched and none provided")

    kernel.chronicle.log("cortex", "multi_launch_start", {
        "agents": targets,
        "workspace_id": body.workspace_id,
        "message_preview": body.message[:140],
        "mode": "explicit" if body.agents else ("top_k" if body.top_k else "single"),
    })

    # Light the live scene: store the user's prompt once, then fire a routing
    # bead to every agent in the swarm before they run.
    try:
        kernel.engram.episodic.store(f"User: {body.message}", source="user_input")
        await kernel.pulse.publish(Message(
            topic="engram.write", source="engram",
            payload={"tier": "episodic", "source": "user_input",
                     "preview": body.message.strip().replace("\n", " ")[:80]},
        ))
    except Exception:
        pass
    await asyncio.gather(*(_emit_route(kernel, slug, body.message) for slug in targets))

    runs = await asyncio.gather(*(
        _run_one(kernel, cortex, catalog, slug, body.message, app_state=request.app.state)
        for slug in targets
    ))

    # Persist each agent's reply to episodic memory + stream engram.write so the
    # memory strata and cockpit reflect the launch.
    for r in runs:
        if r.get("success") and r.get("response"):
            await _emit_run_memory(kernel, r["module"], body.message, r["response"])

    succeeded = sum(1 for r in runs if r["success"])

    kernel.chronicle.log("cortex", "multi_launch_done", {
        "agents": targets,
        "succeeded": succeeded,
        "failed": len(runs) - succeeded,
    })

    return {
        "targets": targets,
        "runs": runs,
        "succeeded": succeeded,
        "failed": len(runs) - succeeded,
    }


@router.get("/candidates")
async def candidates(
    request: Request,
    message: str = Query(..., min_length=1),
    catalog_limit: int = Query(default=8, ge=0, le=30),
) -> dict:
    """Recommended agents for a prompt — built-ins via Cortex's classifier,
    plus the top catalog (MCP-adapter) matches via keyword search. The
    launcher UI uses this to pre-suggest a smart picks set.
    """
    kernel = _get_kernel(request)
    cortex = kernel.cortex
    target, scored = cortex._select_module(message)
    top = []
    seen: set[str] = set()
    for s in scored:
        if not s.module or s.module in seen:
            continue
        seen.add(s.module)
        top.append({
            "module": s.module,
            "intent": s.name,
            "score": round(float(s.score), 3),
            "kind": "builtin",
        })
        if len(top) >= 5:
            break
    all_modules = list(cortex._modules.keys())

    # Catalog matches — tokenize the prompt and union the per-keyword search
    # results. catalog.search() does substring matching on individual fields,
    # so handing it a 60-character user prompt finds nothing. Splitting on
    # word boundaries (longer than 3 chars to skip stopwords) lets a prompt
    # like "search the web and draft spreadsheet financial models" surface
    # the matching catalog agents.
    catalog_matches: list[dict] = []
    cat = _get_catalog(request)
    if cat is not None and catalog_limit > 0:
        try:
            import re as _re
            STOP = {"the","and","for","that","this","with","from","into","what","when",
                    "your","you","want","need","like","want","make","just","also","then",
                    "very","much","more","over","onto","than","each","some","such","only",
                    "etc","help","plan","build","create","draft","work","tool"}
            words = [w.lower() for w in _re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", message)]
            keywords = [w for w in words if w not in STOP][:8]
            score_by_slug: dict[str, float] = {}
            entry_by_slug = {}
            for kw in keywords:
                for entry in cat.search(kw, limit=10):
                    score_by_slug[entry.slug] = score_by_slug.get(entry.slug, 0.0) + 1.0
                    entry_by_slug[entry.slug] = entry
            ranked = sorted(score_by_slug.items(), key=lambda kv: kv[1], reverse=True)
            for slug, _score in ranked[:catalog_limit]:
                entry = entry_by_slug[slug]
                catalog_matches.append({
                    "slug": entry.slug,
                    "name": entry.name,
                    "tagline": entry.tagline or "",
                    "category": entry.category,
                    "tags": list(entry.tags or [])[:6],
                    "runnable": bool(entry.runnable),
                    "stars": entry.stars or 0,
                    "kind": "catalog",
                })
        except Exception:
            pass

    return {
        "primary": target,
        "top": top,
        "all_modules": all_modules,
        "catalog_matches": catalog_matches,
    }


class ContinueBody(BaseModel):
    module: str = Field(..., min_length=1)
    history: list[dict] = Field(default_factory=list, description="prior turns: [{role: 'user'|'assistant', content: '...'}]")
    message: str = Field(..., min_length=1)
    workspace_id: str | None = None


_HANDOFF_INSTRUCTION = (
    "\n\nIf another ONEXUS agent would handle the user's next step better "
    "than you can, end your reply with a single line of the form "
    "[handoff: <agent-slug>] naming that agent — the user gets a one-click "
    "button to dispatch the conversation there with full history preserved. "
    "Only suggest hand-off when you are genuinely outside your domain; don't "
    "punt to another agent for things you should answer yourself."
)


def _resolve_persona(kernel, request: Request, slug: str) -> tuple[str, str]:
    """Return (persona_prompt, kind) for a given agent slug.

    Built-ins use the curated _AGENT_PERSONAS map; catalog agents derive
    persona from their catalog entry. Falls back to a generic prompt for
    anything we don't recognize. Every persona is grounded in this
    instance's truthful capability context and suffixed with the hand-off
    instruction so any agent can route the next turn elsewhere when it's
    the right call."""
    cortex = kernel.cortex
    base: str
    kind: str
    if slug in cortex._modules:
        base = _AGENT_PERSONAS.get(
            slug,
            f"You are {slug}, an agent in the ONEXUS operating system. "
            f"Respond helpfully and concisely to the user's request.",
        )
        kind = "builtin"
    else:
        cat = _get_catalog(request)
        entry = None
        if cat is not None:
            try:
                entry = cat.get_agent(slug)
            except Exception:
                entry = None
        if entry is not None:
            base = _catalog_persona(entry)
            kind = "catalog"
        else:
            base = (
                f"You are {slug}, an agent in the ONEXUS operating system. "
                f"Respond helpfully and concisely to the user's request."
            )
            kind = "unknown"
    return ground_persona(base, request.app.state) + _HANDOFF_INSTRUCTION, kind


# Pattern an agent can emit to suggest a hand-off, e.g.:
#   "[handoff: oracle] — let Oracle take it from here"
# Or naturally: "you should ask @oracle about this"
_HANDOFF_PATTERNS = (
    # Explicit marker (preferred — added to the system prompt as an option)
    (r"\[handoff:\s*([a-z0-9][a-z0-9_.-]*)\s*\]", 1.0),
    # Natural @mention
    (r"@([a-z0-9][a-z0-9_.-]{2,})", 0.7),
)


def _detect_handoff_suggestion(response: str, known_slugs: set[str]) -> str | None:
    """Find an agent slug the response suggests handing off to.

    Returns the slug only if it matches a known registered agent or catalog
    slug (so we don't surface garbage like "@username" that the LLM made up)."""
    import re as _re
    for pattern, _confidence in _HANDOFF_PATTERNS:
        for m in _re.finditer(pattern, response, _re.IGNORECASE):
            candidate = m.group(1).lower().strip()
            if candidate in known_slugs:
                return candidate
    return None


@router.post("/continue")
async def continue_thread(body: ContinueBody, request: Request) -> dict:
    """Continue an in-flight Cortex thread.

    The launcher tracks per-card history client-side and POSTs the full
    transcript here so the agent (LLM persona) sees the whole conversation
    on every turn, not just the latest message. Same persona resolution
    for built-in and catalog agents — handoff to a different agent is just
    a new POST with the next module slug; history is preserved across
    the swap.
    """
    kernel = _get_kernel(request)
    cortex = kernel.cortex

    slug = body.module.strip().lower()
    persona, kind = _resolve_persona(kernel, request, slug)

    router_ = getattr(kernel, "provider_router", None)
    if router_ is None:
        raise HTTPException(status_code=503, detail="no LLM provider available")

    # Build the message stream: persona system + clean history + user message.
    messages: list[dict] = [{"role": "system", "content": persona}]
    for turn in (body.history or [])[-20:]:  # cap to last 20 turns for safety
        role = turn.get("role")
        content = (turn.get("content") or "").strip()
        if not content:
            continue
        if role not in ("user", "assistant"):
            continue
        messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": body.message})

    start = time.perf_counter()
    try:
        text = await router_.infer(messages=messages, max_tokens=900, temperature=0.6)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"LLM error: {exc}")
    elapsed = int((time.perf_counter() - start) * 1000)
    response_text = (text or "").strip()

    # Hand-off detection — look for known slugs (built-ins + catalog) so we
    # never recommend something that can't actually be dispatched.
    cat = _get_catalog(request)
    known: set[str] = set(cortex._modules.keys())
    if cat is not None:
        try:
            known.update(e.slug for e in cat._entries.values())
        except Exception:
            pass
    handoff = _detect_handoff_suggestion(response_text, known)

    try:
        kernel.chronicle.log("cortex", "continue", {
            "module": slug,
            "kind": kind,
            "elapsed_ms": elapsed,
            "history_turns": len([m for m in messages if m["role"] != "system"]) - 1,
            "response_preview": response_text[:160],
            "suggested_handoff": handoff,
            "workspace_id": body.workspace_id,
        })
    except Exception:
        pass

    return {
        "module": slug,
        "kind": kind,
        "response": response_text,
        "elapsed_ms": elapsed,
        "suggested_handoff": handoff,
    }


@router.get("/agent-search")
async def cortex_agent_search(
    request: Request,
    q: str = Query(default="", description="prompt fragment to search the catalog"),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict:
    """Catalog search shaped for the Cortex launcher's picker.

    The launcher uses this when the user types into the agent-search box
    inside the picker, so we return enough metadata to render a chip
    (slug, name, category, tagline) without spawning anything.
    """
    cat = _get_catalog(request)
    if cat is None:
        return {"matches": [], "total": 0}
    try:
        entries = cat.search(q.strip(), limit=limit) if q.strip() else cat.list_agents()[:limit]
    except Exception:
        entries = []
    return {
        "matches": [
            {
                "slug": e.slug,
                "name": e.name,
                "tagline": e.tagline or "",
                "category": e.category,
                "runnable": bool(e.runnable),
                "stars": e.stars or 0,
                "kind": "catalog",
            }
            for e in entries
        ],
        "total": len(entries),
    }
