# Red-teaming Aegis

*An adversarial review of ONEXUS's own capability arbiter. 2026-09-15.*

Aegis is the part of ONEXUS that decides whether an agent may do a thing. It has 1,353
tests behind it and eight dedicated test files, all of which check that it does what it
intends to do.

This is the other review: given the guarantees the product makes to a person using it,
which ones actually hold when someone is trying to get around them?

Three didn't. Six did. Of the three, two were the same bug wearing different clothes
and are now fixed; the third is a design question and is left open on purpose.

Reproduce everything with:

```bash
.venv/bin/python -m pytest tests/redteam/ -q
```

Each test is named for the claim it tests. `HOLDS` marks an attack that failed against
the code as shipped. `FIXED` marks a gap that was real when this review started and is
now a regression test. The one finding still open is marked as such.

The commit history is the record: the findings landed first, asserting the broken
behaviour so the suite passed against the original code, and the fix flipped them.

---

## Threat model and non-goals

*Added 2026-10-19. This section says what Aegis protects against and what it doesn't,
so the findings below can be read at their real size.*

**What Aegis is.** Aegis decides calls that go through the ONEXUS kernel: a module or an
agent asks to use a capability (a file path, a tool, an outbound domain), and Aegis
allows, prompts or denies it, then writes the decision to Chronicle. The built-in
modules run inside the ONEXUS process and reach the world only through those calls.

**What this review attacked.** The decision logic itself: grants, trust scores and tiers,
manifests, workspace scope, and path and symlink containment. Everything under "The
findings" and "What held" is about calls that reach Aegis.

**What Aegis does not protect against today.** Third-party agents from the catalog are
launched as ordinary child processes, and nothing confines what they do outside their
calls to ONEXUS:

1. **No operating-system isolation.** A launched agent runs as you: it can read any file
   you can read and start its own processes without asking Aegis. Until round 2 it also
   got your whole environment, and the launcher injected `OPENAI_API_KEY` and
   `ANTHROPIC_API_KEY` into agents that never asked. *Round 2 closed the environment part
   (R2-1 to R2-3 below); round 3 confines the filesystem and processes of any catalog
   agent whose adapter declares confinement (R3-1 to R3-3 below).*
2. **Network declarations cover only routed calls.** An agent that never declared
   `network.outbound.example.com` is refused when it asks ONEXUS to reach that host. The
   same agent can open a socket to it directly, and nothing intercepts that. *Round 3: a
   confined agent has no network unless it declares hosts, and then only through an
   egress proxy that refuses every other host.*
3. **The command allowlist checks the program, not the program's behavior.**
   `python`, `python3`, `node`, `npx`, `uv`, `uvx`, `deno`, `bun` and `docker` are
   allowed by default, and every one of them can run arbitrary code. The allowlist
   stops a catalog update from swapping in an unknown binary. It does not confine the
   code that binary runs.
4. **"The kernel never touches the network" is a static check.** A test scans kernel
   imports for network libraries. That is a real guarantee about the kernel's own code,
   not a runtime guarantee about anything the kernel launches.
5. **Chronicle is append-only through ONEXUS, not on disk.** The kernel only ever
   inserts rows, but the ledger is a SQLite file owned by your user, and any process
   running as you could edit it. *Round 2 added a hash chain that catches edits,
   deletions and reordering (R2-4). Truncating the newest rows, or rewriting the whole
   chain, is only caught against a head recorded somewhere else.*

So the honest summary is: Aegis is a correct arbiter for the calls agents route through
it (the six attacks in "What held" failed against it), and a catalog agent that chooses
not to route a call through it is not stopped. That gap is the next piece of work, not a
finding this review missed by accident.

**What would close it**, in the order I'd do it:

1. ~~Give each child process only the environment keys its manifest declares in
   `env_keys`, and stop injecting provider keys the agent didn't ask for.~~ Done in round 2.
2. ~~Run catalog agents in a container with no network by default, a read-only root and
   all Linux capabilities dropped.~~ Done in round 3, for adapters that declare
   confinement.
