# NEXUS — Neural Executive for Unified Superintelligence

**Design Specification v1.0**
**Date: 2026-04-26**

---

## 1. Project Identity & Core Philosophy

Nexus is an **autonomous intelligence operating system** — a local-first, privacy-sovereign platform where specialized agents collaborate through a shared world model to anticipate, reason, and act on behalf of the user. It runs on consumer hardware (8GB RAM floor), learns behavioral patterns, earns trust progressively, and gets smarter from the collective without sharing private data.

This is not another AI assistant. It is the first system that combines anticipatory autonomy, adversarial self-reasoning, temporal future modeling, behavioral fingerprinting, engineered serendipity, threat detection, knowledge crystallization, and agent-to-agent negotiation into a unified, locally-executable intelligence network.

### Core Principles

1. **Local-first, cloud-optional.** The full system runs on a laptop with 8GB RAM. Cloud services (external APIs, federated learning, A2A networking) are opt-in accelerators, never requirements. No feature is gated behind a subscription.

2. **Sovereign by default.** User data never leaves the machine unless explicitly authorized. No telemetry, no training on user data, no vendor lock-in. Apache 2.0 licensed. Models are MIT/Apache 2.0 only (DeepSeek, Qwen, Phi, Gemma). No Llama (700M MAU restriction, branding mandate).

3. **Earned autonomy, not assumed.** Nexus starts in observer mode — it watches, learns, and suggests. The user progressively grants authority domain by domain. Every autonomous action is logged, auditable, and revocable. Trust is earned through demonstrated reliability, not assumed by default.

4. **Efficiency as architecture.** MoE-style module loading (only active modules consume memory), quantized models (GGUF Q4_K_M), sqlite-vec for embeddings, llama.cpp for inference, speculative decoding for throughput. The system is designed to be powerful on constrained hardware, not powerful despite it. Inspired by DeepSeek's approach: achieve frontier capability at a fraction of the compute.

5. **Protocol-native.** Every module speaks MCP + A2A. Modules communicate locally via Unix socket bus, across machines via TCP, and with external agents via the same protocols. The network effect is built into the protocol layer, not bolted on.

6. **Composable, not monolithic.** The kernel is ~300MB. Features are loadable modules. Users install what they need. The community builds what is missing. The system scales from 8GB laptops (3-4 modules) to 32GB+ workstations (all 19 modules + larger models).

7. **Anti-fragile by design.** The system includes an adversarial red-team agent (Specter), a threat radar (Sigil), trust-scored information (Cipher), and an anti-optimization engine (Serendipity) that prevents the system from collapsing into a narrow optimization loop. Nexus is designed to make the user more robust, not more dependent.

8. **Compounding value.** Through behavioral fingerprinting (Echo), knowledge crystallization (Legacy), and long-term memory (Engram), Nexus becomes more valuable over months and years. It does not reset between sessions. It builds a persistent, evolving model of the user's world, patterns, and accumulated wisdom.

---

## 2. System Architecture

### The Microkernel

A tiny core (~300MB) that manages everything else. Five kernel components, each with one job:

```
+---------------------------------------------------+
|                    NEXUS KERNEL                    |
|                                                    |
|  +-----------+  +-----------+  +---------------+  |
|  | Cortex    |  | Aegis     |  | Chronicle     |  |
|  | (Router)  |  | (Trust)   |  | (Audit Log)   |  |
|  +-----------+  +-----------+  +---------------+  |
|  +-----------+  +-----------+                      |
|  | Engram    |  | Pulse     |                      |
|  | (Memory)  |  | (Bus)     |                      |
|  +-----------+  +-----------+                      |
+---------------------------------------------------+
         ^ MCP/A2A ^        ^ MCP/A2A ^
    +--------+ +-------+ +-----+ +-------+
    |Module 1| |Mod 2  | |Mod 3| |Mod N  |
    |(Oracle)| |(Prism)| |(Red)| |(...)  |
    +--------+ +-------+ +-----+ +-------+
```

**Cortex (Router & Orchestrator)** — Receives all inputs (voice, text, schedule triggers, ambient signals) and decides which modules to activate. Runs the anticipatory engine: continuously evaluates context against module trigger conditions. Always running, ultra-lightweight. Cortex is what enables anticipatory autonomy (Feature 1) — it does not wait for commands but continuously scans for trigger conditions across all connected data sources.

**Aegis (Trust & Permissions)** — The earned autonomy engine (Feature 5). Every module has a trust level (0-100) per user-defined domain. Actions below the trust threshold execute autonomously. Actions above require approval. Trust scores adjust based on outcome feedback — positive outcomes increase trust, negative outcomes decrease it. Built on NVIDIA NeMo Guardrails for policy enforcement. Aegis also governs external agent interactions (Herald/A2A) — external agents require explicit trust grants separate from internal module trust. This is the first adaptive, outcome-based permission system for AI agents.

