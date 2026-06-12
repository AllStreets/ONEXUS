# nexus/modules/council.py
"""
Council -- multi-perspective deliberation engine.

Absorbs: ethical_prism, forge, serendipity, prism, cipher, sandbox.

The Council is NEXUS's collective intelligence surface. It orchestrates
structured multi-round debate across modules and applies analytical LENSES
and deliberation MODES to produce synthesized recommendations with
preserved dissent.

LENSES (activated based on message content):
  - ethical    : 7-framework ethical analysis (from ethical_prism)
  - verification : trust-scored claims with conflict detection (from cipher)
  - lateral    : anti-optimization surprise scoring (from serendipity)
  - synthesis  : cross-domain tag-based connection finding (from prism)

MODES (specialized deliberation types):
  - negotiation : structured multi-round bargaining (from forge)
  - simulation  : hypothetical outcome projection (from sandbox)
"""
from __future__ import annotations

import hashlib
import re
import uuid
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from nexus.modules.base import NexusModule
from nexus.kernel.pulse import Message


# ---------------------------------------------------------------------------
# Deliberation roles for module participants
# ---------------------------------------------------------------------------

_DELIBERATION_ROLES: dict[str, dict[str, Any]] = {
    "specter": {
        "role": "adversarial",
        "instruction": "Find weaknesses, hidden assumptions, and failure modes.",
        "triggers": ["decision", "should i", "plan", "strategy", "risk"],
    },
    "oracle": {
        "role": "analytical",
        "instruction": "Give a clear first-read analysis and a concrete recommendation.",
        "triggers": ["what", "how", "best", "use case", "analyze", "explain", "compare"],
    },
    "legacy": {
        "role": "historical",
        "instruction": "Recall relevant prior context, precedent, and what was decided before.",
        "triggers": ["before", "history", "remember", "past", "precedent", "again"],
    },
    "sentry": {
        "role": "risk",
        "instruction": "Flag safety, trust, and risk concerns in the proposal.",
        "triggers": ["risk", "safe", "trust", "danger", "secure", "permission"],
    },
    "echo": {
        "role": "reflective",
        "instruction": "Mirror and sharpen the core intent; surface what's really being asked.",
        "triggers": ["mean", "intent", "really", "clarify", "goal"],
    },
    "atlas": {
        "role": "factual",
        "instruction": "Provide relevant facts and knowledge context.",
        "triggers": ["fact", "know", "data", "evidence", "history"],
    },
}

_DEFAULT_CONFIG = {
    "max_rounds": 3,
    "min_modules": 2,
    "max_modules": 5,
    "always_include": ["specter"],
    "timeout_per_round_seconds": 30,
}


# ---------------------------------------------------------------------------
# Ethical lens -- 7 frameworks (absorbed from ethical_prism)
# ---------------------------------------------------------------------------

ETHICAL_FRAMEWORKS = [
    {
        "name": "Utilitarian",
        "prompt": "Analyze this decision from a UTILITARIAN perspective. Focus on consequences: what produces the greatest good for the greatest number? Consider all stakeholders and weigh outcomes.",
    },
    {
        "name": "Deontological",
        "prompt": "Analyze this decision from a DEONTOLOGICAL (duty-based) perspective. Is the action itself right or wrong, regardless of consequences? What rules or duties apply?",
    },
    {
        "name": "Virtue Ethics",
        "prompt": "Analyze this decision from a VIRTUE ETHICS perspective. What would a person of good character do? Which virtues are at stake?",
    },
    {
        "name": "Care Ethics",
        "prompt": "Analyze this decision from a CARE ETHICS perspective. Who is affected and what relationships are at stake? Who is vulnerable?",
    },
    {
        "name": "Contractualist",
        "prompt": "Analyze this decision from a CONTRACTUALIST perspective. Could all affected parties reasonably accept this action? Is it fair?",
    },
    {
        "name": "Rights-Based",
        "prompt": "Analyze this decision from a RIGHTS-BASED perspective. Does this violate anyone's fundamental rights -- autonomy, privacy, dignity, freedom, property?",
    },
    {
        "name": "Pragmatic Ethics",
        "prompt": "Analyze this decision from a PRAGMATIC ETHICS perspective. What actually works in practice given real-world constraints?",
    },
]

_ETHICAL_SYNTHESIS_PROMPT = """You are an ethical synthesis engine. You have received analyses of a decision from 7 ethical frameworks. Synthesize them:

Decision: {decision}

Framework analyses:
{analyses}

Provide:
1. CONSENSUS: Where do most frameworks agree?
2. TENSIONS: Where do frameworks conflict?
3. DISSENT: Which framework(s) dissent from the majority, and why?
4. KEY QUESTION: What is the single most important ethical question this decision raises?

Do NOT recommend an action. Present the ethical landscape and let the human decide."""

_ETHICAL_KEYWORDS = [
    "ethical", "moral", "right", "wrong", "fair", "unfair", "justice",
    "rights", "duty", "harm", "consent", "privacy", "autonomy",
    "vulnerable", "exploit", "discriminat",
]


