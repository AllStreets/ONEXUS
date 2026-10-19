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

1. **No operating-system isolation.** `nexus/agents/launcher.py` starts an agent with
   `subprocess.Popen(..., env=dict(os.environ))`, and when a provider router is
   configured it adds `OPENAI_API_KEY` and `ANTHROPIC_API_KEY` to that environment.
   `nexus/agents/mcp_agent.py` also passes the whole `os.environ`. A launched agent runs
   as you: it can read any file you can read, read every environment variable including
   those keys, and start its own processes, without asking Aegis.
2. **Network declarations cover only routed calls.** An agent that never declared
   `network.outbound.example.com` is refused when it asks ONEXUS to reach that host. The
   same agent can open a socket to it directly, and nothing intercepts that.
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
   running as you could edit it. There is no hash chain yet to make tampering visible.

So the honest summary is: Aegis is a correct arbiter for the calls agents route through
it (the six attacks in "What held" failed against it), and a catalog agent that chooses
not to route a call through it is not stopped. That gap is the next piece of work, not a
finding this review missed by accident.

**What would close it**, in the order I'd do it:

1. Give each child process only the environment keys its manifest declares in
   `env_keys`, and stop injecting provider keys the agent didn't ask for.
2. Run catalog agents in a container with no network by default, a read-only root and
   all Linux capabilities dropped. [SMADP's sandbox](https://github.com/AllStreets/SMADP)
   already uses that profile for its own runs.
3. Send any network access an agent is granted through an egress proxy that enforces
   the declared hosts, so a refused domain is refused at the socket.
4. Chain Chronicle entries by hash, so an edit to the file shows up on the next read.

Round 2 of this review will attack that boundary the same way round 1 attacked the
arbiter: write the attacks first (an agent reading `~` directly, opening a raw socket,
reading a key from its environment), watch them succeed against the current code, then
fix.

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