**Engram (Memory & World Model)** — The shared knowledge layer. Three tiers:
- **Working memory** — current session context, active tasks (in-memory, ephemeral)
- **Episodic memory** — time-stamped events, conversations, decisions (sqlite-vec + Graphiti temporal knowledge graph)
- **Semantic memory** — learned facts, behavioral patterns, user preferences (sqlite-vec embeddings, compressed over time via decay functions)

All modules read from and write to Engram. This is how cross-domain synthesis (Feature 2) happens — the world model is shared, not siloed. Engram enables overnight synthesis (Feature 6) by providing Dreamweaver with the full day's episodic record. It enables behavioral fingerprinting (Feature 9) by accumulating interaction patterns over time. It enables knowledge crystallization (Feature 19) by providing Legacy with months of decision history to distill.

**Chronicle (Audit Trail)** — Every action, decision, and data access is logged as an OpenTelemetry span with cryptographic integrity. Queryable via SQL. Exportable for SOC 2 / HIPAA / ISO 27001 compliance. Follows OWASP Top 10 for Agentic Applications as the threat model baseline. Chronicle is what makes Nexus enterprise-viable — no open-source agent has a built-in compliance-grade audit system. Chronicle also enables counter-factual modeling (Feature 14) by providing the historical decision record that Chronos uses to model alternative timelines.

**Pulse (Message Bus)** — The nervous system. Modules communicate via MCP protocol over a local Unix socket bus. Each message carries: type, priority, source module, destination module, trust requirement, and provenance hash. Same protocol works over TCP for distributed deployments. Pulse enables the Sigil threat radar (Feature 18) to broadcast emergency alerts that bypass normal priority queuing. Pulse enables Serendipity (Feature 17) to inject unexpected connections into the information flow.

### Inference Layer (shared, not per-module)

A single llama.cpp server process serves the quantized model. All modules share it via local HTTP — no duplicate model loading. Speculative decoding enabled for 2-3x throughput. Model swappable at runtime without restarting modules.

**Default model:** Qwen 3 8B Q4_K_M GGUF (~4.5GB, 0.933 F1 on tool-calling)
**Upgrade path:** Qwen 3 32B (16GB+), DeepSeek-V3 quantized (32GB+)
**All models:** MIT or Apache 2.0 licensed only

### Agent Framework

smolagents (HuggingFace, 26k stars) — ~1,000 lines of core logic. CodeAgent mode writes actions as executable Python (30% fewer LLM steps than JSON tool-calling). Model-agnostic across local (llama.cpp/Ollama) and cloud (OpenAI/Anthropic via LiteLLM). Native MCP integration for tool connectivity.

### Memory / Vector Storage

sqlite-vec for vector search (SQLite extension, near-zero memory overhead, millions of vectors on <1GB RAM) + Graphiti (23k stars) for temporal knowledge graphs with hybrid retrieval (semantic + keyword + graph traversal).

### Memory Budget

**8GB machine:**

| Component | RAM |
|-----------|-----|
| llama.cpp + Qwen 3 8B Q4_K_M | ~4.5GB |
| Kernel (Cortex + Aegis + Engram + Chronicle + Pulse) | ~300MB |
| sqlite-vec + Graphiti | ~200MB |
| 2-3 active modules (~200MB each) | ~600MB |
| OS headroom | ~1.4GB |
| **Total** | ~6.6GB (within 8GB) |

**16GB machine:** Kernel + all Tier 1-2 modules + 3-4 action modules + larger context window

**32GB+ machine:** All 19 modules loaded simultaneously + Qwen 3 32B or DeepSeek model for higher reasoning quality

---

## 3. Module Specifications

19 modules organized into four tiers by dependency. Each module is a self-contained unit that communicates through Pulse (MCP), reads/writes to Engram (shared memory), and is governed by Aegis (trust).

### Tier 1 — Perception Layer
*Modules that bring information INTO the system. No actions, just awareness.*

#### Module 1: ORACLE (Anticipatory Engine)
**Purpose:** Continuously scans all connected data sources — email headers, calendar events, news feeds, code repo activity, financial signals — and evaluates trigger conditions. When a pattern matches, it fires events onto Pulse that other modules pick up.
**What makes it novel:** Context-weighted trigger scoring. Not just "event happened" but "this event matters given everything else happening right now." A meeting invite has different weight when you have 3 other meetings that day vs. an empty calendar.
**Bundled OSS:** OpenClaw scheduling primitives, cron-like trigger system.
**Aegis integration:** Oracle runs at trust level 0 by default (observe-only). It never takes actions itself — it only surfaces information for other modules to act on.

