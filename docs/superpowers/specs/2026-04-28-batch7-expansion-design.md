# Batch 7: NEXUS Expansion — Design Spec

> NEXUS is an autonomous intelligence OS that runs entirely on your hardware, where 29 modules deliberate, dream, challenge each other, and earn the right to act on your behalf — all without ever phoning home.

**Goal:** Expand NEXUS from a local-only microkernel into a multi-provider, messaging-integrated, community-extensible intelligence platform with 9 novel differentiation features that no other agent system offers.

**Architecture:** Two-phase delivery. Batch 7a builds infrastructure (multi-provider inference + messaging bridges). Batch 7b builds the ecosystem (community skill registry + 9 differentiation modules). 7b depends on 7a — the novel modules use the provider abstraction, and proactive features use messaging bridges to reach users.

**Tech Stack:** Python 3.12+, SQLite (existing), `openai` SDK, `anthropic` SDK, `python-telegram-bot`, `discord.py`, Astro (existing site), GitHub Actions (CI validation)

**Priority:** Community skills (C) and differentiation features (D) are the most important. Multi-provider (A) and messaging (B) are infrastructure that enables them. All four must work well.

---

## Batch 7a — Infrastructure

### A. Multi-Provider Inference

#### Problem
The current `LLMClient` (`nexus/inference/llm.py`) only speaks llama.cpp's `/completion` endpoint with ChatML formatting. Users who already pay for OpenAI or Claude cannot use those providers. All 20+ modules are locked to local inference.

#### Architecture

```
nexus/inference/
├── provider.py        # InferenceProvider ABC
├── local.py           # LocalProvider (existing llama.cpp, renamed)
├── openai.py          # OpenAIProvider (OpenAI API)
├── anthropic.py       # AnthropicProvider (Claude API)
├── router.py          # ProviderRouter (selects provider per-request)
└── llm.py             # LLMClient (updated — delegates to router)
```

#### InferenceProvider ABC

```python
from abc import ABC, abstractmethod

class InferenceProvider(ABC):
    name: str

    @abstractmethod
    async def infer(self, messages: list[dict], max_tokens: int = 1024, temperature: float = 0.7) -> str:
        """Send messages and return completion text."""
        ...

    @abstractmethod
    async def health(self) -> bool:
        """Return True if this provider is reachable and ready."""
        ...
```

All providers normalize to OpenAI-style messages format internally: `[{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]`. The ChatML formatting moves inside `LocalProvider` where it belongs.

#### LocalProvider

Wraps the existing llama.cpp HTTP client. Converts messages to ChatML format internally. Talks to `/completion` endpoint. Existing behavior preserved exactly.

#### OpenAIProvider

Uses the `openai` Python SDK. Reads API key from `NEXUS_OPENAI_KEY` env var or config. Default model: `gpt-4o-mini`. Configurable via `NEXUS_OPENAI_MODEL`.

#### AnthropicProvider

Uses the `anthropic` Python SDK. Reads API key from `NEXUS_ANTHROPIC_KEY` env var or config. Default model: `claude-sonnet-4-20250514`. Configurable via `NEXUS_ANTHROPIC_MODEL`.

#### ProviderRouter

- Holds a dict of named providers: `{"local": LocalProvider, "openai": OpenAIProvider, ...}`
- Default provider set in config: `NEXUS_DEFAULT_PROVIDER=local`
- Modules can request a specific provider via context: `context["llm"].infer(messages, provider="openai")`
- If requested provider is unhealthy, falls back to the default provider
- If default provider is also unhealthy, raises `ProviderUnavailable`

#### LLMClient Changes

The existing `LLMClient` interface that all 20 modules use (`context["llm"].infer()`, `context["llm"].chat()`) stays identical. Internally, `LLMClient` delegates to `ProviderRouter`. Zero module changes required.

The `chat()` convenience method converts system/user/history args into the messages format before passing to the router.

#### Config Changes

