# N3 — Herald/Forge Negotiation + Real Federation Peer Ops + Serendipity + Aurora v3

**Date:** 2026-06-14
**Branch:** `feat/missing-minds`
**Spec:** `docs/superpowers/specs/2026-06-12-missing-minds-design.md` (Layer N3)
**Layout ref:** `docs/superpowers/plans/2026-06-09-aurora-v3-layout.md`

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship NEXUS v2's final layer. (N3.1) A structured agent-to-agent negotiation protocol — offer → counter → accept/reject → commit — where proposals/counters/commitments are typed Pulse messages, every commit is gated by `aegis.check_capability()`, and Chronicle records the full transcript. (N3.2) Promote the existing federation scaffold from message-routing to real workspace-scoped, allowlist-only, Aegis-gated peer **sync** — testable locally via a loopback peer with no real network, keeping the static "only Aegis touches the network" invariant green. (N3.3) A Serendipity anti-optimization discovery module (surfaces low-relevance/high-novelty items from Engram/Atlas on a budget, manifest-v1 ADVISOR, gated, cited, Chronicle-logged) plus the Aurora v3 responsive CSS-Grid + container-query layout and finishing the six placeholder identity glyphs.

**Architecture:** N3 lands entirely on the unchanged kernel contracts. The negotiation engine is a pure deterministic state machine in `nexus/society/herald.py` (mirroring how Chronos/Dreamweaver live in `nexus/synthesis/`), wrapped by a `HeraldModule` (manifest-v1, ADVISOR) that publishes/consumes typed Pulse messages and gates each `commit` through Aegis. Federation sync is a new `nexus/federation/sync.py` `WorkspaceSyncEngine` that diffs Atlas facts between this instance and an allowlisted peer; all peer HTTP continues to flow only through `FederationProtocol`/`PeerDiscovery` (which route through `KernelHttpClient` → `aegis.network()`), so the kernel-import invariant stays intact. A loopback transport (`LoopbackPeerClient`) lets two in-process kernels sync without sockets. Serendipity follows the Prism/Chronos module template exactly. Aurora v3 rewrites `app.css`/`index.html`/`app.js` per the referenced layout doc and finishes the glyphs in `icons.js`.

**Tech Stack:** Python 3.14, FastAPI, SQLite (via existing Engram/Chronicle/Aegis), pydantic v2 manifests, `httpx` (Aegis-only), pytest (`.venv/bin/python -m pytest`), vanilla ES-module JS + CSS for Aurora. No new dependencies.

---

## Spec deviations

1. **Federation is already substantially built.** `nexus/federation/{protocol,discovery,peer,security,models}.py` and `routes/federation.py` already do handshake / capability-exchange / message-routing / heartbeats, all routed through `KernelHttpClient` → `aegis.network()` (so the network invariant already holds). N3.2 therefore **does not re-implement transport**; it adds the missing piece the spec actually calls for — *scoped sync between instances* (workspace-scoped, allowlist-only, Aegis-gated) — as a new `WorkspaceSyncEngine` + allowlist gate + sync endpoints + kill switch, reusing the existing protocol/registry/security. Noted because the spec phrases N3.2 as "wire the existing federation config to real peer ops," which is largely done for routing; the genuinely new work is *sync*.

2. **"Herald/Forge"** — the spec names two agents but describes one protocol. We ship a single `HeraldModule` that owns the protocol and the transcript, plus a thin `Forge` helper class (in the same `society` package) that builds/validates proposal payloads. This avoids a second near-empty module while keeping both names meaningful (Herald = messenger/transcript; Forge = where commitments are forged/validated).

3. **Negotiation auto-accept kill switch.** Herald's only *automated* behavior is optional policy-driven auto-accept of a counter that strictly dominates the prior offer. That is gated behind `NEXUS_HERALD_AUTOACCEPT` (default off) + a `<data_dir>/herald-autoaccept.kill` file, mirroring the Dreamweaver convention. Manual negotiation needs no kill switch.

4. **Glyphs already partly finished.** The six named glyphs (wraith, oracle, autonomic, legacy, consciousness, sentry) may already be hand-drawn line-stroke SVGs, and sigil/atlas/prism/chronos were finished in N1/N2. The remaining placeholder is the **new** Serendipity glyph. Task 12 (a) audits each of the six for "real mark vs primitive," upgrading any still-primitive, and (b) adds distinctive `serendipity`/`herald`/`federation` glyphs, with a regression test asserting every built-in glyph is a non-trivial SVG. Don't churn already-good art.

---

## File Structure

| File | New/Edit | Purpose |
|---|---|---|
| `nexus/society/__init__.py` | New | Package for agent-society (negotiation) logic |
| `nexus/society/herald.py` | New | `NegotiationState` machine + `Forge` payload builder/validator (pure) |
| `nexus/modules/herald.py` | New | `HeraldModule` (manifest-v1 ADVISOR) — typed Pulse + Aegis-gated commit + Chronicle transcript |
| `nexus/api/routes/herald.py` | New | `/api/herald/*` — start/counter/respond/commit/transcript |
| `nexus/federation/sync.py` | New | `WorkspaceSyncEngine` + `PeerAllowlist` + `LoopbackPeerClient` |
| `nexus/api/routes/federation.py` | Edit | Add `/api/federation/sync/*` endpoints (allowlist-gated, scoped) |
| `nexus/modules/serendipity.py` | New | `SerendipityModule` (manifest-v1 ADVISOR) |
| `nexus/society/serendipity.py` | New | `SerendipityEngine` (pure novelty/relevance + budget) |
| `nexus/api/routes/serendipity.py` | New | `/api/serendipity/discover` (gated) |
| `nexus/kernel/cortex.py` | Edit | Register Herald + Serendipity in `default_builtin_registry()` |
| `nexus/api/server.py` | Edit | Include herald/serendipity routers; wire sync engine + allowlist + kill switch |
| `nexus/aurora/index.html` | Edit | Grid shell + 3 inner wrappers (v3) |
| `nexus/aurora/app.css` | Edit | Full v3 rewrite per layout doc |
| `nexus/aurora/app.js` | Edit | Emit new wrappers; Herald + federation-sync panels |
| `nexus/aurora/icons.js` | Edit | Finish/verify glyphs + add serendipity/herald/federation marks |
| `tests/society/test_herald_state.py` etc. | New | (see tasks) |