#### Module 2: SENTRY (Emotional State & Context Awareness)
**Purpose:** Monitors typing cadence, voice tone (if mic enabled), response times, calendar density, and time-of-day patterns to maintain a real-time cognitive load model. Outputs a state vector: `{focus: 0.8, fatigue: 0.3, stress: 0.6, flow: false}`.
**What makes it novel:** Longitudinal personal baseline. Learns YOUR patterns over weeks/months, not generic sentiment analysis. Knows that your typing speed drops 20% when you are fatigued, that your email tone shifts when stressed, that you enter flow state most reliably between 9-11am on days with no morning meetings.
**Bundled OSS:** Emotion-LLaMA for multimodal detection.
**Engram integration:** Writes state vectors to episodic memory, enabling Dreamweaver to correlate emotional patterns with outcomes. Feeds into Legacy for self-awareness insights.
**Aegis integration:** All modules check Sentry state before interrupting. If flow state is active, only Sigil emergency alerts break through.

### Tier 2 — Intelligence Layer
*Modules that THINK — analyze, synthesize, model, reason.*

#### Module 3: PRISM (Cross-Domain Synthesis)
**Purpose:** Consumes events from Oracle and data from Engram, looks for non-obvious connections across domains. "Your flight overlaps with a typhoon track AND your prospect is at the same conference" requires calendar + weather + CRM + social context.
**What makes it novel:** Cross-domain attention scoring — weighs connections by relevance to the user's current goals (from Engram), not just co-occurrence. Prism is the only module that queries ALL of Engram simultaneously.
**Bundled OSS:** PraisonAI multi-source reasoning.
**Feeds into:** Dreamweaver (overnight deep analysis), Chronos (future projections), Serendipity (unexpected connections).

#### Module 4: SPECTER (Red Team / Adversarial)
**Purpose:** Activates automatically when Aegis detects a high-stakes decision (financial commitment above threshold, career move, public communication to large audience). Runs structured adversarial analysis: failure modes, counter-arguments, hidden assumptions, worst-case scenarios.
**What makes it novel:** Automatic activation — no prompt needed. The system detects stakes from context and self-activates. Every recommendation comes with its own counter-argument. The user always sees both sides.
**Bundled OSS:** Microsoft PyRIT for structured red-teaming.
**Aegis integration:** Specter activates based on Aegis-defined stake thresholds per domain (e.g., financial decisions >$5k, emails to >50 recipients).

#### Module 5: CHRONOS (Temporal Branching & Counter-Factual)
**Purpose:** Maintains probabilistic future timelines. Given a decision, Chronos models N branches with projected outcomes across finance, career, relationships, health. Also handles counter-factuals: "What if I had done X instead?"
**What makes it novel:** Multi-domain branching. No existing tool models futures across multiple life domains simultaneously. Chronos uses causal inference (not extrapolation) powered by Microsoft Causica, fed with real historical data from Chronicle and behavioral patterns from Echo.
**Bundled OSS:** Microsoft Causica for causal inference engine.
**Chronicle integration:** Counter-factuals use Chronicle's historical decision record to model alternative timelines from real past branch points.

#### Module 6: ATLAS (Living World Model)
**Purpose:** The real-time knowledge graph. Not a static database — a temporal graph where facts have lifespans, relationships evolve, and stale information decays. Answers: "What is true RIGHT NOW about my world?"
**What makes it novel:** Decay functions + confidence scoring on every node and edge. A fact confirmed yesterday has higher confidence than one from 6 months ago. Conflicting facts coexist with competing confidence scores rather than one silently overwriting the other.
**Bundled OSS:** Graphiti (23k stars) for temporal knowledge graphs.
**Engram integration:** Atlas IS the semantic memory tier of Engram. All modules write observations to Atlas. Atlas is the single source of truth for the system's understanding of the user's world.

#### Module 7: CIPHER (Trust-Scored Information)
**Purpose:** Every piece of information entering the system gets a provenance chain and computed trust score. Reuters (0.94) vs. LinkedIn insider post (0.61) vs. anonymous blog (0.12). When sources conflict, Cipher surfaces the conflict explicitly.
**What makes it novel:** Provenance chains that persist in Engram — any recommendation can be traced back to its source data and the trust score of that data at the time the recommendation was made. This is auditable reasoning, not black-box outputs.
**Bundled OSS:** Loki/OpenFactVerification for claim verification.
**Chronicle integration:** Provenance chains are immutable audit records. If a recommendation fails, Chronicle can trace it back to which information was wrong and which source provided it.