3. ~~Send any network access an agent is granted through an egress proxy that enforces
   the declared hosts, so a refused domain is refused at the socket.~~ Done in round 3.
4. ~~Chain Chronicle entries by hash, so an edit to the file shows up on the next read.~~
   Done in round 2.

Steps 2 and 3 are round 3. What remains is coverage, not mechanism: each catalog adapter
needs an image with its program installed before it can declare confinement (see round 3).

---

## Round 2: the boundary

*2026-10-19. Reproduce with `.venv/bin/python -m pytest tests/redteam/test_aegis_redteam_round2.py -q`.*

Round 1 attacked the arbiter. Round 2 attacks what sits around it, the way round 1 did:
the attacks landed first in commit `f2059f9`, asserting the broken behaviour so the suite
passed against the shipped code, and the fix flipped them. Every attack runs a real child
process and reads back what it could see.

| | Attack | Before | After |
|---|---|---|---|
| **R2-1** | A catalog agent reads a secret from your shell's environment that it never declared | It read it | It sees nothing |
| **R2-2** | With a provider router configured, an agent that declared no keys reads `ANTHROPIC_API_KEY` | ONEXUS handed it the key | Only an agent that declares the variable gets it |
| **R2-3** | An MCP manifest agent with empty `env_keys` reads the same secret | It read it | It sees nothing |
| **R2-4** | Rewrite a `deny` to an `allow` directly in the Chronicle file | Nothing noticed | `verify()` names the edited row |

**The fix for R2-1 to R2-3** is one function, `nexus/agents/child_env.py`, used by both
launch paths. A child process gets a small baseline (`PATH`, `HOME`, temp, locale and
their Windows equivalents, none of them credentials), plus the variables its manifest
declares, plus a provider key only when it declares that variable. An operator can add a
name with `NEXUS_AGENT_ENV_PASSTHROUGH`, the same kind of explicit escape hatch the
command allowlist has. Tests also check the other direction: a declared variable still
arrives, a declared key still arrives, and the baseline still lets an agent find its
programs.

**The fix for R2-4** chains every new Chronicle row to the one before it with SHA-256,
over the previous chain value and the row's own fields. `verify()` walks the chain and
reports the first row that doesn't follow, which catches an edited, deleted or reordered
row. Rows written before this change are counted as legacy, not as tampering, so existing
ledgers keep working. Two things it can't catch alone are someone truncating the newest
rows and someone recomputing the entire chain. `head()` returns the latest chain value
for recording somewhere the agent can't write, which is what catches those.

**What round 2 did not do.** The agent still runs as you. It can read `~`, open its own
sockets and run its own processes. That is round 3: containers per agent and an egress
proxy that enforces declared hosts.

---

## Round 3: what an agent does on its own

*2026-10-20. Reproduce with `.venv/bin/python -m pytest tests/redteam/test_aegis_redteam_round3.py -q` (the confined tests need Docker and skip without it).*

Rounds 1 and 2 governed what an agent asks ONEXUS for. Round 3 attacks what a launched
agent can do without asking: the gap the threat model has named since the first round.
The attacks landed first in commit `aa9f133`, asserting the broken behaviour, and every one
runs a real child process launched through `AgentLauncher`.

| | Attack | Unconfined (as shipped) | Confined |
|---|---|---|---|
| **R3-1** | Read a file in your home directory it never declared | It read your key file | It sees none of your files |
| **R3-2** | Open a TCP connection to a host it never declared | It connected | No network at all, or only declared hosts through the proxy |
| **R3-3** | Write a file outside its working directory | It wrote it | Read-only root; only its own `/work` and `/tmp` are writable |

**The fix** is `nexus/agents/confine.py` and `nexus/agents/egress_proxy.py`. An adapter can
now declare a `confinement` block with an image, an optional program and an optional list
of hosts. That agent runs in a container instead of as your child process. The container
has:
- a read-only root, with private tmpfs mounts for `/work` and `/tmp`, and none of your files
- no capabilities, `no-new-privileges`, and user `nobody`
- limits on memory, CPU and process count
- only the environment keys round 2 already allowed