> **Note:** The plan carries complete code for the load-bearing pieces (state machine, Herald module, sync engine, Serendipity engine) and precise prose for glue + the large CSS v3 rewrite (follow the layout doc). VERIFY all kernel/Aurora API signatures against the real N1/N2-extended code before editing; adapt minimally and document deviations. NO emoji anywhere.

---

## Task 1 — Herald negotiation state machine (pure)

**Files:** `nexus/society/__init__.py`, `nexus/society/herald.py`, `tests/society/test_herald_state.py`

States: `OPEN` (offer) → `COUNTERED` → `ACCEPTED`/`REJECTED` (terminal) → `COMMITTED` (terminal, capability bound). Illegal transitions raise `IllegalTransition`. Pure data — no Pulse/Aegis/I/O.

- [ ] Write `tests/society/test_herald_state.py`:
  ```python
  """Unit tests for the Herald negotiation state machine (pure)."""
  from __future__ import annotations

  import pytest

  from nexus.society.herald import (
      Forge, IllegalTransition, NegotiationState, NegotiationStatus,
  )


  def _offer():
      return Forge.offer(
          initiator="agent-a", responder="agent-b",
          capability="engram.write.workspace", workspace_id="ws1",
          terms={"scope": "summaries", "ttl_s": 600}, value=0.4,
      )


  def test_offer_opens_negotiation():
      neg = NegotiationState.start(_offer())
      assert neg.status is NegotiationStatus.OPEN
      assert neg.capability == "engram.write.workspace"
      assert len(neg.transcript) == 1
      assert neg.transcript[0]["kind"] == "offer"


  def test_counter_moves_to_countered_and_records():
      neg = NegotiationState.start(_offer())
      neg.counter(Forge.counter(by="agent-b", terms={"ttl_s": 300}, value=0.3))
      assert neg.status is NegotiationStatus.COUNTERED
      assert neg.transcript[-1]["kind"] == "counter"
      assert neg.current_value == 0.3


  def test_accept_then_commit_is_terminal():
      neg = NegotiationState.start(_offer())
      neg.accept(by="agent-b")
      assert neg.status is NegotiationStatus.ACCEPTED
      token = neg.commit(by="agent-a")
      assert neg.status is NegotiationStatus.COMMITTED
      assert token.capability == "engram.write.workspace"
      assert token.workspace_id == "ws1"


  def test_reject_is_terminal():
      neg = NegotiationState.start(_offer())
      neg.reject(by="agent-b", reason="terms too broad")
      assert neg.status is NegotiationStatus.REJECTED
      assert neg.transcript[-1]["reason"] == "terms too broad"


  def test_cannot_commit_without_accept():
      neg = NegotiationState.start(_offer())
      with pytest.raises(IllegalTransition):
          neg.commit(by="agent-a")


  def test_cannot_act_after_terminal():
      neg = NegotiationState.start(_offer())
      neg.reject(by="agent-b", reason="no")
      with pytest.raises(IllegalTransition):
          neg.counter(Forge.counter(by="agent-b", terms={}, value=0.1))


  def test_auto_accept_only_when_counter_dominates():
      neg = NegotiationState.start(_offer())  # value 0.4
      neg.counter(Forge.counter(by="agent-b", terms={"ttl_s": 300}, value=0.3))
      assert neg.counter_dominates() is True
      neg2 = NegotiationState.start(_offer())
      neg2.counter(Forge.counter(by="agent-b", terms={"ttl_s": 1200}, value=0.9))
      assert neg2.counter_dominates() is False
  ```