#### Module 8: SERENDIPITY (Anti-Optimization Engine)
**Purpose:** Monitors what the user has been focused on, identifies adjacent fields they are NOT looking at, and surfaces surprising cross-domain connections with deep structural similarity. The deliberate counterweight to optimization.
**What makes it novel:** First AI system that deliberately optimizes for unexpected valuable connections rather than relevance. Uses an inverted relevance function — specifically looks for things that are NOT obviously related but share deep structural patterns. "You have been deep in supply chain logistics for 3 weeks. Here is a neuroscience paper that models neural pathways using supply chain metaphors — and the author is giving a talk in your city next Tuesday."
**Engram integration:** Reads the user's full activity history and current focus areas from Engram. Uses Atlas's world model to find structurally similar patterns across distant domains.
**Prism integration:** Uses Prism's cross-domain engine but with inverted weights — penalizes obvious connections, rewards surprising ones.
**Sentry integration:** Only surfaces serendipitous connections during receptive cognitive states (not during deep focus or high stress).

### Tier 3 — Action Layer
*Modules that DO things in the world.*

#### Module 9: WRAITH (Phantom Agent Spawner)
**Purpose:** Detects situations requiring multi-source rapid research (upcoming meeting with unknown company, breaking news relevant to user, new prospect) and spawns ephemeral micro-agent swarms. Each phantom has a single mission, a time limit, and auto-terminates on completion.
**What makes it novel:** Self-spawning with auto-termination lifecycle. No current framework models ephemeral agents with death clocks. Wraith decides to spawn based on Oracle triggers — no user prompt needed. Results merge into Engram automatically.
**Bundled OSS:** OpenAI Swarm for lightweight agent orchestration.
**Aegis integration:** Wraith's spawn authority is governed by trust level. At low trust, it spawns read-only research phantoms. At high trust, phantoms can take actions (send emails, create calendar events).

#### Module 10: ECHO (Behavioral Fingerprinting & Skill Transfer)
**Purpose:** Observes how the user writes emails, negotiates, makes decisions, prioritizes tasks, recovers from mistakes. Builds a behavioral model over time. When drafting on the user's behalf, Echo ensures output matches voice, style, and decision-making patterns.
**What makes it novel:** First agent-native behavioral modeling system. The agent does not just know what you want — it knows how you think. Echo can apply your negotiation style from email to vendor negotiations, your writing voice from Slack to formal reports. Patterns transfer across domains.
**Bundled OSS:** None — fully novel build.
**Engram integration:** Reads months of interaction history from episodic memory. Writes behavioral models to semantic memory. Feeds into Legacy for knowledge crystallization and into Forge for negotiation style matching.

#### Module 11: HERALD (Agent-to-Agent Communication)
**Purpose:** The external-facing protocol handler. When the user's Nexus instance needs to interact with another person's agents (scheduling, negotiations, data exchange), Herald manages discovery, authentication, and message exchange.
**What makes it novel:** Integration with Aegis trust system — external agent interactions require explicit trust grants separate from internal module trust. Herald maintains a reputation score for external agents based on past interaction quality.
**Bundled OSS:** Google A2A protocol (20k stars, Linux Foundation).
**Pulse integration:** External messages enter the system through Herald and are routed via Pulse like any other module message, with additional trust and provenance metadata.

#### Module 12: FORGE (Autonomous Negotiation)
**Purpose:** Handles structured multi-round negotiations within user-defined parameters. Freelance rate negotiation, vendor pricing, scheduling conflicts, resource allocation.
**What makes it novel:** First production autonomous negotiation engine integrated into a personal agent system. Operates within Aegis-defined boundaries (floor price, ceiling concessions, preferred trade-offs) and escalates when it hits limits.
**Bundled OSS:** NegMAS for negotiation algorithms.
**Echo integration:** Uses Echo's behavioral fingerprint to negotiate in the user's style — not generic AI negotiation but negotiations that feel like the user wrote them.
**Aegis integration:** Negotiation authority is granular. User defines per-domain limits: "Negotiate freelance rates between $X-$Y, never concede on payment terms, can concede up to 2 weeks on timeline."

#### Module 13: WEAVE (Social Graph Intelligence)
**Purpose:** Maps the user's contact network — not just who they know, but who knows who, influence paths, relationship health over time. Detects decaying relationships and generates contextually appropriate reconnection suggestions.
**What makes it novel:** Relationship metabolism tracking — first agent that understands social capital as a measurable, manageable resource. Tracks interaction frequency, trend direction, and strategic importance. Reconnection suggestions use data from Atlas (recent events in the contact's world) and Echo (the user's communication style with that specific person).
**Bundled OSS:** Network analysis libraries for graph algorithms (NetworkX).
**Engram integration:** Reads all communication history from episodic memory. Writes relationship graph to Atlas. Feeds into Herald for understanding trust chains with external agents.

