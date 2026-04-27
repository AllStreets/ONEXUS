# Batch 6 -- Council & Autonomic Design Specification

**Date:** 2026-04-27

---

## 1. Overview

Two new modules that transform NEXUS from a tool you query into a system that thinks and acts on your behalf. Both are open source (Apache 2.0), run locally, and require no external services.

**Council** orchestrates structured multi-agent deliberation between existing NEXUS modules. Inspired by Marvin Minsky's *Society of Mind* -- intelligence emerges from the interaction of many simpler agents, not from a single monolithic reasoner.

**Autonomic** observes your patterns, learns your routines, and gradually takes autonomous action -- but only as fast as Aegis trust allows. Every action is auditable, every decision is adversarially checked, and trust retreats on failure.

Both modules follow Approach A (lightweight orchestration): they call existing modules through the standard `handle()` interface. Zero changes to existing module code. Modules don't know they're participating in a deliberation or being observed.

---

## 2. Module: Council

### 2.1 Purpose

Take a question or decision, select relevant modules, run a structured multi-round debate, synthesize the result, and return both a recommendation and the full deliberation transcript.

### 2.2 Architecture

```
User Question
     │
     V
  ┌──────────┐
  │ COUNCIL  │
  │ (select) │──── Which modules are relevant?
  └────┬─────┘
       │
       V
  ┌─────────────────────────────────┐
  │        DELIBERATION             │
  │                                 │
  │  Round 1: Each module responds  │
  │  Round 2: Each sees others'     │
  │           arguments, responds   │
  │  Round 3: Final positions       │
  │                                 │
  │  Pulse: broadcasts each round   │
  │  Chronicle: logs full transcript│
  └────────────┬────────────────────┘
               │
               V
  ┌──────────────────┐
  │    SYNTHESIS      │
  │                   │
  │  Consensus view   │
  │  Dissenting views │
  │  Confidence score │
  │  Key uncertainties│
  └──────────────────┘
```

### 2.3 Module Selection

Council selects modules based on question content, using a strategy similar to Cortex's keyword routing but optimized for deliberation roles:

```python
_DELIBERATION_ROLES: dict[str, dict] = {
    "specter": {
        "role": "adversarial",
        "instruction": "Find weaknesses, hidden assumptions, and failure modes.",
        "triggers": ["decision", "should I", "plan", "strategy", "risk"],
    },
    "chronos": {
        "role": "temporal",
        "instruction": "Model future timelines and consequences.",
        "triggers": ["future", "long-term", "timeline", "when", "deadline"],
    },
    "serendipity": {
        "role": "lateral",
        "instruction": "Surface non-obvious connections and overlooked perspectives.",
        "triggers": ["option", "alternative", "creative", "stuck", "blind spot"],
    },
    "forge": {
        "role": "strategic",
        "instruction": "Analyze trade-offs, incentives, and negotiation angles.",
        "triggers": ["deal", "offer", "trade-off", "cost", "benefit", "negotiate"],
    },
    "atlas": {
        "role": "factual",
        "instruction": "Provide relevant facts and knowledge context.",
        "triggers": ["fact", "know", "data", "evidence", "history"],
    },
    "cipher": {
        "role": "verification",
        "instruction": "Assess source reliability and information conflicts.",
        "triggers": ["trust", "source", "verify", "conflict", "credib"],
    },
    "prism": {
        "role": "synthesis",
        "instruction": "Find cross-domain connections and synthesize perspectives.",
        "triggers": ["connect", "relate", "pattern", "synthesize", "insight"],
    },
}
```

Council scores the question against each role's triggers and selects the top 3-5 (configurable, default 4). At least Specter (adversarial) is always included -- every deliberation needs a devil's advocate.

### 2.4 Deliberation Protocol

Each round follows this structure:

**Round 1 -- Opening positions:**
Each selected module receives the user's question plus its role instruction via `handle()`. Context dict includes:
```python
{
    "mode": "council_deliberation",
    "round": 1,
    "role": "adversarial",
    "instruction": "Find weaknesses...",
    "question": "Should I switch to freelancing?",
    "prior_responses": {},  # empty for round 1
}
```

**Round 2 -- Cross-examination:**
Each module receives the same question plus ALL round 1 responses from other modules. Context includes:
```python
{
    "mode": "council_deliberation",
    "round": 2,
    "role": "adversarial",
    "instruction": "Find weaknesses...",
    "question": "Should I switch to freelancing?",
    "prior_responses": {
        "chronos": "Looking at a 5-year timeline...",
        "serendipity": "Consider that your photography hobby...",
        "forge": "The trade-off structure here...",
    },
}
```