- [ ] Run: `.venv/bin/python -m pytest tests/society/test_herald_state.py` — expect `ModuleNotFoundError`.
- [ ] Create `nexus/society/__init__.py` (empty) and `nexus/society/herald.py`:
  ```python
  """Herald — agent-to-agent negotiation state machine (pure, deterministic).

  The kernel-free core: an offer/counter/accept/reject/commit machine plus
  Forge, which builds and validates the typed payloads. No Pulse, no Aegis,
  no I/O here — HeraldModule wires those in.
  """
  from __future__ import annotations

  import uuid
  from dataclasses import dataclass, field
  from datetime import datetime, timezone
  from enum import Enum
  from typing import Any


  class NegotiationStatus(str, Enum):
      OPEN = "open"
      COUNTERED = "countered"
      ACCEPTED = "accepted"
      REJECTED = "rejected"
      COMMITTED = "committed"


  _TERMINAL = {NegotiationStatus.REJECTED, NegotiationStatus.COMMITTED}


  class IllegalTransition(Exception):
      """Raised when a negotiation action is invalid for the current state."""


  @dataclass(frozen=True)
  class CommitToken:
      negotiation_id: str
      capability: str
      workspace_id: str | None
      terms: dict[str, Any]
      committed_by: str


  def _now() -> str:
      return datetime.now(timezone.utc).isoformat()


  class Forge:
      """Builds and validates typed negotiation payloads."""

      @staticmethod
      def offer(*, initiator: str, responder: str, capability: str,
                workspace_id: str | None, terms: dict[str, Any],
                value: float) -> dict[str, Any]:
          if not initiator or not responder:
              raise ValueError("offer requires initiator and responder")
          if not capability:
              raise ValueError("offer requires a capability")
          if not (0.0 <= value <= 1.0):
              raise ValueError("offer value must be in [0,1]")
          return {
              "kind": "offer", "initiator": initiator, "responder": responder,
              "capability": capability, "workspace_id": workspace_id,
              "terms": dict(terms), "value": float(value), "at": _now(),
          }

      @staticmethod
      def counter(*, by: str, terms: dict[str, Any], value: float) -> dict[str, Any]:
          if not (0.0 <= value <= 1.0):
              raise ValueError("counter value must be in [0,1]")
          return {"kind": "counter", "by": by, "terms": dict(terms),
                  "value": float(value), "at": _now()}


  @dataclass
  class NegotiationState:
      negotiation_id: str
      initiator: str
      responder: str
      capability: str
      workspace_id: str | None
      status: NegotiationStatus
      current_terms: dict[str, Any]
      current_value: float
      offer_value: float
      transcript: list[dict[str, Any]] = field(default_factory=list)

      @classmethod
      def start(cls, offer: dict[str, Any]) -> "NegotiationState":
          if offer.get("kind") != "offer":
              raise ValueError("start requires an offer payload")
          neg = cls(
              negotiation_id=uuid.uuid4().hex[:12],
              initiator=offer["initiator"], responder=offer["responder"],
              capability=offer["capability"], workspace_id=offer["workspace_id"],
              status=NegotiationStatus.OPEN,
              current_terms=dict(offer["terms"]), current_value=offer["value"],
              offer_value=offer["value"],
          )
          neg.transcript.append(offer)
          return neg

      def _require(self, allowed: set[NegotiationStatus], action: str) -> None:
          if self.status in _TERMINAL:
              raise IllegalTransition(f"{action}: negotiation is terminal ({self.status.value})")
          if self.status not in allowed:
              raise IllegalTransition(f"{action}: not allowed from {self.status.value}")

      def counter(self, counter: dict[str, Any]) -> None:
          self._require({NegotiationStatus.OPEN, NegotiationStatus.COUNTERED}, "counter")
          self.current_terms = dict(counter["terms"])
          self.current_value = float(counter["value"])
          self.status = NegotiationStatus.COUNTERED
          self.transcript.append(counter)

      def accept(self, *, by: str) -> None:
          self._require({NegotiationStatus.OPEN, NegotiationStatus.COUNTERED}, "accept")
          self.status = NegotiationStatus.ACCEPTED
          self.transcript.append({"kind": "accept", "by": by, "at": _now()})

      def reject(self, *, by: str, reason: str = "") -> None:
          self._require({NegotiationStatus.OPEN, NegotiationStatus.COUNTERED}, "reject")
          self.status = NegotiationStatus.REJECTED
          self.transcript.append({"kind": "reject", "by": by, "reason": reason, "at": _now()})

      def commit(self, *, by: str) -> CommitToken:
          if self.status is not NegotiationStatus.ACCEPTED:
              raise IllegalTransition("commit: requires ACCEPTED state")
          self.status = NegotiationStatus.COMMITTED
          self.transcript.append({"kind": "commit", "by": by, "at": _now()})
          return CommitToken(
              negotiation_id=self.negotiation_id, capability=self.capability,
              workspace_id=self.workspace_id, terms=dict(self.current_terms),
              committed_by=by,
          )

      def counter_dominates(self) -> bool:
          return (self.status is NegotiationStatus.COUNTERED
                  and self.current_value <= self.offer_value)

      def to_dict(self) -> dict[str, Any]:
          return {
              "negotiation_id": self.negotiation_id, "initiator": self.initiator,
              "responder": self.responder, "capability": self.capability,
              "workspace_id": self.workspace_id, "status": self.status.value,
              "current_terms": self.current_terms, "current_value": self.current_value,
              "transcript": self.transcript,
          }
  ```
- [ ] Run → expect pass.
- [ ] Commit: `feat(society): Herald negotiation state machine and Forge payload builder`

## Task 2 — Herald module manifest (v1, ADVISOR)

**Files:** `nexus/modules/herald.py`, `tests/modules/test_herald_manifest.py`

- [ ] Write `tests/modules/test_herald_manifest.py` mirroring the N2 chronos manifest test: slug `herald`, system True, in_process, intent `NEGOTIATE`, trust floor 0.30 / ADVISOR, declares no network capability, present in `default_builtin_registry().slugs()`.
- [ ] Run → expect failure.
- [ ] Implement `HeraldModule.manifest()` (full module body in Task 3): declares `chronicle.read.workspace` + `pulse.subscribe` Routine; identity mark `builtin:herald`, gradient `["#ffd9a8", "#9c6a2a"]`. Register `HeraldModule` in `default_builtin_registry()` in `cortex.py`.
- [ ] Run → expect pass.
- [ ] Commit: `feat(herald): manifest-v1 ADVISOR module registered in builtin registry`

## Task 3 — Herald module behavior: typed Pulse, Aegis-gated commit, Chronicle transcript

**Files:** `nexus/modules/herald.py`, `tests/modules/test_herald.py`

Herald publishes typed Pulse messages on `herald.offer/counter/accept/reject/commit`. The **commit** calls `aegis.check_capability(initiator, capability, workspace_id)` against the initiator's manifest; only ALLOW binds the `CommitToken`. Every change is appended to the registry and logged to Chronicle (`herald`/`negotiation_event`); a final `herald`/`transcript` record holds the whole transcript on commit/reject.

