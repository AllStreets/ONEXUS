# NEXUS — The Agentic OS (A Home for Living Agents)

> Working vision, captured 2026-06-16. This is the north star NEXUS grows into:
> **The consumer face of NEXUS + ONEXUS — compose, run, and *watch* swarms of safe, audited AI
> agents working on your behalf, with the kernel's cognition made visible and beautiful. An
> operating system for the agentic age.**
>
> **Release gate:** The ONEXUS marketing campaign does not launch until every word of this vision
> is realized to its fullest. ONEXUS is not "ready" until NEXUS is the experience described here.

This document is meant to be picked up later for full development. It expands every word of the
vision to its fullest potential.

## 1. The one sentence

NEXUS becomes the **operating system for the agentic age**: a local-first, sovereign environment
where anyone can compose, run, trust, and *watch* swarms of AI agents — drawn from the ONEXUS
catalog of thousands of agents — doing real work, with the kernel's reasoning rendered legible and
alive so that you can finally *see the AI think, and trust it.*

## 2. Why this, why NEXUS

NEXUS already is the hard part nobody else has built honestly: a real kernel — Cortex (routing),
Aegis (the single enforced network boundary and capability arbiter), Engram (tiered memory),
Chronicle (append-only audit of every byte and decision), Pulse (the message bus) — plus the
Aurora shell whose color *is* the kernel's mood. ONEXUS-Agents supplies the catalog: thousands of
real, benchmarked agents with MCP adapters. What's missing is the **experience that makes a normal,
powerful human want to live inside it** — the moment a person opens NEXUS, dispatches a swarm,
watches it reason safely, and never wants to go back to a chat box.

The values, sharpened:

- **Trust through legibility.** The entire pitch of the agentic age fails on one word: trust. NEXUS
  wins by making cognition *visible*. You watch Cortex route, Aegis grant or deny, Engram remember,
  Chronicle record. Nothing is hidden. Trust is not asked for; it is *shown*.
- **Sovereign and local-first.** Runs on your machine. Ollama by default — no keys, no rate limits,
  air-gappable. Cloud models optional. Your agents, your data, your audit log.
- **Safe by construction, not by promise.** Aegis is the only module that touches the network, and
  that invariant is lint-enforceable, not aspirational. Every capability is gated, first-use
  prompted, and logged. This is the antidote to "agent frameworks that run arbitrary code and hope."

## 3. The experience — living agents you can watch

You open NEXUS. The Aurora shell is calm violet — low load, focused. You type or speak an intent:
"research the three best open-source vector databases, benchmark them on my dataset, and draft a
recommendation." Cortex lights up and routes; it pulls three agents from the ONEXUS catalog
(browse/search/info already exist as MCP tools), each with a known trust floor and benchmark
pedigree. Aegis steps in: one agent wants network egress to a benchmark host — a first-use prompt
appears, you grant it for this workspace, and the grant is written to Chronicle. The shell shifts to
creative navy as inference deepens. On screen, a **live kernel visualization** (the v2 N1 work,
"Sigil"/live viz) shows the swarm as a constellation of reasoning: routing pings, memory writes,
capability grants and denials flowing in real time. An agent oversteps; Aegis denies it; the shell
flickers alert red for exactly as long as the anomaly lasts, then settles. The work completes; the
recommendation is drafted; the entire run is replayable from Chronicle, decision by decision.

That is the wow: **you did not chat with an AI. You ran a swarm, and you watched it think, and you
trusted it because you could see every move it made.**

## 4. Capabilities, realized to the fullest

**Compose.** A workspace is a living environment with its own agents, memory, file grants, and home
tone. Composing a swarm is as natural as opening apps: pull agents from the ONEXUS catalog, wire
them into a task, and go. Templates for common swarms (research, build, monitor, negotiate).

**Run.** The kernel boots agents the way an OS runs apps — isolated, gated, observable. Local LLM
first; cloud override per task. Workspaces partition everything; Aegis gates first-use capabilities.