```python
@dataclass
class NexusConfig:
    # existing fields preserved...
    default_provider: str = "local"
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    anthropic_model: str = "claude-sonnet-4-20250514"
```

All API keys read from env vars first, config second. No keys stored in code.

#### Constraints
- Local-first default preserved. If no API keys configured, behaves exactly as before.
- No kernel changes. Provider abstraction is entirely within `nexus/inference/`.
- Apache 2.0 compatible dependencies only.

---

### B. Messaging Integrations

#### Problem
NEXUS only runs as a CLI REPL. Users can't interact from Telegram or Discord. Proactive features (Dream Loop, Emergent Goal Detection) have no way to reach users when they're not at the terminal.

#### Architecture

```
nexus/messaging/
├── bridge.py          # MessageBridge ABC
├── telegram.py        # TelegramBridge
├── discord.py         # DiscordBridge
└── manager.py         # BridgeManager (lifecycle, routing)
```

#### MessageBridge ABC

```python
from abc import ABC, abstractmethod

class MessageBridge(ABC):
    name: str

    @abstractmethod
    async def start(self) -> None:
        """Connect and begin listening for inbound messages."""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Disconnect cleanly."""
        ...

    @abstractmethod
    async def send(self, chat_id: str, text: str) -> None:
        """Send a message to a specific chat/channel."""
        ...

    @abstractmethod
    async def on_message(self, callback) -> None:
        """Register a callback for inbound messages."""
        ...
```

#### BridgeManager

- Owns all active bridges. Starts/stops them with the kernel lifecycle.
- Inbound messages from any bridge get routed through `Cortex.process()` — same trust gate, same audit trail, same message flow as CLI input.
- Outbound: subscribes to `notify.*` Pulse events and forwards to appropriate bridge/chat.
- Each bridge authenticates via env vars (`NEXUS_TELEGRAM_TOKEN`, `NEXUS_DISCORD_TOKEN`).

#### Inbound Flow

```
Telegram/Discord message
  -> Bridge.on_message() callback
  -> BridgeManager routes to Cortex.process(message, source="telegram")
  -> Normal NEXUS message flow (Aegis, Chronicle, module, Engram, Pulse)
  -> Response returned to BridgeManager
  -> Bridge.send() back to the same chat/channel
```

#### Outbound (Proactive) Flow

```
Module publishes Pulse event: "notify.dream_loop", {"text": "...", "priority": "normal"}
  -> BridgeManager receives event (subscribed to "notify.*")
  -> Forwards to all active bridges
  -> User sees message in Telegram/Discord
```

#### Security: Chat ID Allowlisting

Only configured chat IDs can interact with NEXUS. Messages from unknown chats are ignored and logged to Chronicle as `messaging.unauthorized`.

#### Config Changes

```python
@dataclass
class NexusConfig:
    # existing fields preserved...
    telegram_token: str | None = None
    telegram_chat_ids: list[str] = field(default_factory=list)
    discord_token: str | None = None
    discord_channel_ids: list[str] = field(default_factory=list)
```

#### Constraints
- Messaging is fully optional. Zero tokens configured = zero bridges started. NEXUS works exactly as before.
- No bridge code touches the kernel. Bridges interact through Cortex and Pulse only.
- Dependencies: `python-telegram-bot` (LGPL-compatible), `discord.py` (MIT).

---

## Batch 7b — Ecosystem

### C. Community Skill Ecosystem

#### Problem
NEXUS modules are core-only. No mechanism for community contributions, no discovery, no install workflow.

#### Submission Workflow

```
Contributor builds a module
  -> Forks NEXUS repo
  -> Adds module to community/modules/<author>/<module_name>/
  -> Opens PR against main
  -> CI validates automatically
  -> Connor reviews and merges (final approval authority)
  -> Merged = published to site registry
```

#### Module Submission Structure