- [ ] Write `tests/modules/test_herald.py` (use the real Aegis/Chronicle/Pulse fixtures like the N2 module tests; register an initiator manifest and grant it so its declared capability ALLOWs): offer publishes a `herald.offer` Pulse; accept→commit on a granted initiator returns `committed: true, verdict: ALLOW`; commit on an initiator whose capability is undeclared returns `committed: false, verdict: DENY`; the full transcript (offer/counter/accept/commit kinds) lands in Chronicle `herald`/`transcript`. Use proper async Pulse subscribers (`async def _capture(m): seen.append(m)`).
- [ ] Run → expect failure.
- [ ] Implement the full `nexus/modules/herald.py`:
  ```python
  # nexus/modules/herald.py
  """Herald — agent-to-agent negotiation (N3.1).

  Proposals, counters, and commitments are typed Pulse messages. Each commit
  is gated by aegis.check_capability() against the INITIATOR's manifest, and
  the full transcript is recorded in Chronicle.
  """
  from __future__ import annotations

  from typing import Any

  from nexus.modules.base import NexusModule
  from nexus.society.herald import Forge, NegotiationState, NegotiationStatus


  class HeraldModule(NexusModule):
      name = "herald"
      description = (
          "Agent-to-agent negotiation -- offer/counter/accept/reject/commit as "
          "typed Pulse messages; each commit is Aegis-gated by capability class "
          "and the full transcript is recorded in Chronicle"
      )
      version = "1.0.0"

      @classmethod
      def manifest(cls):
          from nexus.agents.manifest import Manifest
          return Manifest.model_validate({
              "manifest_version": 1, "slug": "herald", "name": "herald",
              "tagline": "Structured negotiation between agents inside Aegis boundaries.",
              "version": cls.version, "system": True,
              "publisher": {"type": "org", "handle": "nexus"},
              "category": "coordination", "license": "Apache-2.0",
              "identity": {"mark": {"kind": "builtin:herald",
                                    "gradient": ["#ffd9a8", "#9c6a2a"]}},
              "intents": [{
                  "name": "NEGOTIATE",
                  "patterns": [r"\bherald\b", r"\bnegotiat\w*\b", r"\bpropos\w*\b",
                               r"\bcounter-?offer\b", r"\bcommit\s+to\b", r"\bagreement\b"],
                  "semantic_signals": ["negotiate", "propose", "counter-offer",
                                       "reach agreement", "commit to terms",
                                       "agent negotiation"],
                  "weight": 1.0,
              }],
              "capabilities": {
                  "tools": [{"name": "handle", "class": "Routine"}],
                  "declared": {"Routine": ["chronicle.read.workspace", "pulse.subscribe"],
                               "Notable": [], "Sensitive": [], "Privileged": []},
              },
              "runtime": {"transport": "in_process"},
              "trust": {"floor": 0.30, "default_tier": "ADVISOR"},
          })

      def __init__(self):
          self._negotiations: dict[str, NegotiationState] = {}

      async def _emit(self, ctx, topic: str, payload: dict[str, Any]) -> None:
          pulse = ctx.get("pulse")
          if pulse is None:
              return
          from nexus.kernel.pulse import Message
          await pulse.publish(Message(topic=topic, source="herald", payload=payload))

      def _log(self, ctx, action: str, payload: dict[str, Any]) -> None:
          ch = ctx.get("chronicle")
          if ch is not None:
              ch.log("herald", action, payload)

      async def open_negotiation(self, ctx, *, initiator, responder, capability,
                                 workspace_id, terms, value) -> dict[str, Any]:
          offer = Forge.offer(initiator=initiator, responder=responder,
                              capability=capability, workspace_id=workspace_id,
                              terms=terms, value=value)
          neg = NegotiationState.start(offer)
          self._negotiations[neg.negotiation_id] = neg
          await self._emit(ctx, "herald.offer", {"negotiation_id": neg.negotiation_id, **offer})
          self._log(ctx, "negotiation_event", {"negotiation_id": neg.negotiation_id,
                                               "kind": "offer", "capability": capability})
          return neg.to_dict()

      async def counter(self, ctx, negotiation_id, *, by, terms, value) -> dict[str, Any]:
          neg = self._get(negotiation_id)
          neg.counter(Forge.counter(by=by, terms=terms, value=value))
          await self._emit(ctx, "herald.counter", {"negotiation_id": negotiation_id,
                                                   "by": by, "terms": terms, "value": value})
          self._log(ctx, "negotiation_event", {"negotiation_id": negotiation_id, "kind": "counter"})
          return neg.to_dict()

      async def respond(self, ctx, negotiation_id, *, action, by, reason="") -> dict[str, Any]:
          neg = self._get(negotiation_id)
          if action == "accept":
              neg.accept(by=by)
              await self._emit(ctx, "herald.accept", {"negotiation_id": negotiation_id, "by": by})
          elif action == "reject":
              neg.reject(by=by, reason=reason)
              await self._emit(ctx, "herald.reject", {"negotiation_id": negotiation_id,
                                                      "by": by, "reason": reason})
              self._log(ctx, "transcript", {"negotiation_id": negotiation_id,
                                           "status": neg.status.value, "transcript": neg.transcript})
          else:
              raise ValueError(f"unknown action {action!r}")
          self._log(ctx, "negotiation_event", {"negotiation_id": negotiation_id, "kind": action})
          return neg.to_dict()

      async def commit(self, ctx, negotiation_id, *, by) -> dict[str, Any]:
          neg = self._get(negotiation_id)
          aegis = ctx.get("aegis")
          verdict, reason = "ALLOW", "no aegis in context"
          if aegis is not None:
              decision = aegis.check_capability(neg.initiator, neg.capability, neg.workspace_id)
              verdict, reason = decision.verdict.value, decision.reason
          if verdict != "ALLOW":
              self._log(ctx, "commit_denied", {"negotiation_id": negotiation_id,
                                              "capability": neg.capability, "reason": reason})
              return {"committed": False, "verdict": verdict, "reason": reason,
                      "negotiation_id": negotiation_id}
          token = neg.commit(by=by)
          await self._emit(ctx, "herald.commit", {"negotiation_id": negotiation_id,
                                                  "capability": token.capability,
                                                  "workspace_id": token.workspace_id})
          self._log(ctx, "negotiation_event", {"negotiation_id": negotiation_id, "kind": "commit"})
          self._log(ctx, "transcript", {"negotiation_id": negotiation_id,
                                       "status": neg.status.value, "transcript": neg.transcript})
          return {"committed": True, "verdict": verdict, "negotiation_id": negotiation_id,
                  "capability": token.capability, "workspace_id": token.workspace_id,
                  "terms": token.terms}

      def get(self, negotiation_id) -> dict[str, Any] | None:
          neg = self._negotiations.get(negotiation_id)
          return neg.to_dict() if neg else None

      def list_open(self) -> list[dict[str, Any]]:
          return [n.to_dict() for n in self._negotiations.values()
                  if n.status not in (NegotiationStatus.REJECTED, NegotiationStatus.COMMITTED)]

      def _get(self, negotiation_id) -> NegotiationState:
          neg = self._negotiations.get(negotiation_id)
          if neg is None:
              raise KeyError(f"unknown negotiation {negotiation_id!r}")
          return neg

      async def handle(self, message: str, context: dict[str, Any]) -> str:
          opens = self.list_open()
          if not opens:
              return ("[Herald] No open negotiations. Start one via the Herald API "
                      "(offer -> counter -> accept/reject -> commit). Every commit is "
                      "Aegis-gated and the transcript is recorded in Chronicle.")
          lines = [f"[Herald] {len(opens)} open negotiation(s):"]
          for n in opens:
              lines.append(f"  - {n['negotiation_id']} {n['initiator']}->{n['responder']} "
                           f"[{n['status']}] cap={n['capability']} value={n['current_value']}")
          return "\n".join(lines)
  ```