**Round 3 -- Final positions:**
Each module sees all round 2 responses and submits its final position. Same context structure with `"round": 3`.

### 2.5 Synthesis

After all rounds complete, Council synthesizes using the LLM (via Cortex's `_llm` function):

```python
@dataclass
class DeliberationResult:
    question: str
    recommendation: str          # synthesized consensus
    confidence: float            # 0.0-1.0
    consensus_view: str          # what most modules agreed on
    dissenting_views: list[str]  # preserved minority opinions
    key_uncertainties: list[str] # what remains unknown
    participants: list[str]      # which modules participated
    rounds: int                  # how many rounds ran
    transcript: list[dict]       # full round-by-round transcript
```

The synthesis prompt instructs the LLM to:
1. Identify the majority position
2. Preserve the strongest dissenting argument (not discard it)
3. Rate confidence based on agreement level (unanimous = high, split = low)
4. List what the modules collectively couldn't resolve

### 2.6 Integration Points

- **Pulse:** Broadcasts `council.deliberation.start`, `council.round.complete`, and `council.deliberation.complete` events. Other modules can subscribe for observability.
- **Chronicle:** Logs the full deliberation: question, participants, each round's responses, synthesis, and confidence. Immutable record of every Council decision.
- **Engram:** Stores the result in episodic memory. Autonomic can later reference past deliberations.
- **Aegis:** Council's own trust score. Low trust = can only deliberate. Higher trust = can trigger actions based on deliberation outcomes.

### 2.7 Configuration

```python
DEFAULT_CONFIG = {
    "max_rounds": 3,
    "min_modules": 3,
    "max_modules": 5,
    "always_include": ["specter"],  # always have a devil's advocate
    "timeout_per_round_seconds": 30,
}
```

### 2.8 Cortex Keywords

```python
"council": ["deliberate", "debate", "council", "perspectives", "weigh", "consider",
            "should I", "decide", "pros and cons", "think through", "advise"],
```

---

## 3. Module: Autonomic

### 3.1 Purpose

Observe user patterns, learn routines, and gradually take autonomous action as trust is earned through successful outcomes. Transforms NEXUS from reactive to proactive.

### 3.2 Trust Tiers

| Tier | Trust Range | Capability | Description |
|------|-------------|-----------|-------------|
| Observer | 0-20 | Watch only | Learns patterns from all Pulse events. Builds internal models. Never surfaces anything. |
| Suggester | 21-50 | Suggest | Proactively offers observations and suggestions. "You usually do X around this time." |
| Drafter | 51-75 | Prepare | Prepares actions for approval. Pre-runs Council deliberations. Drafts responses via Echo. |
| Actor | 76-90 | Act + confirm | Executes routine actions autonomously. Asks permission for novel situations. |
| Steward | 91-100 | Full autonomy | Autonomous operation in earned domains. Specter audits a random sample. |

### 3.3 Architecture

```
  All Pulse Events
       │
       V
  ┌────────────┐
  │ AUTONOMIC  │
  │ (observe)  │──── Pattern DB (SQLite via Engram)
  └────┬───────┘
       │
       │  Trust check via Aegis
       V
  ┌─────────────────────┐
  │   ACTION PIPELINE   │
  │                     │
  │  1. Pattern match   │──── Is this a known routine?
  │  2. Novelty check   │──── Has user approved similar before?
  │  3. Stakes assess   │──── Low/medium/high impact?
  │  4. Trust gate      │──── Does current trust allow this?
  │  5. Specter audit   │──── Random audit check (10%)
  │  6. Execute / Ask   │──── Act or request permission
  └─────────────────────┘
       │
       V
  Chronicle logs everything
```

### 3.4 Pattern Model

Autonomic tracks patterns as structured records in Engram:

```python
@dataclass
class Pattern:
    id: str
    category: str              # "scheduling", "communication", "research", etc.
    description: str           # human-readable pattern description
    trigger_conditions: dict   # when this pattern activates
    action_template: str       # what to do
    confidence: float          # 0.0-1.0, increases with repetition
    times_observed: int        # how many times seen
    times_approved: int        # how many times user approved the action
    times_rejected: int        # how many times user rejected
    last_seen: str             # ISO timestamp
```

Patterns are learned by subscribing to all Pulse events and tracking:
- **Temporal patterns:** What happens at what time/day/frequency
- **Sequence patterns:** What follows what (action A usually precedes action B)
- **Response patterns:** How the user typically responds to certain situations
- **Decision patterns:** What the user approves vs. rejects

### 3.5 Domain-Specific Trust

Autonomic maintains per-domain trust scores via Aegis, separate from its global module trust:

```python
@dataclass
class DomainTrust:
    domain: str           # "scheduling", "communication", "research", etc.
    trust_score: int      # 0-100, independent per domain
    successes: int
    failures: int
    last_failure: str     # ISO timestamp
    cooldown_until: str   # ISO timestamp, if in retreat
```

This means Autonomic can be Steward-level for scheduling (trust 95 -- it's been managing your calendar for months without error) while still Observer-level for financial decisions (trust 10 -- you've never let it touch money).

### 3.6 Retreat Mechanism

When an autonomous action produces a bad outcome (user flags it, or Specter audit catches an error):

1. Domain trust drops by 20 points (configurable)
2. If trust drops below the current tier threshold, Autonomic retreats to the lower tier for that domain
3. A cooldown period begins (default 48 hours) during which the domain trust cannot increase
4. The failure is logged to Chronicle with full reasoning chain
5. Autonomic must re-earn trust through the normal progression

### 3.7 Council Integration

For decisions above a configurable stakes threshold, Autonomic invokes Council before acting:

- **Low stakes** (routine, previously approved pattern): Act directly
- **Medium stakes** (new variation of known pattern): Quick Council deliberation (2 rounds, 3 modules)
- **High stakes** (novel situation or high-impact domain): Full Council deliberation (3 rounds, 5 modules), then present recommendation to user regardless of trust level

Stakes assessment uses pattern confidence, domain sensitivity, and action reversibility.

### 3.8 Specter Audit

At configurable intervals (default: 10% of autonomous actions), Specter retroactively audits Autonomic's decision:

1. Autonomic logs its reasoning chain to Chronicle
2. After execution, Specter receives the reasoning chain and outcome
3. Specter evaluates: was the reasoning sound? Were alternatives considered? Was risk appropriately assessed?
4. If Specter flags the decision, domain trust is reduced

This creates an adversarial feedback loop that prevents Autonomic from becoming overconfident.

### 3.9 Kill Switch

`nexus deny autonomic` immediately:
1. Revokes all autonomous permissions across all domains
2. Resets all domain trust scores to 0
3. Logs the revocation to Chronicle
4. Autonomic returns to pure Observer mode

This is non-negotiable and cannot be overridden by Autonomic itself. The user is always sovereign.

### 3.10 Cortex Keywords

```python
"autonomic": ["automate", "routine", "autopilot", "autonomous", "on my behalf",
              "handle it", "take care of", "manage for me", "do it for me"],
```

### 3.11 Pulse Subscriptions

Autonomic subscribes to:
- `*` (wildcard) -- observes all events for pattern learning
- `council.deliberation.complete` -- learns from Council outcomes
- `aegis.trust.change` -- tracks trust changes across all modules

Autonomic publishes:
- `autonomic.pattern.detected` -- new pattern identified
- `autonomic.action.proposed` -- action prepared for approval
- `autonomic.action.executed` -- autonomous action taken
- `autonomic.action.rejected` -- user rejected a proposed action
- `autonomic.retreat` -- trust dropped, tier retreated

---

## 4. File Structure

```
nexus/modules/
├── council.py       ← Multi-agent deliberation orchestrator
└── autonomic.py     ← Earned autonomous action engine

tests/
├── test_council.py  ← Council deliberation tests
└── test_autonomic.py ← Autonomic pattern + trust tests
```

No new files in `nexus/kernel/`. No modifications to existing modules. No new dependencies beyond the standard library.

---

## 5. README Updates

After implementation, update README.md:
- Add Council and Autonomic to the architecture diagram (new tier: "Orchestration" between kernel and existing module tiers)
- Add to the "What's Built" tables
- Update module count badges (23 → 25)
- Update test count badge
- Add to Module Roadmap (Batch 6: BUILT)

---

## 6. Site Updates

After implementation, update the NEXUS site:
- Add Council and Autonomic to ModuleGrid.astro with a new tier color
- Run generate-docs.py to auto-generate reference pages
- Push to trigger GitHub Actions deployment

---

## 7. Constraints

- Apache 2.0 licensed, fully open source
- No external API calls, no network access required
- No modifications to existing modules or kernel components
- All data stays in local SQLite via Engram
- Must work without an LLM (graceful degradation -- synthesis step returns raw transcript instead of LLM summary)
- Must not break any of the existing 233 tests