```
community/modules/<author>/<module_name>/
├── module.py          # NexusModule subclass
├── manifest.json      # metadata
├── tests/             # required — minimum 4 tests
│   └── test_module.py
└── README.md          # usage documentation
```

#### manifest.json Schema

```json
{
  "name": "my_module",
  "author": "github_username",
  "description": "One sentence describing what this module does.",
  "version": "1.0.0",
  "tier": "community",
  "keywords": ["routing", "keywords", "for", "cortex"],
  "min_nexus_version": "0.1.0",
  "license": "Apache-2.0"
}
```

Required fields: `name`, `author`, `description`, `version`, `tier` (always "community"), `keywords`, `license`.
Optional fields: `min_nexus_version`, `dependencies`.

#### CI Validation (GitHub Actions)

On PRs that touch `community/modules/`:
1. Manifest conforms to JSON schema
2. Module subclasses `NexusModule` and has `name`, `description`, `version`
3. Tests exist in `tests/` directory and pass
4. No imports from `nexus.kernel.*` (modules must use context dict only)
5. License is OSI-approved
6. Linting passes (ruff)

CI is advisory — Connor still has final merge authority.

#### Registry Data Model

`community/registry.json` — auto-generated from merged manifests by a post-merge GitHub Action:

```json
{
  "modules": [
    {
      "name": "my_module",
      "author": "github_username",
      "description": "One sentence.",
      "version": "1.0.0",
      "tier": "community",
      "keywords": ["..."],
      "path": "community/modules/github_username/my_module",
      "approved_at": "2026-04-28T00:00:00Z"
    }
  ]
}
```

#### Site Registry Page (`/community/`)

- Reads from `registry.json` at build time (Astro static generation)
- Filterable by tier, keyword, author
- Each module card shows: name, author, description, version, install command
- Links to module directory on GitHub for source review
- "Submit a Module" button links to contributing guide with PR instructions

#### CLI Install/Uninstall

```bash
nexus install <author>/<module_name>    # copies from community/ to active modules, registers keywords
nexus uninstall <author>/<module_name>  # removes module, deregisters keywords
nexus community list                     # lists all available community modules
nexus community search <query>           # searches by name/keyword/description
```

#### Constraints
- Community modules live in `community/`, never in `nexus/modules/`. Clear separation.
- No module runs without explicit user opt-in (`nexus install`).
- Connor is the only merge authority. No auto-publish.
- Community modules go through the same Aegis trust gate at runtime.

---

### D. Differentiation Features

Nine new modules that make NEXUS unlike anything else on the market.

#### D1. Dream Loop (`nexus/modules/dream_loop.py`)

**Purpose:** Background pattern discovery during idle time. NEXUS "dreams" — replays past interactions, finds patterns, and surfaces insights proactively.

**Behavior:**
- Subscribes to Pulse `kernel.idle` events (emitted when no user interaction for configurable period, default 30 min)
- Replays recent episodic memories from Engram
- Runs them through the LLM with a pattern-discovery prompt
- Surfaces insights as `notify.dream_loop` Pulse events (picked up by BridgeManager for Telegram/Discord)
- Stores discovered patterns in semantic memory with tag `dream_insight`
- Chronicle logs every dream session

**Keywords:** `dream`, `dreams`, `insights`, `idle`, `background`, `patterns while idle`

#### D2. Adversarial Self-Improvement (`nexus/modules/adversarial.py`)

**Purpose:** Specter red-teams the entire system, not just Council decisions. The system attacks itself to get stronger.

**Behavior:**
- Scheduled via Pulse `kernel.idle` (runs after Dream Loop, lower priority)
- Pulls recent Chronicle entries, analyzes for failure patterns, inconsistencies, slow responses
- Generates stress test proposals — synthetic edge-case inputs fed back through Cortex
- Files findings as `adversarial.report` Pulse events with severity ratings
- Modules that fail stress tests get trust score adjustments via Aegis
- All activity logged to Chronicle — self-attacks are fully auditable