- [ ] Run → expect pass.
- [ ] Commit: `feat(herald): typed-Pulse negotiation with Aegis-gated commit and Chronicle transcript`

## Task 4 — Herald API routes (observable in Aurora)

**Files:** `nexus/api/routes/herald.py`, `nexus/api/server.py`, `tests/api/test_herald_routes.py`

Persist one `HeraldModule` on `app.state`. Routes: `POST /api/herald/offer`, `POST /api/herald/{id}/counter`, `POST /api/herald/{id}/respond`, `POST /api/herald/{id}/commit`, `GET /api/herald/{id}`, `GET /api/herald`. Build the kernel context (`aegis`/`chronicle`/`pulse`) per request.

- [ ] Write `tests/api/test_herald_routes.py`: offer returns `negotiation_id` + status `open`; counter updates value; respond accept → `accepted`; commit on undeclared-capability initiator → `committed: false`; commit on granted initiator → `committed: true`; `GET /api/herald` lists open. Register the initiator manifest + grant via `client.app.state.kernel.aegis`.
- [ ] Run → expect failure.
- [ ] Implement `nexus/api/routes/herald.py` (`_herald(request)` lazy-stores the module; `_ctx(request)` returns the kernel context; Pydantic bodies `OfferBody`/`CounterBody`/`RespondBody`/`CommitBody`; `KeyError`→404, `IllegalTransition`/`ValueError`→409/400). Register in `server.py` near the prism/chronos block.
- [ ] Run → expect pass.
- [ ] Commit: `feat(api): /api/herald negotiation routes (offer/counter/respond/commit), Aurora-observable`

## Task 5 — Federation: peer allowlist + loopback client (no network)

**Files:** `nexus/federation/sync.py`, `tests/federation/test_sync.py` (allowlist + loopback portion)

`PeerAllowlist` is a workspace-scoped JSON allowlist (`federation_sync_allowlist.json`). `LoopbackPeerClient` routes an outbound sync straight into a peer's inbound handler — no httpx, no sockets — so the kernel-import invariant is untouched (this file imports neither httpx nor socket).

- [ ] Write the allowlist portion of `tests/federation/test_sync.py`: `allow`/`is_allowed` is workspace-scoped (peer-b on ws1 True, ws2 False, unknown peer False); persists across reloads; `revoke` works.
- [ ] Run → expect `ModuleNotFoundError`.
- [ ] Implement `PeerAllowlist` + `LoopbackPeerClient` in `nexus/federation/sync.py`:
  ```python
  """Federation workspace sync (N3.2).

  Workspace-scoped, allowlist-only, Aegis-gated sync of Atlas facts between
  NEXUS instances. NETWORK INVARIANT: this module imports neither httpx nor
  socket — all real peer HTTP still flows through FederationProtocol /
  PeerDiscovery, which route through KernelHttpClient -> aegis.network().
  Local tests use LoopbackPeerClient (two in-process kernels, no sockets).
  """
  from __future__ import annotations

  import json
  from collections.abc import Awaitable, Callable
  from pathlib import Path
  from typing import Any


  class PeerAllowlist:
      """Per-workspace allowlist of peer IDs permitted to sync."""

      def __init__(self, data_path: Path):
          self.data_path = Path(data_path)
          self.data_path.mkdir(parents=True, exist_ok=True)
          self._file = self.data_path / "federation_sync_allowlist.json"
          self._allow: dict[str, list[str]] = {}

      def allow(self, peer_id: str, workspace_id: str) -> None:
          self._allow.setdefault(workspace_id, [])
          if peer_id not in self._allow[workspace_id]:
              self._allow[workspace_id].append(peer_id)
          self.save()

      def revoke(self, peer_id: str, workspace_id: str) -> None:
          if workspace_id in self._allow:
              self._allow[workspace_id] = [p for p in self._allow[workspace_id] if p != peer_id]
          self.save()

      def is_allowed(self, peer_id: str, workspace_id: str) -> bool:
          return peer_id in self._allow.get(workspace_id, [])

      def workspaces_for(self, peer_id: str) -> list[str]:
          return [ws for ws, peers in self._allow.items() if peer_id in peers]

      def save(self) -> None:
          self._file.write_text(json.dumps(self._allow, indent=2))

      def load(self) -> None:
          if self._file.exists():
              try:
                  self._allow = json.loads(self._file.read_text())
              except json.JSONDecodeError:
                  self._allow = {}


  InboundHandler = Callable[[str, list[dict[str, Any]]], Awaitable[dict[str, Any]]]


  class LoopbackPeerClient:
      """Test transport: routes an outbound sync into a peer's inbound handler."""

      def __init__(self, inbound: InboundHandler):
          self._inbound = inbound

      async def push_atlas(self, workspace_id: str,
                           facts: list[dict[str, Any]]) -> dict[str, Any]:
          return await self._inbound(workspace_id, facts)
  ```
- [ ] Run → expect pass.
- [ ] Commit: `feat(federation): per-workspace peer allowlist and loopback sync transport`

## Task 6 — Federation: WorkspaceSyncEngine (Atlas-fact diff, Aegis-gated, Chronicle-logged)

**Files:** `nexus/federation/sync.py`, `tests/federation/test_sync.py` (engine portion)

`WorkspaceSyncEngine` exports the local workspace's Atlas facts, pushes them to an allowlisted peer via the injected client, and merges inbound facts via `engram.atlas.observe(...)`. Every sync passes `aegis.check_capability("federation", "federation.sync.workspace", workspace_id)`; both directions log to Chronicle (`federation`/`sync_push`, `federation`/`sync_merge`). A `sync_enabled` kill switch short-circuits.