# ---------------------------------------------------------------------------
# Verification lens -- trust-scored claims + conflict detection (from cipher)
# ---------------------------------------------------------------------------

_DEFAULT_UNKNOWN_TRUST = 0.15


@dataclass
class SourceProfile:
    name: str
    base_trust: float
    category: str


@dataclass
class Claim:
    claim_id: str
    value: str
    source: str
    trust: float


# ---------------------------------------------------------------------------
# Lateral lens -- surprise scoring (from serendipity)
# ---------------------------------------------------------------------------

@dataclass
class KnowledgeEntry:
    domain: str
    content: str
    tags: list[str]


@dataclass
class SurprisingConnection:
    source_domain: str
    content: str
    shared_concepts: list[str]
    surprise_score: float
    explanation: str


def _extract_terms(text: str) -> set[str]:
    return set(re.findall(r'\b[a-z]{3,}\b', text.lower()))


# ---------------------------------------------------------------------------
# Synthesis lens -- cross-domain tag connections (from prism)
# ---------------------------------------------------------------------------

@dataclass
class Observation:
    domain: str
    content: str
    tags: list[str]


@dataclass
class Insight:
    summary: str
    domains: list[str]
    tags: list[str]
    observations: list[Observation]
    connection_strength: float


# ---------------------------------------------------------------------------
# Negotiation mode (from forge)
# ---------------------------------------------------------------------------

@dataclass
class NegotiationConfig:
    domain: str
    floor: float
    ceiling: float
    target: float
    max_rounds: int
    concession_limit: float


@dataclass
class Offer:
    round_num: int
    amount: float
    from_party: str
    timestamp: str = ""


@dataclass
class NegotiationState:
    id: str
    config: NegotiationConfig
    status: str  # active, accepted, escalated, rejected
    current_round: int = 0
    offers: list[Offer] = field(default_factory=list)
    our_last: float = 0.0


# ---------------------------------------------------------------------------
# Simulation mode prompt (from sandbox)
# ---------------------------------------------------------------------------

_SIMULATION_PROMPT = """You are a scenario simulator. Given the proposed action and historical context, project the likely outcome:

Proposed action: {action}

Historical context (similar past events):
{context_data}

Provide:
1. Most likely outcome (with confidence %)
2. Best case scenario
3. Worst case scenario
4. Key risks or uncertainties
5. Recommendation: proceed, modify, or abandon

This is a simulation only -- no real actions will be taken."""


# ---------------------------------------------------------------------------
# Deliberation result
# ---------------------------------------------------------------------------

@dataclass
class DeliberationResult:
    question: str
    recommendation: str
    confidence: float
    consensus_view: str
    dissenting_views: list[str]
    key_uncertainties: list[str]
    participants: list[str]
    rounds: int
    lenses_applied: list[str] = field(default_factory=list)
    mode: str = "standard"
    transcript: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Negotiation mode keywords
# ---------------------------------------------------------------------------

_NEGOTIATION_KEYWORDS = ["negotiate", "offer", "deal", "bargain", "counter"]
_SIMULATION_KEYWORDS = ["simulate", "what if", "hypothetical", "scenario", "project outcome"]


# ===========================================================================
# Council Module
# ===========================================================================