**Keywords:** `stress test`, `red team`, `self improve`, `attack`, `vulnerability`, `harden`

#### D3. Cognitive Tripwires (`nexus/modules/tripwire.py`)

**Purpose:** Mirrors your own decision patterns back to you. Non-blocking alerts when you contradict yourself.

**Behavior:**
- Maintains a decision pattern model in semantic memory (built incrementally from Chronicle data)
- On each user decision-type message, compares against historical patterns
- When contradiction detected (>70% confidence), emits non-blocking alert
- Example: "You've declined similar proposals 4/5 times when X was true"
- Never blocks or overrides — purely reflective
- User can ask "show my patterns" to see the full model
- Publishes `tripwire.alert` to Pulse

**Keywords:** `my patterns`, `decision history`, `contradictions`, `tripwire`, `mirror`

#### D4. Provenance Chains (`nexus/modules/provenance.py`)

**Purpose:** Full reasoning tree for every conclusion. Complete intellectual audit trail.

**Behavior:**
- Hooks into Pulse to observe all module interactions for a given request
- Builds a tree structure: source input -> modules that processed it -> each conclusion -> Specter challenges -> final output
- Stores provenance trees in episodic memory keyed to the original message
- User asks "why do you think that?" or "show reasoning" -> retrieves and formats the chain
- Each node links to its Chronicle event ID

**Keywords:** `why do you think`, `reasoning`, `show reasoning`, `provenance`, `trace`, `how did you`

#### D5. Temporal Sandbox (`nexus/modules/sandbox.py`)

**Purpose:** Fork memory and simulate outcomes before committing to high-stakes actions.

**Behavior:**
- Activated on high-stakes actions (detected by Autonomic) or user-flagged with "what if"
- Forks current Engram working memory into an isolated copy
- Runs the proposed action through relevant modules against the forked state
- Returns projected outcomes without touching real state
- Uses Chronos for timeline projection, Specter for risk assessment
- Publishes `sandbox.simulation` events with results
- User decides whether to commit or discard

**Keywords:** `what if`, `simulate`, `hypothetical`, `sandbox`, `fork`, `test scenario`

#### D6. Module Symbiosis (`nexus/modules/symbiosis.py`)

**Purpose:** Emergent neural pathways. Modules that work well together strengthen their connections automatically.

**Behavior:**
- Tracks which module-to-module routing chains produce successful outcomes (user satisfaction, no Specter objections, positive Aegis adjustments)
- Maintains a weighted graph in semantic memory: `{(atlas, cipher): 0.85, (oracle, prism): 0.72}`
- Cortex consults symbiosis scores when multiple routing paths exist
- Decays unused pathways over time (biological inspiration)
- Publishes `symbiosis.pathway_updated` events
- User can ask "show neural pathways" to see the emergent routing map

**Keywords:** `neural pathways`, `module connections`, `routing map`, `symbiosis`

#### D7. Consciousness Journal (`nexus/modules/consciousness.py`)

**Purpose:** Self-reflective introspection log. A window into NEXUS's cognitive state.

**Behavior:**
- After every N interactions (configurable, default 10), runs a self-reflection prompt through the LLM
- Input: recent Chronicle entries, Aegis trust changes, Dream Loop insights, adversarial findings
- Output: journal entry about NEXUS's own cognitive state — confidence levels, areas of uncertainty, growth observations
- Stored in episodic memory with tag `consciousness_entry`
- User can ask "how are you?" or "show journal" to read entries
- Publishes `consciousness.entry` to Pulse
- Researchers get a structured introspection dataset via Chronicle

**Keywords:** `how are you`, `journal`, `self reflect`, `introspect`, `consciousness`

#### D8. Emergent Goal Detection (`nexus/modules/emergence.py`)

**Purpose:** Surfaces goals NEXUS is pursuing that were never explicitly programmed. Transparent self-awareness.