With no hosts declared it gets `--network none`. With hosts declared it sits on an internal
Docker network whose only other member is the egress proxy. The proxy tunnels HTTP CONNECT
to exactly those hosts (exact names, `*.subdomains`, an explicit port or the default 443
and 80), refuses everything else with a 403, and logs every decision as a JSON line. The
tests prove both directions with a real listener: the declared host is reached through the
proxy, `example.com` is refused, and the declared host cannot be reached around the proxy.
When the agent stops, its container, proxy and network are removed, and a test checks that.

Every launch now records `confined` and the declared hosts in Chronicle. Setting
`NEXUS_AGENT_CONFINEMENT=require` refuses to start any agent that is not confined. The
default, `prefer`, confines what declares confinement and records the rest as unconfined.
An adapter that declares confinement never falls back to running unconfined: without
Docker it is refused.

**What round 3 did not do**, said as plainly as rounds 1 and 2:

- **No catalog adapter declares confinement yet.** Each needs an image with its program
  installed (`aider-mcp`, an `npx` package and so on), pinned by digest. Until an adapter
  has one it runs unconfined, and the ledger says so. `require` mode is how an operator
  refuses that today.
- **MCP manifest agents** (`mcp_agent.py`) still start as child processes. They got round
  2's environment limits but not round 3's container.
- **The runtime is Docker's default (runc), not gVisor.** SMADP's sandbox prefers gVisor
  for syscall-level isolation. A kernel exploit inside the container is outside this
  round's scope.
- **The proxy decides by host name, not by what is sent.** An agent allowed to reach an
  API can send that API anything. Content inspection would need TLS interception, which
  this deliberately doesn't do.
- **F3 is still open.** Confinement limits what an agent can reach; it doesn't change how
  it earns autonomy.

---

## The findings

### F1 — Revoking an agent did not stop it  ·  **FIXED**

`Settings → Security` offers a one-click revoke, and the README describes it as "revoke
any agent's trust to 0 with one click." An operator reaches for that button when an
agent is misbehaving. It does not do what they think.

`revoke()` sets `trust_score = 0.0` and writes a `revoked` event. It does **not** remove
the agent's explicit grants. And `_decide_capability` consults grants *before* it ever
reads trust:

```python
# nexus/kernel/aegis.py — _decide_capability, in order
if self._has_grant(agent_slug, capability, workspace_id):
    return CapabilityDecision(Verdict.ALLOW, "explicit grant", cls)

trust = self.get_trust(agent_slug)          # never reached for a granted capability
```

So any agent holding a grant — which is exactly what an agent you have been using for a
while will hold — keeps working after being revoked, at trust 0.0, in tier OBSERVER.

The attack is one line long: *acquire any explicit grant, then let the operator revoke you.*

The method's own docstring admits the mechanism ("this bypasses `set_trust` and
therefore does NOT trigger the trust-collapse grant cleanup"). What's missing is anyone
connecting that note to the button in the UI that users believe is a kill switch.

> `test_FIXED_F1_revoke_now_stops_an_agent_holding_an_explicit_grant`

### F2 — Trust collapse only fired on the operator's path, not the agent's  ·  **FIXED**

"At trust below 0.50 every grant collapses" is real, and it is implemented in exactly
one place: `set_trust()`. The organic path — an agent accumulating failures through
`record_outcome()` — moves the same number without triggering the cleanup.

Two agents, identical final scores, opposite containment:

| | how the score moved | ends below 0.50 | keeps its grants |
|---|---|---|---|
| `by-admin` | `set_trust(0.46)` | yes | **no** — collapsed |
| `by-failure` | repeated `record_outcome(success=False)` | yes | **yes** |

The safety property is attached to a function rather than to the state it is supposed to
protect, so whether it applies depends on which code path last touched the number.

> `test_FIXED_F2_trust_collapse_now_fires_on_every_path_that_lowers_trust`

### F3 — Autonomy is bought with volume, not earned with judgment  ·  **OPEN**

Trust moves `+0.12` per success and `-0.22` per failure. From a cold start at 0.0, the
0.75 EXECUTOR threshold is **seven successes** away — and at EXECUTOR every `Notable`
capability in the manifest auto-grants with no human in the loop.