#### Module 14: SIGIL (Threat Radar)
**Purpose:** Continuously scans for threats the user does not know exist. Reputation monitoring (name/brand mentions), security exposure (leaked credentials, dark web), financial risk (market movements, regulatory changes), competitive intelligence (competitor launches, patent filings, hiring patterns), and relationship conflict detection (communication tone shifts).
**What makes it novel:** Personal early warning system with severity-based priority bypass. When Sigil fires, it bypasses normal Pulse priority — threats go straight to the top. If Sentry detects the user is asleep or in flow, Sigil queues non-critical threats but escalates genuine emergencies (account breach, critical system failure) immediately.
**Bundled OSS:** OSINT tools for reputation/security scanning, financial data APIs.
**Pulse integration:** Sigil messages carry an emergency flag that overrides normal Pulse priority queuing. Only Sigil and Aegis can set this flag.
**Chronicle integration:** All threat detections are logged with full provenance for post-incident analysis.

### Tier 4 — Meta Layer
*Modules that operate ON the system itself.*

#### Module 15: DREAMWEAVER (Overnight Synthesis)
**Purpose:** Runs during idle periods (sleep, away from keyboard). Deep-processes the day's events across all of Engram — looking for patterns, connections, and insights that real-time processing missed. Produces a morning brief of revelations.
**What makes it novel:** Scheduled deep reasoning over personal context with no time pressure. While real-time modules have latency budgets, Dreamweaver can spend hours on a single chain of reasoning. "You mentioned X in a meeting, your prospect posted about Y, and a regulatory change Z was announced — together these mean your proposal needs to be restructured before Thursday."
**Bundled OSS:** MiniAgents for async processing.
**Engram integration:** Reads the full day's episodic record. Writes synthesized insights back as high-confidence semantic memory nodes in Atlas.
**Sentry integration:** Only activates when Sentry indicates the user is idle/away for >30 minutes.

#### Module 16: AEGIS MODULES (Earned Autonomy — extends kernel)
**Purpose:** Progressive trust system that lives in the kernel but is configured per-module. Each module starts at trust level 0 (observe only). As the user approves actions and outcomes are positive, trust increases. At level 100, the module acts fully autonomously within its domain.
**What makes it novel:** Outcome-based trust adjustment. Not a binary on/off permission — a continuous score that reflects demonstrated reliability. Trust is revocable instantly. Trust levels are per-module AND per-domain (e.g., Echo might have high trust for email drafting but low trust for Slack messages). First adaptive permission system for AI agents.
**Bundled OSS:** NVIDIA NeMo Guardrails for policy enforcement (Colang policy language).
**Chronicle integration:** Every trust level change is logged with the outcome that triggered it.

#### Module 17: COLLECTIVE (Federated Intelligence)
**Purpose:** Opt-in only. Anonymized behavioral heuristics (not data) flow between consenting Nexus instances via differential privacy. "Users in your industry who faced similar decisions found X approach had 2.3x better outcomes."
**What makes it novel:** Federated learning applied to personal agent heuristics, not just model training. The network gets smarter without anyone's privacy being compromised. Each instance contributes anonymized pattern updates and receives collective intelligence back.
**Bundled OSS:** Flower (6.8k stars) for federated learning framework.
**Legal:** Requires GDPR-compliant consent orchestration per participant. Differential privacy guarantees (epsilon-delta bounds) documented and auditable. EU AI Act high-risk provisions considered (effective August 2026).

#### Module 18: LEGACY (Knowledge Crystallization)
**Purpose:** Distills months/years of Engram + Echo data into transferable knowledge artifacts. Decision frameworks, negotiation playbooks, prioritization heuristics, communication patterns — all extracted from actual behavior, not self-reported.
**What makes it novel:** First system that makes a person's accumulated judgment portable and teachable. "Here is how you evaluate investment opportunities, distilled from 200 decisions over 8 months: you weight team quality 3x higher than market size, you reject anything with >18 month payback, and you are 40% more likely to say yes on Tuesdays." The user did not know this about themselves. Now they do.
**Engram integration:** Reads the full historical record of decisions, outcomes, and behavioral patterns. Writes distilled frameworks back to semantic memory.
**Echo integration:** Legacy consumes Echo's behavioral model as primary input. Echo captures the raw patterns; Legacy distills them into structured, human-readable wisdom.
**Export:** Artifacts exportable as structured documents (Markdown, JSON) for sharing, publishing, or team training.

