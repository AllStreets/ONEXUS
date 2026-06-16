# ONEXUS — Press Kit

Everything you need to write about, link to, or post ONEXUS. Last updated for the
v2 ("The Missing Minds") launch. Copy freely.

**Repo:** https://github.com/AllStreets/ONEXUS
**Run it:** `onexus serve` → http://localhost:8765

---

## One-liner

ONEXUS is a sovereign agent runtime — a local-first kernel that runs AI agents
entirely on your machine, where every tool call passes a capability gate and
nothing leaves your hardware.

## Boilerplate (three lengths)

**Short (tweet-length):**
> A local-first AI agent runtime. Runs offline on Ollama, gates every tool call,
> and never phones home. Ships with 8,000+ agents. One command to run. Your
> agents, your machine, your rules.

**Medium (one paragraph):**
> ONEXUS is a local-first agent runtime built around least privilege. The model
> runs on your hardware via Ollama, a single component (Aegis) is the only thing
> allowed to touch the network and it gates every tool an agent invokes, and an
> append-only log records every action. It runs air-gapped. It ships with a
> catalog of 8,000+ agents you can summon, and a vanilla-JS UI (Aurora) whose
> shell ambiently shifts color with what the kernel is doing. One command to run,
> fully open source, no account.

**Long (for an article intro):**
> Most "AI agent" platforms are someone else's cloud, running with broad
> permissions over your code and data. ONEXUS inverts that. It is a small kernel
> that runs agents locally: Cortex routes requests, Aegis enforces the network
> boundary and gates every tool call, Engram holds memory and per-workspace
> state, Chronicle is an append-only audit log of every action, and Pulse is the
> internal bus. The default inference provider is Ollama, so with a local model
> nothing leaves your machine — you can pull the network cable and it keeps
> working. Modules start as advisors and earn trust; nothing gets broad authority
> by default. It ships with an 8,000+ agent catalog and Aurora, a build-step-free
> UI whose entire shell recolors with the kernel's live state. It installs and
> runs with a single command and is fully open source with ~1,300 tests.

---

## Key facts

| | |
|---|---|
| What it is | Local-first, least-privilege AI agent runtime (kernel + UI) |
| Sovereignty | Runs offline on Ollama; one component owns network egress; full audit log |
| Kernel | Cortex (routing) · Aegis (gating + egress) · Engram (memory) · Chronicle (audit) · Pulse (bus) |
| Catalog | 8,000+ agents you can browse and summon |
| Trust model | Modules earn trust; advisor (0.30) by default, nothing privileged automatically |
| UI | Aurora — vanilla JS, no build step, ambient color-shifting shell |
| Inference | Ollama by default; optional BYO cloud key (OpenAI / Anthropic) |
| Run | `onexus serve` → localhost:8765 (root redirects to /aurora) |
| Engineering | ~1,300 tests, CI-gated |

## The story / what's novel

"Local-first" usually means just the model. ONEXUS makes the whole boundary
local and enforced: a single network egress point, capability gating on every
tool call, and an append-only audit trail — least privilege as architecture, not
a settings page. The ambient UI is the emotional hook: it turns invisible kernel
state into something you can see at a glance.

## Screenshots

In [`assets/`](assets/).

- **`assets/onexus-aurora.png`** — Aurora at rest: the dark, ambient shell with a
  workspace, the agent sidebar, and the live kernel-activity feed. The hero image
  (best paired with a clip of the shell shifting color).
- **`assets/onexus-providers.png`** — Settings → Providers: live provider health
  (Ollama healthy/green by default) and the in-app "Restart Ollama" control.

## Links

- Repo: https://github.com/AllStreets/ONEXUS
- Quickstart: see the repo README (`onexus serve`)
- Local LLM: https://ollama.com

## Maker quote

> "Every agent framework I tried was someone else's cloud running with broad
> permissions over my code. I wanted the opposite — agents that run on my machine
> with an enforced boundary on what they can touch. The 'only Aegis touches the
> network' rule is a real invariant in the code; I want people to try to break
> it."

## Brand notes

- Name is **ONEXUS** (the GitHub org is `AllStreets/ONEXUS`; the project is also
  referred to as NEXUS internally — use ONEXUS in public copy).
- No emoji; the aesthetic is dark, ambient, calm-confident.
- Lead visuals with the ambient UI; it is the single best hook.
- Be precise about the security model and invite scrutiny — it converts
  skeptics. Never overstate local-model capability; it is a BYO-model trade-off.