- [ ] Write the engine portion of `tests/federation/test_sync.py` (build two engines A and B with real Aegis/Chronicle/Engram + a `federation` manifest declaring `federation.sync.workspace` Routine, granted): loopback sync from A to B when allowlisted merges facts into B's Engram and logs `sync_push`/`sync_merge`; sync blocked with `not_allowlisted` when the peer isn't allowlisted; sync blocked with `kill_switch` when `set_sync_enabled(False)`.
- [ ] Run → expect failure.
- [ ] Implement `WorkspaceSyncEngine`:
  ```python
  class WorkspaceSyncEngine:
      """Workspace-scoped, allowlist-only, Aegis-gated Atlas-fact sync."""

      CAPABILITY = "federation.sync.workspace"

      def __init__(self, *, instance_id, aegis, chronicle, allowlist, engram_for):
          self._instance_id = instance_id
          self._aegis = aegis
          self._chronicle = chronicle
          self._allowlist = allowlist
          self._engram_for = engram_for   # Callable[[workspace_id], Engram]
          self._enabled = True

      def set_sync_enabled(self, value: bool) -> None:
          self._enabled = bool(value)

      def _log(self, action, payload):
          if self._chronicle is not None:
              self._chronicle.log("federation", action, payload)

      def _export_atlas(self, workspace_id):
          eng = self._engram_for(workspace_id)
          conn = eng.atlas._conn()
          try:
              rows = conn.execute(
                  "SELECT subject, relation, object, confidence, fact_class, "
                  "source_ref FROM atlas_facts").fetchall()
          finally:
              conn.close()
          return [{"subject": r["subject"], "relation": r["relation"],
                   "object": r["object"], "confidence": float(r["confidence"]),
                   "fact_class": r["fact_class"], "source_ref": r["source_ref"]}
                  for r in rows]

      async def push_workspace(self, peer_id, workspace_id, client):
          if not self._enabled:
              self._log("sync_skipped", {"peer": peer_id, "workspace": workspace_id,
                                        "reason": "kill_switch"})
              return {"pushed": 0, "gated": True, "blocked": "kill_switch"}
          if not self._allowlist.is_allowed(peer_id, workspace_id):
              self._log("sync_denied", {"peer": peer_id, "workspace": workspace_id,
                                       "reason": "not_allowlisted"})
              return {"pushed": 0, "gated": True, "blocked": "not_allowlisted"}
          if self._aegis is not None:
              decision = self._aegis.check_capability("federation", self.CAPABILITY, workspace_id)
              if decision.verdict.value != "ALLOW":
                  self._log("sync_denied", {"peer": peer_id, "workspace": workspace_id,
                                           "reason": decision.reason})
                  return {"pushed": 0, "gated": True, "blocked": "aegis"}
          facts = self._export_atlas(workspace_id)
          ack = await client.push_atlas(workspace_id, facts)
          self._log("sync_push", {"peer": peer_id, "workspace": workspace_id,
                                 "count": len(facts), "ack": ack})
          return {"pushed": len(facts), "gated": False, "blocked": None, "ack": ack}

      async def handle_inbound_atlas(self, workspace_id, facts):
          eng = self._engram_for(workspace_id)
          merged = 0
          for f in facts:
              eng.atlas.observe(f["subject"], f["relation"], f["object"],
                                confidence=float(f.get("confidence", 0.5)),
                                fact_class=f.get("fact_class", "default"),
                                source_ref=f.get("source_ref"))
              merged += 1
          self._log("sync_merge", {"workspace": workspace_id, "merged": merged})
          return {"merged": merged}
  ```
  (Confirm `atlas.observe` accepts `fact_class` and `source_ref` kwargs against the real N1 Engram; adapt if different.)
- [ ] Run → expect pass.
- [ ] Commit: `feat(federation): workspace-scoped Aegis-gated Atlas-fact sync engine with kill switch`

## Task 7 — Federation sync API endpoints + server wiring

**Files:** `nexus/api/routes/federation.py`, `nexus/api/server.py`, `tests/api/test_federation_sync_routes.py`

Add: `POST /api/federation/sync/allow`, `DELETE /api/federation/sync/allow/{peer_id}/{workspace_id}`, `GET /api/federation/sync/allowlist`, `POST /api/federation/sync/push`, and inbound `POST /api/federation/sync/atlas`. The outbound real-network push uses the existing `FederationProtocol._http` (KernelHttpClient → aegis.network); the engine never touches the network. Wire `WorkspaceSyncEngine` + `PeerAllowlist` into the federation init block in `server.py`, plus `NEXUS_FEDERATION_SYNC` env (default on) + `<data_dir>/federation-sync.kill` kill switch.

- [ ] Write `tests/api/test_federation_sync_routes.py`: `allow` then `allowlist` returns the pair; inbound `/sync/atlas` merges facts into the local workspace Engram; `push` to a non-allowlisted peer returns blocked. Skip-if-federation-absent guard.
- [ ] Run → expect failure.
- [ ] Implement endpoints (helpers `_get_sync`/`_get_allowlist` mirroring `_get_protocol`, 503 when federation disabled). Inbound calls `engine.handle_inbound_atlas`. Outbound `/sync/push` calls a method that POSTs via `protocol._http` inside `as_agent("federation")`. Wire into `server.py` federation block per the prose in the plan reference (build `PeerAllowlist`, an `_engram_for(ws_id)` resolver, the `WorkspaceSyncEngine`, the env+file kill switch; store on `kernel.federation_sync_engine`/`kernel.federation_allowlist`; declare `federation.sync.workspace` Routine in the in-server federation manifest). NOTE: N1/N2 added lifespan wiring (Dreamweaver, emergency bypass) — preserve all of it.
- [ ] Run → expect pass.
- [ ] Commit: `feat(api): federation sync endpoints + allowlist + kill switch wired into server`

## Task 8 — Serendipity engine (pure novelty/relevance scoring + budget)

**Files:** `nexus/society/serendipity.py`, `tests/society/test_serendipity_engine.py`

Items have `relevance` (query match) and `novelty` (inverse familiarity). The engine deliberately selects high-novelty / low-relevance items on a `budget`, excluding top-relevance hits. Pure, deterministic (ties broken by id).