class CouncilModule(NexusModule):
    name = "council"
    description = (
        "Multi-perspective deliberation engine -- structured debate, "
        "ethical/verification/lateral/synthesis lenses, negotiation and simulation modes"
    )
    version = "1.0.0"

    @classmethod
    def manifest(cls):
        from nexus.agents.manifest import Manifest
        return Manifest.model_validate({
            "manifest_version": 1,
            "slug": "council",
            "name": "council",
            "tagline": "Four-lens deliberation: ethical, verification, lateral, synthesis.",
            "version": cls.version,
            "system": True,
            "publisher": {"type": "org", "handle": "nexus", "url": "https://github.com/AllStreets/ONEXUS"},
            "category": "deliberation",
            "license": "Apache-2.0",
            "identity": {"mark": {"kind": "builtin:council",
                                  "gradient": ["#ffd2a0", "#c47a32"]}},
            "intents": [{
                "name": "DELIBERATE",
                "patterns": [
                    r"\bshould\s+i\b", r"\bpros\s+and\s+cons\b", r"\bweigh\b", r"\btrade-?off\b",
                    r"\bdeliberat\w*\b", r"\bnegotiat\w*\b", r"\bethic(al|s)?\b", r"\bmoral(ly)?\b",
                    r"\bright\s+thing\b", r"\bdecide\b", r"\bdecision\b", r"\bcouncil\b",
                    r"\bwhat\s+if\b.*\bvs\b", r"\badvise\b", r"\bsimulat\w*\b",
                    r"\bperspective\b", r"\bdebate\b", r"\bconsider\b",
                ],
                "semantic_signals": [
                    "should i", "pros and cons", "what if", "weigh options", "ethical question",
                    "negotiate", "decision", "deliberate", "multiple perspectives", "trade-off",
                    "think through", "advise me", "help me decide", "is it right to",
                    "simulation", "synthesis", "verification", "lateral thinking",
                ],
                "weight": 1.0,
            }],
            "capabilities": {
                "tools": [{"name": "handle", "class": "Routine"}],
                "declared": {
                    "Routine": ["engram.read.workspace"],
                    "Notable": [],
                    "Sensitive": [],
                    "Privileged": [],
                },
            },
            "runtime": {"transport": "in_process"},
            "trust": {"floor": 0.50, "default_tier": "MONITOR"},
        })

    def __init__(self, config: dict[str, Any] | None = None):
        self._config = {**_DEFAULT_CONFIG, **(config or {})}
        self._modules: dict[str, NexusModule] = {}

        # Verification lens state (from cipher)
        self._sources: dict[str, SourceProfile] = {}
        self._claims: dict[str, list[Claim]] = {}
        self._claim_seq = 0

        # Lateral lens state (from serendipity)
        self._focus_areas: list[str] = []
        self._knowledge: list[KnowledgeEntry] = []

        # Synthesis lens state (from prism)
        self._observations: list[Observation] = []

        # Negotiation mode state (from forge)
        self._negotiations: dict[str, NegotiationState] = {}

        # Pulse subscription
        self._sub_id: str | None = None

    # -------------------------------------------------------------------
    # Lifecycle -- Pulse subscription (absorbs cipher/prism/serendipity)
    # -------------------------------------------------------------------

    async def on_load(self, context: dict[str, Any] | None = None) -> None:
        if context:
            # Get access to sibling modules for deliberation
            cortex = context.get("cortex")
            if cortex:
                self._modules = {
                    name: mod for name, mod in cortex._modules.items()
                    if name != self.name
                }
            if "pulse" in context:
                self._sub_id = context["pulse"].subscribe(
                    "cortex.response", self._on_response
                )

    async def on_unload(self, context: dict[str, Any] | None = None) -> None:
        if self._sub_id and context and "pulse" in context:
            context["pulse"].unsubscribe(self._sub_id)
            self._sub_id = None

    async def _on_response(self, msg: Message) -> None:
        """Unified Pulse handler -- feeds all data-collection lenses."""
        payload = msg.payload
        module = payload.get("module", "unknown")
        if module == self.name:
            return
        message = payload.get("message", "")
        response = payload.get("response", "")

        # -- Verification lens: auto-register sources, record claims --
        if module not in self._sources:
            self.register_source(SourceProfile(
                name=module, base_trust=0.5, category="module"
            ))
        self._claim_seq += 1
        claim_id = f"auto_{module}_{self._claim_seq}"
        trust = self._sources[module].base_trust
        self.record_claim(claim_id, response[:200], module, trust)

        # -- Lateral lens: record focus + knowledge --
        self._record_focus(message)
        tags = list(_extract_terms(response))[:10]
        self._add_knowledge(domain=module, content=response[:200], tags=tags)

        # -- Synthesis lens: record observations --
        obs_tags = list(set(re.findall(r'\b[a-z]{4,}\b', message.lower())))[:10]
        self._add_observation(domain=module, content=response[:200], tags=obs_tags)

    # -------------------------------------------------------------------
    # Module registry
    # -------------------------------------------------------------------

    def set_modules(self, modules: dict[str, NexusModule]) -> None:
        self._modules = modules

    # ===================================================================
    # LENS: Ethical (from ethical_prism)
    # ===================================================================

    def _detect_ethical_stakes(self, text: str) -> bool:
        text_lower = text.lower()
        return sum(1 for kw in _ETHICAL_KEYWORDS if kw in text_lower) >= 2

    async def _apply_ethical_lens(
        self, question: str, context: dict[str, Any]
    ) -> dict[str, Any]:
        """Run question through 7 ethical frameworks (requires LLM)."""
        llm = context.get("llm")
        if llm is None:
            return {
                "lens": "ethical",
                "result": "Ethical lens requires LLM -- skipped.",
                "frameworks": [],
            }

        analyses: list[str] = []
        for framework in ETHICAL_FRAMEWORKS:
            prompt = f"{framework['prompt']}\n\nDecision: {question}"
            try:
                result = await llm(prompt)
            except Exception:
                result = f"[{framework['name']} analysis unavailable]"
            analyses.append(f"**{framework['name']}:**\n{result}")

        all_analyses = "\n\n".join(analyses)
        synthesis_prompt = _ETHICAL_SYNTHESIS_PROMPT.format(
            decision=question, analyses=all_analyses
        )
        try:
            synthesis = await llm(synthesis_prompt)
        except Exception:
            synthesis = "Ethical synthesis unavailable."

        return {
            "lens": "ethical",
            "result": synthesis,
            "frameworks": [f["name"] for f in ETHICAL_FRAMEWORKS],
            "full_analyses": all_analyses,
        }

    # ===================================================================
    # LENS: Verification (from cipher)
    # ===================================================================

    def register_source(self, profile: SourceProfile) -> None:
        self._sources[profile.name] = profile

    def list_sources(self) -> list[SourceProfile]:
        return list(self._sources.values())

    def score_information(self, information: str, source: str) -> dict[str, Any]:
        profile = self._sources.get(source)
        trust = profile.base_trust if profile else _DEFAULT_UNKNOWN_TRUST
        return {
            "information": information,
            "source": source,
            "trust_score": trust,
            "category": profile.category if profile else "unknown",
        }

    def record_claim(self, claim_id: str, value: str, source: str, trust: float) -> None:
        claim = Claim(claim_id=claim_id, value=value, source=source, trust=trust)
        self._claims.setdefault(claim_id, []).append(claim)

    def get_conflicts(self) -> list[dict[str, Any]]:
        """Find claims where different sources report different values."""
        conflicts = []
        for claim_id, claims in self._claims.items():
            values = {c.value for c in claims}
            if len(values) > 1:
                conflicts.append({
                    "claim_id": claim_id,
                    "positions": [
                        {"value": c.value, "source": c.source, "trust": c.trust}
                        for c in sorted(claims, key=lambda x: x.trust, reverse=True)
                    ],
                })
        return conflicts

    def get_provenance(self, claim_id: str) -> list[dict[str, Any]]:
        claims = self._claims.get(claim_id, [])
        return [
            {"source": c.source, "value": c.value, "trust": c.trust}
            for c in sorted(claims, key=lambda x: x.trust, reverse=True)
        ]

    def _apply_verification_lens(self) -> dict[str, Any]:
        """Algorithmic conflict detection across all recorded claims."""
        conflicts = self.get_conflicts()
        source_summary = {
            s.name: {"trust": s.base_trust, "category": s.category}
            for s in self._sources.values()
        }
        return {
            "lens": "verification",
            "conflicts": conflicts,
            "conflict_count": len(conflicts),
            "sources_tracked": len(self._sources),
            "source_summary": source_summary,
            "claims_recorded": sum(len(v) for v in self._claims.values()),
        }

    # ===================================================================
    # LENS: Lateral / Surprise (from serendipity)
    # ===================================================================

    def _record_focus(self, area: str) -> None:
        self._focus_areas.append(area)

    def _add_knowledge(self, domain: str, content: str, tags: list[str]) -> None:
        self._knowledge.append(KnowledgeEntry(domain=domain, content=content, tags=tags))

    def find_surprising_connections(self) -> list[SurprisingConnection]:
        """Inverted relevance scoring -- rewards cross-domain surprise."""
        if not self._focus_areas or not self._knowledge:
            return []

        focus_terms: set[str] = set()
        for area in self._focus_areas:
            focus_terms.update(_extract_terms(area))

        connections: list[SurprisingConnection] = []
        for entry in self._knowledge:
            entry_terms = set(t.lower() for t in entry.tags) | _extract_terms(entry.content)
            shared = focus_terms & entry_terms
            if not shared:
                continue

            # Domain distance: same domain = 0 surprise, distant domain = high surprise
            focus_domains = [_extract_terms(a) for a in self._focus_areas]
            domain_terms = _extract_terms(entry.domain)
            domain_overlap = sum(1 for fd in focus_domains for t in domain_terms if t in fd)

            concept_overlap = len(shared) / max(len(focus_terms | entry_terms), 1)
            domain_distance = 1.0 / (1.0 + domain_overlap)
            surprise = round(concept_overlap * domain_distance, 3)

            if surprise > 0:
                connections.append(SurprisingConnection(
                    source_domain=entry.domain,
                    content=entry.content,
                    shared_concepts=sorted(shared),
                    surprise_score=surprise,
                    explanation=f"Connects {entry.domain} to your focus via: {', '.join(sorted(shared))}",
                ))

        connections.sort(key=lambda c: c.surprise_score, reverse=True)
        return connections

    def _apply_lateral_lens(self) -> dict[str, Any]:
        """Algorithmic surprise-based connection finding."""
        connections = self.find_surprising_connections()
        return {
            "lens": "lateral",
            "connections": [
                {
                    "domain": c.source_domain,
                    "surprise": c.surprise_score,
                    "shared_concepts": c.shared_concepts,
                    "explanation": c.explanation,
                }
                for c in connections[:5]
            ],
            "focus_areas_tracked": len(self._focus_areas),
            "knowledge_entries": len(self._knowledge),
        }

    # ===================================================================
    # LENS: Synthesis (from prism)
    # ===================================================================

    def _add_observation(self, domain: str, content: str, tags: list[str]) -> None:
        self._observations.append(Observation(domain=domain, content=content, tags=tags))

    def synthesize_observations(self) -> list[Insight]:
        """Find cross-domain connections through shared tags."""
        if len(self._observations) < 2:
            return []

        tag_index: dict[str, list[int]] = {}
        for i, obs in enumerate(self._observations):
            for tag in obs.tags:
                tag_index.setdefault(tag.lower(), []).append(i)

        seen_groups: set[frozenset[int]] = set()
        insights: list[Insight] = []

        for tag, indices in tag_index.items():
            if len(indices) < 2:
                continue
            domains = {self._observations[i].domain for i in indices}
            if len(domains) < 2:
                continue

            group_key = frozenset(indices)
            if group_key in seen_groups:
                continue
            seen_groups.add(group_key)

            connected_obs = [self._observations[i] for i in indices]
            shared_tags = set.intersection(*(set(o.tags) for o in connected_obs))
            all_tags: set[str] = set()
            for o in connected_obs:
                all_tags.update(o.tags)

            strength = len(shared_tags) / len(all_tags) if all_tags else 0.0

            summary_parts = [f"[{o.domain}] {o.content}" for o in connected_obs]
            summary = "Connection found: " + " + ".join(summary_parts)

            insights.append(Insight(
                summary=summary,
                domains=sorted(domains),
                tags=sorted(shared_tags),
                observations=connected_obs,
                connection_strength=round(strength, 3),
            ))

        insights.sort(key=lambda x: x.connection_strength, reverse=True)
        return insights

    def _apply_synthesis_lens(self) -> dict[str, Any]:
        """Algorithmic cross-domain synthesis."""
        insights = self.synthesize_observations()
        return {
            "lens": "synthesis",
            "insights": [
                {
                    "summary": ins.summary[:200],
                    "domains": ins.domains,
                    "shared_tags": ins.tags,
                    "strength": ins.connection_strength,
                }
                for ins in insights[:5]
            ],
            "observations_tracked": len(self._observations),
        }

    # ===================================================================
    # MODE: Negotiation (from forge)
    # ===================================================================

    def create_negotiation(self, config: NegotiationConfig) -> str:
        neg_id = uuid.uuid4().hex[:8]
        state = NegotiationState(id=neg_id, config=config, status="active")
        self._negotiations[neg_id] = state
        return neg_id

    def get_negotiation_state(self, neg_id: str) -> NegotiationState:
        return self._negotiations[neg_id]

    def make_offer(self, neg_id: str) -> Offer:
        state = self._negotiations[neg_id]
        cfg = state.config
        state.current_round += 1

        if state.current_round == 1:
            amount = cfg.ceiling
        else:
            concession = (cfg.ceiling - cfg.target) * cfg.concession_limit * state.current_round
            amount = max(cfg.target, cfg.ceiling - concession)

        offer = Offer(round_num=state.current_round, amount=round(amount, 2), from_party="nexus")
        state.offers.append(offer)
        state.our_last = amount
        return offer

    def receive_counter(self, neg_id: str, amount: float) -> str:
        state = self._negotiations[neg_id]
        cfg = state.config

        offer = Offer(round_num=state.current_round, amount=amount, from_party="counterparty")
        state.offers.append(offer)

        if amount < cfg.floor:
            state.status = "escalated"
            return "escalate"
        if amount >= cfg.target:
            state.status = "accepted"
            return "accept"
        if state.current_round >= cfg.max_rounds:
            state.status = "escalated"
            return "escalate"
        return "counter"

    def get_negotiation_history(self, neg_id: str) -> list[Offer]:
        return self._negotiations[neg_id].offers

    def _detect_negotiation_mode(self, text: str) -> bool:
        text_lower = text.lower()
        return sum(1 for kw in _NEGOTIATION_KEYWORDS if kw in text_lower) >= 1

    async def _handle_negotiation(self, message: str, context: dict[str, Any]) -> str:
        """Handle negotiation-mode deliberation."""
        lower = message.lower()

        if "start" in lower or "create" in lower or "begin" in lower:
            nums = re.findall(r'\$?([\d,]+)', message)
            if len(nums) >= 2:
                floor_val = float(nums[0].replace(",", ""))
                ceiling_val = float(nums[1].replace(",", ""))
                target_val = (floor_val + ceiling_val) / 2
                config = NegotiationConfig(
                    domain="custom",
                    floor=floor_val,
                    ceiling=ceiling_val,
                    target=target_val,
                    max_rounds=5,
                    concession_limit=0.2,
                )
                neg_id = self.create_negotiation(config)
                offer = self.make_offer(neg_id)
                return (
                    f"[Council/Negotiation] Negotiation {neg_id} started.\n"
                    f"  Range: ${floor_val:.0f} - ${ceiling_val:.0f} (target: ${target_val:.0f})\n"
                    f"  Opening offer: ${offer.amount:.0f}"
                )

        if self._negotiations:
            lines = [f"[Council/Negotiation] {len(self._negotiations)} negotiation(s):"]
            for state in self._negotiations.values():
                lines.append(
                    f"  [{state.id}] {state.config.domain} -- {state.status} "
                    f"(round {state.current_round}/{state.config.max_rounds})"
                )
            return "\n".join(lines)

        return "[Council/Negotiation] No active negotiations. Say 'start negotiation for $X-$Y' to begin."

    # ===================================================================
    # MODE: Simulation (from sandbox)
    # ===================================================================

    def _detect_simulation_mode(self, text: str) -> bool:
        text_lower = text.lower()
        return any(kw in text_lower for kw in _SIMULATION_KEYWORDS)

    async def _handle_simulation(self, message: str, context: dict[str, Any]) -> str:
        """Hypothetical outcome projection -- no real state changes."""
        engram = context.get("engram")
        llm = context.get("llm")
        chronicle = context.get("chronicle")
        pulse = context.get("pulse")

        memories = []
        if engram:
            memories = engram.episodic.recall(message, limit=20)
        context_text = (
            "\n".join(f"- {m['content']}" for m in memories)
            if memories
            else "No relevant historical data."
        )

        if llm is None:
            return "[Council/Simulation] Simulation mode requires LLM -- unavailable."

        prompt = _SIMULATION_PROMPT.format(action=message, context_data=context_text)
        try:
            simulation = await llm(prompt)
        except Exception:
            return "[Council/Simulation] Simulation failed."

        if chronicle:
            chronicle.log("council", "simulation", {
                "action": message[:200],
                "result_preview": simulation[:300],
            })

        if pulse:
            await pulse.publish(Message(
                topic="council.simulation",
                source="council",
                payload={"text": simulation[:500], "action": message[:200]},
            ))

        return f"[Council/Simulation] (no real actions taken):\n\n{simulation}"

    # ===================================================================
    # Lens activation logic
    # ===================================================================

    def _select_lenses(self, question: str) -> list[str]:
        """Determine which lenses to activate based on message content."""
        lenses: list[str] = []
        if self._detect_ethical_stakes(question):
            lenses.append("ethical")
        if self.get_conflicts():
            lenses.append("verification")
        if self._focus_areas and self._knowledge:
            lenses.append("lateral")
        if len(self._observations) >= 2:
            lenses.append("synthesis")
        return lenses

    # ===================================================================
    # Core deliberation (original Council logic, enhanced)
    # ===================================================================

    def select_participants(self, question: str) -> list[str]:
        question_lower = question.lower()
        # Score over EVERY loaded sibling module — not just those with a
        # predefined role. Previously only the modules listed in
        # _DELIBERATION_ROLES were eligible (specter + atlas), and atlas often
        # isn't even loaded, so deliberations collapsed to a single
        # participant. Modules without a defined role still join with the
        # default role/instruction (see the deliberation loop).
        candidates = set(self._modules) | set(_DELIBERATION_ROLES)
        scores: list[tuple[str, int]] = []
        for mod_name in candidates:
            triggers = _DELIBERATION_ROLES.get(mod_name, {}).get("triggers", [])
            score = sum(1 for t in triggers if t in question_lower)
            scores.append((mod_name, score))
        # Loaded modules outrank unloaded role placeholders at equal score —
        # otherwise an unloaded role (atlas, usually) can claim a slot and
        # then be dropped by the availability filter, stranding the
        # deliberation below min_modules again. Name is the final key so the
        # ordering is deterministic.
        scores.sort(key=lambda x: (x[1], x[0] in self._modules, x[0]), reverse=True)

        selected: list[str] = []
        for name in self._config["always_include"]:
            if name not in selected:
                selected.append(name)

        for mod_name, score in scores:
            if mod_name in selected:
                continue
            if score > 0 or len(selected) < self._config["min_modules"]:
                selected.append(mod_name)
            if len(selected) >= self._config["max_modules"]:
                break

        while len(selected) < self._config["min_modules"]:
            for mod_name, _ in scores:
                if mod_name not in selected:
                    selected.append(mod_name)
                    break
            else:
                break
            if len(selected) >= self._config["min_modules"]:
                break

        return selected

    async def deliberate(
        self,
        question: str,
        context: dict[str, Any],
        participants: list[str] | None = None,
    ) -> DeliberationResult:
        # Refresh the sibling-module set from cortex. on_load may have run
        # before the other modules finished registering (load order), leaving
        # self._modules sparse — which used to strand deliberations at a single
        # participant. Re-snapshot the live registry here.
        cortex = context.get("cortex") if context else None
        if cortex is not None and getattr(cortex, "_modules", None):
            self._modules = {
                name: mod for name, mod in cortex._modules.items() if name != self.name
            }

        if participants is None:
            participants = self.select_participants(question)

        available = [p for p in participants if p in self._modules]
        if not available:
            return DeliberationResult(
                question=question,
                recommendation="No modules available for deliberation.",
                confidence=0.0,
                consensus_view="",
                dissenting_views=[],
                key_uncertainties=["No modules participated."],
                participants=[],
                rounds=0,
                transcript=[],
            )

        # --- Apply lenses ---
        active_lenses = self._select_lenses(question)
        lens_results: dict[str, dict[str, Any]] = {}

        for lens_name in active_lenses:
            if lens_name == "ethical":
                lens_results["ethical"] = await self._apply_ethical_lens(question, context)
            elif lens_name == "verification":
                lens_results["verification"] = self._apply_verification_lens()
            elif lens_name == "lateral":
                lens_results["lateral"] = self._apply_lateral_lens()
            elif lens_name == "synthesis":
                lens_results["synthesis"] = self._apply_synthesis_lens()

        # --- Multi-round debate ---
        transcript: list[dict[str, Any]] = []
        prior_responses: dict[str, str] = {}
        max_rounds = self._config["max_rounds"]

        for round_num in range(1, max_rounds + 1):
            round_record: dict[str, Any] = {"round": round_num, "responses": {}}
            for mod_name in available:
                role_info = _DELIBERATION_ROLES.get(mod_name, {})
                delib_context = {
                    **context,
                    "mode": "council_deliberation",
                    "round": round_num,
                    "role": role_info.get("role", "general"),
                    "instruction": role_info.get("instruction", "Provide your perspective."),
                    "question": question,
                    "prior_responses": dict(prior_responses) if round_num > 1 else {},
                    "lens_results": lens_results,
                }
                try:
                    response = await self._modules[mod_name].handle(question, delib_context)
                except Exception as exc:
                    response = f"[Error from {mod_name}: {exc}]"
                round_record["responses"][mod_name] = response
                prior_responses[mod_name] = response

            transcript.append(round_record)

            pulse = context.get("pulse")
            if pulse:
                await pulse.publish(Message(
                    topic="council.round.complete",
                    source="council",
                    payload={"round": round_num, "participants": available},
                ))

        result = await self._synthesize(
            question, available, transcript, context, lens_results, active_lenses
        )

        chronicle = context.get("chronicle")
        if chronicle:
            chronicle.log("council", "deliberation.complete", {
                "question": question[:200],
                "participants": result.participants,
                "confidence": result.confidence,
                "rounds": result.rounds,
                "lenses": active_lenses,
                "mode": result.mode,
            })

        engram = context.get("engram")
        if engram:
            engram.episodic.store(
                f"Council deliberation: {question[:100]} -> {result.recommendation[:200]}",
                source="council",
            )

        return result

    def _response_agreement_score(self, responses: dict[str, str]) -> float:
        """
        Rough proxy for agreement: mean pairwise Jaccard similarity on word sets.
        Returns 0.0 (full disagreement) to 1.0 (identical).
        """
        texts = list(responses.values())
        if len(texts) < 2:
            return 1.0
        stopwords = {"the", "a", "an", "is", "it", "to", "of", "and", "or", "in", "that", "this"}
        word_sets = [set(t.lower().split()) - stopwords for t in texts]
        pairs = 0
        total_sim = 0.0
        for i in range(len(word_sets)):
            for j in range(i + 1, len(word_sets)):
                a, b = word_sets[i], word_sets[j]
                union = a | b
                if union:
                    total_sim += len(a & b) / len(union)
                pairs += 1
        return total_sim / pairs if pairs else 1.0

    async def _synthesize(
        self,
        question: str,
        participants: list[str],
        transcript: list[dict[str, Any]],
        context: dict[str, Any],
        lens_results: dict[str, dict[str, Any]] | None = None,
        active_lenses: list[str] | None = None,
    ) -> DeliberationResult:
        if not transcript:
            return DeliberationResult(
                question=question, recommendation="No deliberation occurred.",
                confidence=0.0, consensus_view="", dissenting_views=[],
                key_uncertainties=[], participants=participants, rounds=0,
            )

        final_round = transcript[-1]["responses"]

        # Confidence: blend participant coverage with response agreement.
        coverage = min(1.0, len(participants) / self._config["max_modules"])
        agreement = self._response_agreement_score(final_round)
        agreement_weight = agreement if agreement <= 0.9 else 0.9 - (agreement - 0.9) * 0.5
        confidence = round(coverage * 0.6 + agreement_weight * 0.4, 2)

        # Separate adversarial voices from consensus voices
        dissent: list[str] = []
        consensus_parts: list[str] = []
        for mod_name, resp in final_round.items():
            role = _DELIBERATION_ROLES.get(mod_name, {}).get("role", "")
            if role == "adversarial":
                dissent.append(f"[{mod_name}] {resp[:200]}")
            else:
                consensus_parts.append(resp[:200])
        consensus = " ".join(consensus_parts) if consensus_parts else ""

        # Inject lens findings into synthesis
        lens_summary_parts: list[str] = []
        if lens_results:
            for lens_name, lr in lens_results.items():
                if lens_name == "ethical":
                    lens_summary_parts.append(f"ETHICAL LENS: {lr.get('result', '')[:300]}")
                elif lens_name == "verification":
                    n = lr.get("conflict_count", 0)
                    lens_summary_parts.append(
                        f"VERIFICATION LENS: {n} conflict(s) detected across "
                        f"{lr.get('sources_tracked', 0)} sources, "
                        f"{lr.get('claims_recorded', 0)} claims."
                    )
                elif lens_name == "lateral":
                    conns = lr.get("connections", [])
                    if conns:
                        top = conns[0]
                        lens_summary_parts.append(
                            f"LATERAL LENS: Top surprise connection -- {top.get('explanation', '')} "
                            f"(surprise: {top.get('surprise', 0)})"
                        )
                elif lens_name == "synthesis":
                    ins_list = lr.get("insights", [])
                    if ins_list:
                        top_ins = ins_list[0]
                        lens_summary_parts.append(
                            f"SYNTHESIS LENS: Cross-domain link between "
                            f"{', '.join(top_ins.get('domains', []))} via "
                            f"{', '.join(top_ins.get('shared_tags', [])[:5])} "
                            f"(strength: {top_ins.get('strength', 0)})"
                        )

        lens_text = "\n".join(lens_summary_parts) if lens_summary_parts else ""

        # LLM synthesis path
        llm = context.get("llm")
        if llm is not None:
            transcript_lines: list[str] = []
            for entry in transcript:
                transcript_lines.append(f"--- Round {entry['round']} ---")
                for mod_name, resp in entry["responses"].items():
                    role_label = _DELIBERATION_ROLES.get(mod_name, {}).get("role", "general")
                    transcript_lines.append(f"[{mod_name} / {role_label}]: {resp[:400]}")
            transcript_text = "\n".join(transcript_lines)

            prompt = (
                "You are synthesizing a multi-agent deliberation council. "
                "Below is the full transcript across all rounds, followed by the original question. "
                "Produce a structured synthesis that integrates every perspective. "
                "Be specific -- reference the actual content from the transcript.\n\n"
                f"QUESTION: {question}\n\n"
                f"TRANSCRIPT:\n{transcript_text}\n\n"
            )
            if lens_text:
                prompt += f"LENS FINDINGS:\n{lens_text}\n\n"
            prompt += (
                "Respond in this exact format:\n"
                "RECOMMENDATION:\n"
                "<A clear, actionable recommendation integrating the perspectives above>\n\n"
                "KEY UNCERTAINTIES:\n"
                "1. <uncertainty drawn from the deliberation>\n"
                "2. <uncertainty drawn from the deliberation>\n"
                "3. <uncertainty drawn from the deliberation>\n\n"
                "DISSENTING VIEWS:\n"
                "<Summarise significant disagreements or adversarial challenges raised>\n\n"
                "CONSENSUS:\n"
                "<One sentence capturing broad agreement among non-adversarial participants>"
            )

            try:
                raw = await llm(prompt)
            except Exception:
                raw = None

            if raw:
                def _section(text: str, header: str) -> str:
                    m = re.search(
                        rf"{re.escape(header)}\s*\n(.*?)(?=\n[A-Z ]+:\n|\Z)",
                        text,
                        re.DOTALL | re.IGNORECASE,
                    )
                    return m.group(1).strip() if m else ""

                rec = _section(raw, "RECOMMENDATION:") or raw[:400]

                uncertainties_block = _section(raw, "KEY UNCERTAINTIES:")
                uncertainties = [
                    line.lstrip("0123456789.- ").strip()
                    for line in uncertainties_block.splitlines()
                    if line.strip()
                ] or ["See full synthesis above."]

                llm_dissent = _section(raw, "DISSENTING VIEWS:")
                if llm_dissent:
                    dissent = [f"[synthesis] {llm_dissent[:300]}"]

                llm_consensus = _section(raw, "CONSENSUS:")
                if llm_consensus:
                    consensus = llm_consensus

                return DeliberationResult(
                    question=question,
                    recommendation=rec,
                    confidence=confidence,
                    consensus_view=consensus,
                    dissenting_views=dissent,
                    key_uncertainties=uncertainties,
                    participants=participants,
                    rounds=len(transcript),
                    lenses_applied=active_lenses or [],
                    transcript=transcript,
                )

        # Fallback: raw concatenation when no LLM is available or it failed
        recommendation = " | ".join(
            f"{mod_name}: {resp[:150]}" for mod_name, resp in final_round.items()
        )
        if lens_text:
            recommendation += f"\n\nLens findings:\n{lens_text}"

        return DeliberationResult(
            question=question,
            recommendation=recommendation,
            confidence=confidence,
            consensus_view=consensus,
            dissenting_views=dissent,
            key_uncertainties=["LLM synthesis unavailable -- raw responses returned."],
            participants=participants,
            rounds=len(transcript),
            lenses_applied=active_lenses or [],
            transcript=transcript,
        )

    # ===================================================================
    # handle() -- main entry point
    # ===================================================================

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        # Mode detection
        if self._detect_negotiation_mode(message):
            return await self._handle_negotiation(message, context)
        if self._detect_simulation_mode(message):
            return await self._handle_simulation(message, context)

        # Standard deliberation
        result = await self.deliberate(message, context)

        # If deliberation had no participants, use LLM directly
        if not result.participants and result.confidence == 0.0:
            llm = context.get("llm")
            if llm:
                prompt = (
                    "You are Council, a multi-perspective deliberation engine. "
                    "Analyze the following question from multiple angles -- consider "
                    "pros and cons, risks, trade-offs, and stakeholder perspectives. "
                    "Provide a clear recommendation with reasoning.\n\n"
                    f"Question: {message}"
                )
                try:
                    response = await llm(prompt)
                    return f"[Council] Direct analysis (LLM):\n\n{response}"
                except Exception:
                    pass

        lines = [
            f"[Council] Deliberation complete ({result.rounds} rounds, {len(result.participants)} participants)",
            f"Participants: {', '.join(result.participants)}",
            f"Confidence: {result.confidence}",
        ]
        if result.lenses_applied:
            lines.append(f"Lenses: {', '.join(result.lenses_applied)}")
        lines.append("")
        lines.append(f"Recommendation: {result.recommendation}")

        if result.dissenting_views:
            lines.append("")
            lines.append("Dissenting views:")
            for d in result.dissenting_views:
                lines.append(f"  - {d}")
        if result.key_uncertainties:
            lines.append("")
            lines.append("Uncertainties:")
            for u in result.key_uncertainties:
                lines.append(f"  - {u}")
        return "\n".join(lines)