**Watch (the headline feature).** The live kernel visualization is the soul of the product. Cortex
routing, Aegis verdicts, Engram memory tiers, Pulse broadcasts — all rendered as a beautiful,
legible, real-time scene. This is interpretability as a *product surface*, not a research paper.
The Aurora mood (calm violet / creative navy / alert red / powered-down grey) is the ambient layer;
the live viz is the detailed layer. Together: the AI made visible.

**Trust.** Capability trust model surfaced to the user: every agent shows its permissions, its
trust floor, its benchmark pedigree (from ONEXUS scoring), and its full Chronicle history. You can
audit, revoke, and replay. Safety is a *feature you can see*, not a disclaimer.

**The catalog as a living library.** ONEXUS's thousands of agents become NEXUS's app store — but
graded, benchmarked, and runnable via MCP adapters, with the runnable-count alive in the UI
(already prototyped in Aurora). Discovery, install, and run are one continuous motion.

**The cognitive modules** (Council, Specter, Oracle, Sentry, Autonomic, etc.) become first-class,
visible participants in the swarm — not hidden internals but characters you can watch and direct.

## 5. AI / kernel architecture (the foundation already exists — extend it)

- **Cortex** gains a richer routing visualization and explainable route decisions.
- **Aegis** stays the single network boundary; surface its verdicts as the trust UI.
- **Engram** memory (working/episodic/semantic + the Atlas temporal knowledge graph) becomes
  visible: you can watch what the swarm remembers and why, with confidence decay shown over time.
- **Chronicle** powers replay: any run reconstructable decision-by-decision.
- **Pulse** drives the live viz: modules emit, the scene renders.
- **ONEXUS catalog tools** (`nexus_agents_browse/search/info`) become the compose layer's backbone.
- **Local-first inference** (Ollama default) is non-negotiable for the sovereignty promise.

## 6. Design language — the kernel made visible

Aurora is already the differentiator; take it all the way:

- **Mood as ambient truth.** The shell's color is the kernel's live state. Keep and refine the
  calm-focus violet / creative navy / alert red / powered-down grey palette.
- **The live kernel scene** as the centerpiece: a real-time, beautiful, legible rendering of
  cognition — radar pings for routing, full-surface veils for emergencies, memory tiers as strata.
- **Sovereign, dark, glowing, alive.** Near-black, glow accents, hairline edges. No emojis — Lucide
  SVG icons and plain Unicode markers only (the existing invariant).
- **No build-step purity where it serves clarity** (Aurora is vanilla JS today) — but the live viz
  may warrant a real rendering layer; choose tools that keep the local-first, no-landlord promise.
- **The Tauri standalone** (.app on macOS/Windows/Linux) is how a real human installs and lives in
  it — a native, sovereign appliance, not a website.

## 7. The road from here

1. **Live kernel visualization (N1)** — the watch experience, end to end. This is the headline.
2. **Compose UX** — pull agents from ONEXUS, wire a swarm, run it, in a few natural motions.
3. **Trust UI** — per-agent permissions, trust floor, benchmark pedigree, Chronicle history,
   revoke/replay.
4. **Catalog-as-app-store** — discovery → install → run as one motion, runnable-count alive.
5. **Cognitive modules as visible characters** in the swarm.
6. **Workspace templates** for common swarms (research/build/monitor/negotiate).
7. **Engram + Chronicle made visible** (memory you can watch, runs you can replay).
8. **Polish the Tauri appliance** into something a non-engineer installs and loves.

## 8. The release gate (important)

**No ONEXUS marketing campaign launches until this vision is realized to its fullest.** ONEXUS the
catalog is the on-ramp; NEXUS the OS is the destination. Marketing a catalog without the
experience that makes it sing would undersell the whole thing. The bar: a person who has never
written code can open NEXUS, dispatch a swarm of catalog agents to do real work, *watch it think*,
trust it because they can see every move, and feel they are holding the future. When that is true,
launch.

---

*Sibling visions: AgentZeus becomes "The Sovereign Cockpit" (your private planetary instrument).
The new flagship "Planetary Commons" (working name TBD) is the public, world-facing instrument that
democratizes situational awareness. Together the three are one constellation — the private cockpit,
the shared OS, and the planetary commons.*