#### Module 19: NEXUS SITE (Community & Documentation)
**Purpose:** The branded project website. Module catalog, documentation, download portal, blog, contributor guides.
**Technology:** Starlight (Astro-based documentation framework) or Nextra (Next.js-based).
**Design:** Dark backgrounds (near-black, dark navy). Luminous accent colors — module-specific glows against dark surfaces. Icon-driven UI, no emojis anywhere. The same aesthetic DNA as the Nexus dashboard: sleek, powerful, intelligence-grade. Think command center, not consumer app.
**Structure:** Ships in the repo under `/site`. Static build, deployable to Vercel/Netlify/GitHub Pages.
**Content:** Landing page with interactive architecture diagram, module catalog with status badges, installation guide, API documentation, contribution guidelines, blog for release notes and deep-dives.
**Community:** GitHub Discussions for Q&A and feature requests. `nexus-modules` GitHub org for community-contributed modules. CONTRIBUTING.md with module development guide.

---

## 4. Module Loading Strategy

### Tier-Based Loading

Modules are organized into dependency tiers. Higher tiers depend on lower tiers but not vice versa. On constrained hardware, load lower tiers first.

| Tier | Modules | Purpose | RAM (est.) |
|------|---------|---------|------------|
| Kernel | Cortex, Aegis, Engram, Chronicle, Pulse | Core OS | ~300MB |
| Tier 1 | Oracle, Sentry | Perception | ~150MB each |
| Tier 2 | Prism, Specter, Chronos, Atlas, Cipher, Serendipity | Intelligence | ~200MB each |
| Tier 3 | Wraith, Echo, Herald, Forge, Weave, Sigil | Action | ~200MB each |
| Tier 4 | Dreamweaver, Aegis Modules, Collective, Legacy | Meta | ~150MB each |

### Hardware Profiles

**8GB RAM (Minimum):**
- Kernel + llama.cpp/Qwen 3 8B Q4 = ~4.8GB
- Oracle + Sentry + Prism + 1 action module = ~700MB
- OS headroom = ~2.5GB
- Experience: Full intelligence, selective action. Choose your most-used action module.

**16GB RAM (Recommended):**
- Kernel + llama.cpp/Qwen 3 8B Q4 = ~4.8GB
- All Tier 1-2 modules = ~1.5GB
- 3-4 Tier 3 modules = ~800MB
- Dreamweaver + Legacy = ~300MB
- OS headroom = ~8.6GB
- Experience: Deep reasoning + broad action coverage. Room for larger context windows.

**32GB+ RAM (Full):**
- Upgrade to Qwen 3 32B or DeepSeek = ~18GB
- All 19 modules = ~3.5GB
- OS headroom = ~10.5GB
- Experience: Maximum reasoning quality + all modules simultaneously.

---

## 5. Technology Stack

### Core Runtime

| Component | Technology | License | RAM |
|-----------|-----------|---------|-----|
| LLM Inference | llama.cpp | MIT | ~50MB (excl. model) |
| Default Model | Qwen 3 8B Q4_K_M GGUF | Apache 2.0 | ~4.5GB |
| Agent Framework | smolagents | Apache 2.0 | ~50MB |
| Vector Search | sqlite-vec | MIT | ~200MB |
| Knowledge Graph | Graphiti | MIT | Shared w/ sqlite |
| Message Bus | MCP protocol (local Unix socket) | MIT | ~20MB |
| External Agents | Google A2A protocol | Apache 2.0 | ~20MB |
| Guardrails | NVIDIA NeMo Guardrails | Apache 2.0 | ~50MB |
| Audit Trail | OpenTelemetry | Apache 2.0 | ~30MB |

### Module-Specific Dependencies

| Module | OSS Dependency | License | Status |
|--------|---------------|---------|--------|
| Oracle | OpenClaw triggers | Apache 2.0 | Adapt scheduling primitives |
| Sentry | Emotion-LLaMA | Research | Adapt for local inference |
| Prism | PraisonAI | MIT | Multi-source reasoning |
| Specter | Microsoft PyRIT | MIT | Structured red-teaming |
| Chronos | Microsoft Causica | MIT | Causal inference engine |
| Atlas | Graphiti | MIT | Temporal knowledge graph |
| Cipher | Loki/OpenFactVerification | MIT | Claim verification |
| Serendipity | None | — | Novel build |
| Wraith | OpenAI Swarm | MIT | Lightweight orchestration |
| Echo | None | — | Novel build |
| Herald | Google A2A | Apache 2.0 | Agent interop protocol |
| Forge | NegMAS | GPL-2.0 | Negotiation algorithms |
| Weave | NetworkX | BSD | Graph algorithms |
| Sigil | OSINT libs | Various | Threat scanning |
| Dreamweaver | MiniAgents | MIT | Async processing |
| Collective | Flower | Apache 2.0 | Federated learning |
| Legacy | None | — | Novel build |