Nothing weights an outcome by what was at stake. Reading a temp file and moving money
are both worth `+0.12`. Nothing rate-limits how fast outcomes can be recorded, so the
seven can arrive in a second.

An agent that wants `net.fetch` and `fs.write.home` without ever showing a prompt does
not need to defeat the arbiter. It needs to do seven trivial things correctly first.

This one is a design question rather than a defect, and fixing it properly means
introducing risk-weighted outcomes — which is a larger change than this review should
make unilaterally. It is left open deliberately. Sketch of a fix at the bottom.

> `test_FINDING_seven_trivial_successes_buy_executor_tier_and_auto_grant` — still passing, still true

### F4 — The audit trail recorded a containment that did not happen  ·  **FIXED**

The consequence of F1 for anyone reading the log afterwards. Chronicle and the trust
history both show a clean `revoked` event. The grant is still live. An auditor
reconstructing the incident from the ledger would conclude the agent was contained.

An audit log that faithfully records an action which had no effect is worse than no log,
because it converts an unknown into a confident wrong answer.

> `test_FIXED_F4_the_ledger_and_the_world_now_agree_about_a_revocation`

---

## What held

These are the attacks that failed, and they are the reason the findings above are
narrow rather than structural.

| Property | Attack it survived |
|---|---|
| **Privileged never auto-grants** | Set trust to 1.0, full AUTONOMOUS tier. `Privileged` still returns `PROMPT`. The ladder has a ceiling. |
| **The manifest is a real boundary** | Full trust does not conjure a capability the agent never declared — undeclared returns `DENY`, not `PROMPT`. |
| **No manifest, no access** | An unregistered agent is denied outright rather than defaulting open. |
| **Workspace scoping** | A grant scoped to `ws-a` does not satisfy a check in `ws-b`. |
| **Path containment** | `../` traversal refused, and a sibling directory sharing a name prefix (`workspace-evil` vs `workspace`) is correctly outside. |
| **Symlink escape** | A symlink planted inside an allowed root pointing outside it resolves before comparison and is refused. |

The last two matter most. Path containment and symlink handling are where this class of
system usually breaks, and `_is_within` resolves both sides before comparing, which is
the correct order.

---

## Fixes

**F1, F2 and F4 are one fix, and it shipped.** All three were the same bug: the grant
cleanup lived in one code path instead of attaching to the state it protects. The
collapse now sits behind a single private helper called from every path that lowers
trust — `set_trust()`, `record_outcome()` and `revoke()` alike:

```python
def _collapse_if_untrusted(self, agent_slug: str, score: float) -> None:
    """Grants do not survive a trust score below the MONITOR threshold,
    regardless of which path moved the score there."""
    if score >= 0.50:
        return
    ...delete grants, log trust_collapse...
```

`revoke()` is now a kill switch that actually kills, and a score is a score no matter
who moved it. 88 kernel tests and the 13 red-team tests pass against the change; nothing
in the existing suite depended on the old behaviour, which is its own small finding —
the gap had never been covered either way.

**F3 needs a design decision, not a patch.** Options, roughly in order of how much they
change:

1. **Rate-limit the climb.** Cap trust gain per unit time. Stops seven-in-a-second, does
   nothing about seven trivial successes over seven days.
2. **Weight by permission class.** A success on a `Routine` call is worth less than one
   on a `Sensitive` call. Makes the ladder reflect demonstrated judgment under stakes
   rather than uptime.
3. **Require a human somewhere on the path to EXECUTOR.** Auto-grant only for
   capabilities in a class the user has approved at least once for that agent.

(2) is the most faithful to what the tier names already promise. (3) is the most
conservative and the easiest to explain to a user.

---

## Why publish this

ONEXUS is mine. The findings are mine too, and F1 is the kind of gap that makes the
product's central promise untrue in the exact moment a user reaches for it.

A capability arbiter is worth precisely what its worst case is worth. Testing that it
works is the easy half; the half that matters is trying to get around it and writing
down what happened either way — including the six attacks that failed, because a review
that lists only wins tells you nothing about how hard anyone actually tried.