- [ ] Write `tests/society/test_serendipity_engine.py`: with a relevance ceiling of 0.5, `discover(budget=2)` surfaces the two highest-novelty items under the ceiling (excluding the obvious 0.95-relevance hit); respects budget; every item cites a source; empty when nothing is below the ceiling.
- [ ] Run → expect failure.
- [ ] Implement `nexus/society/serendipity.py`:
  ```python
  """Serendipity — anti-optimization discovery (N3.3, pure).

  Deliberately surfaces low-relevance / high-novelty items on a budget, so the
  system shows you what optimization would have hidden. Deterministic.
  """
  from __future__ import annotations

  from dataclasses import dataclass
  from typing import Any


  @dataclass(frozen=True)
  class Candidate:
      id: str
      text: str
      relevance: float   # [0,1] match to the query
      novelty: float     # [0,1] inverse familiarity
      source: str        # citation (atlas:<id> / engram:<id>)


  class SerendipityEngine:
      def __init__(self, *, relevance_ceiling: float = 0.5):
          self._ceiling = relevance_ceiling

      def discover(self, candidates: list[Candidate], *, budget: int) -> list[dict[str, Any]]:
          eligible = [c for c in candidates if c.relevance <= self._ceiling]
          eligible.sort(key=lambda c: (-c.novelty, c.id))
          chosen = eligible[: max(0, budget)]
          return [{"id": c.id, "text": c.text, "relevance": round(c.relevance, 4),
                   "novelty": round(c.novelty, 4), "source": c.source} for c in chosen]
  ```
- [ ] Run → expect pass.
- [ ] Commit: `feat(society): Serendipity anti-optimization discovery engine (pure)`

## Task 9 — Serendipity module manifest (v1, ADVISOR)

**Files:** `nexus/modules/serendipity.py` (manifest only), `nexus/kernel/cortex.py`, `tests/modules/test_serendipity_manifest.py`

- [ ] Write the manifest test (mirror chronos): slug `serendipity`, system True, in_process, intent `SERENDIPITY`, trust 0.30/ADVISOR, declares `engram.read.workspace` Routine, no network, in registry.
- [ ] Run → expect failure.
- [ ] Implement `SerendipityModule.manifest()` (full body in Task 10), identity `builtin:serendipity` gradient `["#ffc4f0", "#7a2a6a"]`. Register in `cortex.py`.
- [ ] Run → expect pass.
- [ ] Commit: `feat(serendipity): manifest-v1 ADVISOR module registered in builtin registry`

## Task 10 — Serendipity module behavior: gated reads, citations, Chronicle

**Files:** `nexus/modules/serendipity.py`, `tests/modules/test_serendipity.py`

Reads Atlas facts (via the workspace Engram), builds `Candidate`s (relevance from keyword overlap vs the query; novelty from low effective-confidence-rank / sparse edges / age), runs the engine on a budget, cites each `source_ref`, logs `serendipity`/`discovery`. Aegis-gated read (`check_capability("serendipity", "engram.read.workspace", ws)`).

- [ ] Write `tests/modules/test_serendipity.py` (mirror `test_prism.py`): seed Atlas facts of varying confidence; the module surfaces high-novelty/low-relevance facts (not the obvious top match), every line cites a source, `discovery` lands in Chronicle, budget cap respected; a denied read (bare Aegis, no manifest) returns blocked and reads nothing.
- [ ] Run → expect failure.
- [ ] Implement the full `SerendipityModule` (`handle` + `discover(ctx, query, budget)` helper; build candidates from `engram.atlas` rows computing `effective_confidence`; `novelty = 1 - confidence_rank_fraction`, `relevance = keyword_overlap`; `SerendipityEngine(relevance_ceiling=0.5).discover(...)`; cite + Chronicle; default budget 5).
- [ ] Run → expect pass.
- [ ] Commit: `feat(serendipity): gated anti-optimization discovery over Engram/Atlas with citations`

## Task 11 — Serendipity API route

**Files:** `nexus/api/routes/serendipity.py`, `nexus/api/server.py`, `tests/api/test_serendipity_routes.py`

`GET /api/serendipity/discover?q=...&budget=5&workspace_id=...` — gated like the Prism route; returns `{gated, query, budget, items:[{text, novelty, relevance, source}]}`; logs to Chronicle.

- [ ] Write `tests/api/test_serendipity_routes.py`: seed a workspace Engram, call the route, assert 200 + items carry `source` + Chronicle `serendipity`/`discovery` recorded.
- [ ] Run → expect failure.
- [ ] Implement the route (mirror `routes/prism.py` helpers) + register in `server.py`.
- [ ] Run → expect pass.
- [ ] Commit: `feat(api): /api/serendipity/discover gated anti-optimization route`

## Task 12 — Finish identity glyphs + Serendipity/Herald/Federation marks

**Files:** `nexus/aurora/icons.js`, `tests/aurora/test_glyphs.py`

Audit the six named glyphs (wraith, oracle, autonomic, legacy, consciousness, sentry); upgrade any bare primitive to a distinct line-stroke mark. Add `serendipity` (scattered constellation + one off-axis bright node), `herald` (pennant on a staff), `federation` (two linked nodes) glyphs + `GRADIENTS` + `BUILTIN_CAPABILITIES` entries. All `stroke="#fff"`, small viewBox, no emoji.

- [ ] Write `tests/aurora/test_glyphs.py`: every built-in slug (council, specter, autonomic, oracle, wraith, legacy, consciousness, sentry, echo, agents, sigil, atlas, prism, chronos, serendipity, herald, federation) has a glyph entry; no emoji; the three new gradients are present.
- [ ] Run → expect failure.
- [ ] Edit `icons.js`: add the three new glyph functions + gradients + capability entries; upgrade any primitive among the six. Example serendipity mark:
  ```js
  serendipity: (s = 20) => `
    <svg width="${s}" height="${s}" viewBox="0 0 22 22" fill="none" stroke="#fff" stroke-width="1.4" stroke-linecap="round">
      <circle cx="6" cy="14" r="0.9" fill="#fff" stroke="none" opacity="0.5"/>
      <circle cx="11" cy="9" r="0.9" fill="#fff" stroke="none" opacity="0.5"/>
      <circle cx="16" cy="13" r="0.9" fill="#fff" stroke="none" opacity="0.5"/>
      <path d="M6 14 11 9 16 13" opacity="0.45"/>
      <path d="M15 4l0.9 2 2 0.9-2 0.9L15 10l-0.9-2-2-0.9 2-0.9z" fill="#fff" stroke="none"/>
    </svg>`,
  ```