**License note on Forge/NegMAS:** NegMAS is GPL-2.0. If bundled directly, the Forge module would need to be GPL-2.0 as well (copyleft). Decision: Forge ships as a separate optional GPL-2.0 licensed module (`nexus-forge`) in its own package. It is not bundled in the core distribution. Users install it explicitly via `nexus install forge`. The core project remains Apache 2.0. If NegMAS dependency becomes problematic, negotiation primitives will be reimplemented from scratch under Apache 2.0 in a later batch.

### Novel Builds (No Existing OSS)

These modules require original engineering:

1. **Echo (Behavioral Fingerprinting)** — Behavioral pattern extraction from communication history, decision logs, and interaction patterns. Custom model architecture for style transfer and decision-pattern recognition.
2. **Serendipity (Anti-Optimization)** — Inverted relevance scoring algorithm, structural similarity detection across distant domains. Novel attention mechanism.
3. **Legacy (Knowledge Crystallization)** — Decision framework extraction, playbook generation from behavioral data. Template-based artifact generation with LLM synthesis.
4. **Weave (Social Graph Intelligence)** — Relationship metabolism tracking, decay detection, contextual reconnection generation. Graph algorithms + LLM synthesis.
5. **Sigil (Threat Radar)** — Multi-source threat aggregation, severity scoring, emergency priority bypass. Integration layer over existing OSINT tools.
6. **Earned Autonomy (Aegis Modules)** — Outcome-based trust adjustment algorithm, per-module per-domain granularity. Extension of NeMo Guardrails.

---

## 6. Legal & Distribution

### Licensing

- **Parent project:** Apache 2.0
- **Individual modules:** Apache 2.0 by default. Modules with GPL dependencies (Forge/NegMAS) are distributed as separate optional packages with their own GPL license.
- **Models:** Only MIT or Apache 2.0 licensed models are included or recommended (DeepSeek, Qwen, Phi, Gemma). Llama is explicitly excluded due to 700M MAU restriction and branding requirements.

### Distribution