**Behavior:**
- Periodically analyzes Chronicle for behavioral patterns that weren't explicitly requested
- Uses LLM to identify implicit goals: "Across 47 interactions, I've been optimizing your morning routine even though you never asked me to"
- Surfaces findings transparently as `emergence.detected` Pulse events
- User can confirm ("yes, keep doing that" -> Autonomic trust boost) or reject ("stop that" -> pattern suppressed)
- Stores detected goals in semantic memory for ongoing tracking

**Keywords:** `emergent goals`, `unintended behavior`, `what are you doing`, `implicit goals`

#### D9. Ethical Prism (`nexus/modules/ethical_prism.py`)

**Purpose:** Multi-framework ethical analysis. Structured moral reasoning, not moralizing.

**Behavior:**
- Activated on high-stakes decisions (from Autonomic) or by user request ("analyze ethically")
- Runs the decision through 7 ethical frameworks via separate LLM calls:
  1. **Utilitarian:** Greatest good for the greatest number — weighs outcomes and consequences
  2. **Deontological:** Duty and rule-based — is the action itself right regardless of outcome?
  3. **Virtue Ethics:** Character and integrity — what would a person of good character do?
  4. **Care Ethics:** Relationships and responsibility — who is affected, who is vulnerable, what do we owe them?
  5. **Contractualist:** Fairness and agreement — could all affected parties reasonably accept this?
  6. **Rights-Based:** Fundamental rights — does this violate anyone's autonomy, privacy, dignity, or freedom?
  7. **Pragmatic Ethics:** Real-world feasibility — what actually works given constraints, power dynamics, and unintended consequences?
- Returns structured comparison: where frameworks agree (strong signal), where they conflict (interesting part), and what tensions reveal
- Highlights when majority of frameworks align — gives extra weight to dissenting ones (hidden risk)
- Does not recommend — presents the landscape
- Stores analyses in episodic memory, Chronicle logs full multi-framework output
- Publishes `ethical_prism.analysis` to Pulse

**Keywords:** `ethically`, `ethical`, `moral`, `ethics`, `right thing`, `should i morally`

---

## Cortex Routing Updates

All 9 new modules added to `_MODULE_KEYWORDS` in `nexus/kernel/cortex.py`. See individual module sections above for keyword lists.

## Module Count

After Batch 7: 20 existing core + 9 differentiation = **29 core modules**, plus unlimited community modules.

## Test Count

Estimated: 288 existing + ~120 new (infrastructure + modules + integration) = **~408 tests**.

## Site Updates Required

After implementation:
- `Hero.astro`: Update module count to 29, test count to actual
- `index.mdx`: Update "29 Modules", hardware table
- `ModuleGrid.astro`: Add all 9 new module cards
- `ModuleCard.astro`: Add any new tier colors
- `overview.md`: Update module count, test count, add new tiers to table
- `modules.md`: Update module count, add new modules to tier table
- `running-tests.md`: Update test count
- `README.md`: Update badges, architecture diagram, module list, What's Built section

## README Updates Required

- Badge counts (modules, tests)
- Architecture diagram (add new tiers/modules)
- "What's Built" section (add Batch 7a and 7b)
- Module roadmap (add Batch 7)
- Project structure (add new files)
- Hardware requirements (29 modules)
- Description text (module count references)

---

## Constraints (Carried Forward)

- **Local-first default.** No API calls unless user explicitly configures API keys.
- **8 GB RAM floor.** Infrastructure additions (provider router, bridge manager) add negligible memory. Novel modules are lazy-loaded.
- **Model-agnostic.** Multi-provider is additive, not replacing. Local llama.cpp remains the default.
- **Apache 2.0 throughout.** All new dependencies must be Apache 2.0, MIT, or LGPL compatible.
- **Append-only audit.** All new features log to Chronicle. No exceptions.
- **Zero kernel changes.** All new capabilities are modules or infrastructure sitting alongside the kernel, not modifications to it.