- [ ] Run: `.venv/bin/python -m pytest tests/aurora/test_glyphs.py tests/aurora/test_accessibility.py` — expect pass.
- [ ] Commit: `feat(aurora): serendipity/herald/federation identity glyphs and glyph regression test`

## Task 13 — Aurora v3 responsive layout (CSS Grid + container queries)

**Files:** `nexus/aurora/index.html`, `nexus/aurora/app.css`, `nexus/aurora/app.js`, `tests/aurora/test_v3_layout.py`

Implement the layout exactly per `docs/superpowers/plans/2026-06-09-aurora-v3-layout.md`. Large mechanical CSS task — the prose below is the contract; follow the layout doc for full specifics.

- **`index.html`**: replace the `position:fixed; inset:16px` shell with `#app-root` (grid, `grid-template-rows: var(--chrome-h,52px) 1fr`). Inside: `.nx-chrome` (row 1) and `.nx-body` (row 2, `display:grid; grid-template-columns: var(--side-w) minmax(0,1fr) var(--cockpit-w); min-height:0; overflow:hidden`). Each of `.nx-sidebar`/`.nx-main`/`.nx-cockpit-rail` gets an inner wrapper (`flex:1; min-height:0; overflow-y:auto`). The composer sits as a `flex:none` sibling of `.nx-main-inner`. Keep `lang="en"` and `<title>ONEXUS</title>`.
- **`app.css`** (top-down rewrite): root vars + width breakpoints (1440/1200/980; cockpit retracts at ≤980), `html,body,#app-root{height:100dvh;overflow:hidden;margin:0}`, the region-discipline block, container-query declarations on `.nx-cockpit-rail` (`container-type:inline-size; container-name:cockpit`) + the `@container cockpit (...)` rules, the visual layer (layered shadows, glass chrome, spring curve `cubic-bezier(0.32,0.72,0,1)`, deep-purple darks, mood accents). **Preserve** every selector the accessibility/zero-emoji tests and the N1/N2 kernel-viz/atlas/chronos styles depend on. Do NOT touch `tokens.css`/`mood.css` media-query blocks — accessibility tests read `prefers-reduced-motion`/`prefers-reduced-data` from tokens and `prefers-contrast` from mood; keep those exact strings present.
- **`app.js`**: update renderers to emit the new wrapper structure; add a Herald negotiations panel + a federation-sync status panel to the cockpit/overlay (subscribe to `herald.*` via the existing SSE stream; show sync push/merge counts). No emoji. PRESERVE all N1/N2 renderers (kernel viz, atlas graph, chronos timeline, morning brief).
- [ ] Write `tests/aurora/test_v3_layout.py`: app.css has `grid-template-columns`, `minmax(0`, `100dvh`, `container-type`, `@container`, breakpoints `1440px`/`1200px`/`980px`; accessibility strings preserved (`prefers-reduced-motion`/`prefers-reduced-data` in tokens.css, `prefers-contrast` in mood.css); no emoji in `/aurora`, app.css, app.js.
- [ ] Run → expect failure.
- [ ] Implement per the layout doc.
- [ ] Run: `.venv/bin/python -m pytest tests/aurora/` — expect pass (v3 + accessibility + glyphs + all N1/N2 aurora tests).
- [ ] Commit: `feat(aurora): v3 responsive CSS-Grid + container-query layout with negotiation and sync panels`

## Task 14 — Full-suite regression + acceptance invariants

- [ ] Run: `.venv/bin/python -m pytest tests/release/test_v1_acceptance.py` — expect pass (kernel-import invariant: `nexus/federation/sync.py` + new modules import no httpx/socket in the kernel dir; zero-emoji; accessibility media queries green). If acceptance asserts an exact built-in module count, bump it for herald + serendipity.
- [ ] Run the full suite: `.venv/bin/python -m pytest` — expect baseline 1212 + all new N3 tests, zero regressions. Use superpowers:systematic-debugging on any pre-existing failure.
- [ ] Confirm kill switches: `NEXUS_HERALD_AUTOACCEPT` and `NEXUS_FEDERATION_SYNC`/`federation-sync.kill` default-safe and observable via Chronicle.
- [ ] Commit: `test(n3): full-suite regression green — N3 society/federation/serendipity/aurora-v3`

---

## Self-Review — requirement → task mapping

**N3.1 Herald/Forge negotiation**
- State machine (offer→counter→accept/reject→commit), pure → Task 1.
- Proposals/counters/commitments as typed Pulse messages → Task 3.
- Each commit gated by `aegis.check_capability` → Task 3 + Task 4.
- Chronicle records full transcript → Task 3.
- Observable in Aurora → Task 4 + Task 13 panel.
- Auto-accept kill switch → Spec deviation 3 + `counter_dominates()`.

**N3.2 Federation peer operations**
- Workspace-scoped, allowlist-only, Aegis-gated sync → Tasks 5–7.
- Testable locally without network → `LoopbackPeerClient` (Tasks 5/6).
- Only Aegis touches the network; invariant green → `sync.py` imports no httpx/socket; real network stays in `FederationProtocol._http`; Task 14.
- Kill switch + observable → Task 6/7.

**N3.3 Serendipity + Aurora v3**
- Anti-optimization discovery on a budget → Task 8.
- Manifest-v1 ADVISOR, gated, cited, Chronicle-logged → Tasks 9–11.
- Aurora v3 responsive layout per the plan → Task 13.
- Finished/new glyphs, no emoji → Task 12.

**Invariants:** manifest-v1 @ ADVISOR (T2/T9); every tool call gated (T3/T6/T10); every action in Chronicle (T3/T6/T10); only Aegis touches network (Spec dev 1 + T14); kill switches + Aurora observability; zero emoji + accessibility preserved (T12/T13/T14).