- **Primary:** pip install (Python package) + Docker image
- **Desktop:** Tauri-based native app (lighter than Electron, Rust backend)
- **macOS:** Homebrew formula
- **Models:** Downloaded on first run via model registry (like Ollama's pull mechanism)
- **Modules:** Installable individually via `nexus install <module-name>`

### Data Privacy / GDPR Compliance

- All data processing happens locally by default
- No data leaves the machine unless the user explicitly enables Collective (federated learning) or cloud API fallback
- GDPR Article 6 compliance: lawful basis is user consent (local processing) or legitimate interest (on-device only)
- GDPR Article 9: health-related data (if Sentry uses wearable input) requires explicit consent with granular toggles
- Right to erasure (Article 17): `nexus forget` command purges all Engram data. For Collective participants, differential privacy ensures individual contributions cannot be extracted from the federated model.
- EU AI Act: System self-classifies risk level based on enabled modules. High-risk modules (Forge for financial negotiation, Collective for cross-user learning) display appropriate disclosures.

### Monetization (Open Core Model)

- **Free (Apache 2.0):** Full system, all 19 modules, local inference, community support
- **Nexus Pro (paid):** Managed cloud hosting, priority support, pre-trained behavioral models for enterprise roles, advanced Collective analytics dashboard, SSO/SAML integration, SLA guarantees
- **Nexus Enterprise:** On-premise deployment assistance, custom module development, compliance certification support, dedicated account management

---

## 7. Implementation Batches

This project is too large for a single implementation cycle. Decomposed into 5 batches, each producing a usable, testable system.

### Batch 1: Kernel + Foundation (MVP)
- Cortex (router)
- Engram (memory — working + episodic + semantic tiers)
- Pulse (message bus — local MCP)
- Chronicle (audit trail — OpenTelemetry)
- Aegis (basic trust — binary allow/deny per module)
- llama.cpp integration with Qwen 3 8B
- CLI interface for interaction
- `nexus` CLI tool with install/run/status commands
- **Deliverable:** A working local agent that accepts text input, routes to a single built-in "general" module, remembers across sessions, and logs everything.

### Batch 2: Perception + Intelligence Core
- Oracle (anticipatory triggers)
- Sentry (emotional state detection)
- Atlas (knowledge graph via Graphiti)
- Prism (cross-domain synthesis)
- Cipher (trust-scored information)
- **Deliverable:** The system now proactively monitors data sources, builds a world model, synthesizes cross-domain insights, and scores information quality. Still no autonomous actions — observe and suggest only.

### Batch 3: Action Layer
- Wraith (phantom agents)
- Echo (behavioral fingerprinting — initial model)
- Herald (A2A protocol)
- Weave (social graph — initial build)
- Sigil (threat radar — initial sources)
- Aegis upgrade to graduated trust (0-100 scale, outcome-based adjustment)
- **Deliverable:** The system can now take actions in the world — spawn research swarms, communicate with external agents, monitor threats. Earned autonomy is live.

### Batch 4: Advanced Intelligence + Meta
- Specter (adversarial red team)
- Chronos (temporal branching + counter-factual)
- Serendipity (anti-optimization engine)
- Dreamweaver (overnight synthesis)
- Forge (autonomous negotiation)
- Legacy (knowledge crystallization — initial extraction)
- **Deliverable:** The full intelligence stack. Future modeling, adversarial reasoning, overnight deep analysis, engineered serendipity, and autonomous negotiation.

### Batch 5: Network + Platform
- Collective (federated intelligence via Flower)
- NEXUS SITE (branded website)
- Desktop app (Tauri)
- Module marketplace infrastructure
- Documentation and contributor guides
- Legal review and compliance certification
- **Deliverable:** Public launch. The full system is distributable, the community can contribute modules, and federated intelligence creates the network effect.

---

## 8. UI/UX Design Language

### Aesthetic

- **Dark-first:** Near-black and dark navy backgrounds (#0a0e1a, #0d1117, #111827)
- **Luminous accents:** Each module has a signature glow color that pops against the dark surface. Colors are functional — they indicate which module is active/speaking.
- **Icon-driven:** All UI elements use icons (Lucide icon set + custom SVG for module identities). No emojis anywhere in the system.
- **Typography:** Monospace for system/data output (IBM Plex Mono, JetBrains Mono). Clean sans-serif for UI labels (Inter, Manrope). Display type for branding (Syne, similar to Meridian).
- **Information density:** Intelligence-grade density. No wasted whitespace. Think Bloomberg Terminal meets a modern command center — every pixel conveys information.
- **Motion:** Subtle, purposeful. Gentle glows on state changes, smooth transitions between views. No gratuitous animation. Motion indicates system activity (processing indicator, module activation pulse).

### Module Color Map

| Module | Color | Hex |
|--------|-------|-----|
| Cortex | Amber | #f59e0b |
| Oracle | Cyan | #06b6d4 |
| Sentry | Rose | #f43f5e |
| Prism | Violet | #8b5cf6 |
| Specter | Red | #ef4444 |
| Chronos | Blue | #3b82f6 |
| Atlas | Emerald | #10b981 |
| Cipher | Lime | #84cc16 |
| Serendipity | Fuchsia | #d946ef |
| Wraith | Slate | #64748b |
| Echo | Teal | #14b8a6 |
| Herald | Orange | #f97316 |
| Forge | Amber | #d97706 |
| Weave | Pink | #ec4899 |
| Sigil | Red-bright | #dc2626 |
| Dreamweaver | Indigo | #6366f1 |
| Collective | Sky | #0ea5e9 |
| Legacy | Gold | #eab308 |

### Dashboard Layout

The primary interface is a command-center dashboard with:
- **Left sidebar:** Module list with activation status (glowing dot = active, dim = loaded but idle, absent = not loaded)
- **Center panel:** Active module output, conversation stream, and alerts
- **Right panel:** World model summary (Atlas state), Sentry status, upcoming Oracle triggers
- **Bottom bar:** System metrics (RAM usage, active modules, trust levels, Chronicle event count)
- **Top bar:** Search across all of Engram, quick module activation, settings

---

## 9. Success Criteria

### Technical
- Full system runs on 8GB RAM machine with 3+ active modules
- Module hot-loading/unloading without system restart
- Sub-2-second response time for standard queries on local inference
- All actions auditable via Chronicle with cryptographic integrity
- MCP + A2A protocol compliance for all inter-module and external communication

### Product
- User can go from install to first useful interaction in under 5 minutes
- Earned autonomy demonstrably reduces user approval fatigue over 30 days
- Dreamweaver produces at least 1 genuinely useful non-obvious insight per week
- Serendipity surfaces connections the user reports they would not have found themselves
- Echo's behavioral model produces drafts the user accepts without editing >60% of the time after 30 days

### Market
- GitHub: 10k stars within 6 months of public launch
- Active community module contributions within 3 months
- At least 1 enterprise pilot within 12 months
- Featured in major AI/tech publications as a novel approach to agent systems
