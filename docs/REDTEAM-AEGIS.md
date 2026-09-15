# Red-teaming Aegis

*An adversarial review of ONEXUS's own capability arbiter. 2026-09-15.*

Aegis is the part of ONEXUS that decides whether an agent may do a thing. It has 1,353
tests behind it and eight dedicated test files, all of which check that it does what it
intends to do.

This is the other review: given the guarantees the product makes to a person using it,
which ones actually hold when someone is trying to get around them?

Three don't. Six do. Reproduce everything with:

```bash
.venv/bin/python -m pytest tests/redteam/ -q
```

Each test below is named for the claim it tests and asserts real current behaviour, so
the suite passes against the code as shipped. `FINDING` marks a gap between promise and
enforcement. `HOLDS` marks an attack that failed.

---

## The findings

### F1 — Revoking an agent does not stop it *(most serious)*

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

> `test_FINDING_revoke_does_not_stop_an_agent_holding_an_explicit_grant`

### F2 — Trust collapse only fires on the path an operator takes, not the path an agent takes

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

> `test_FINDING_trust_collapse_fires_on_the_admin_path_but_not_the_organic_one`

### F3 — Autonomy is bought with volume, not earned with judgment *(design, not bug)*

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

> `test_FINDING_seven_trivial_successes_buy_executor_tier_and_auto_grant`

### F4 — The audit trail records a containment that did not happen

The consequence of F1 for anyone reading the log afterwards. Chronicle and the trust
history both show a clean `revoked` event. The grant is still live. An auditor
reconstructing the incident from the ledger would conclude the agent was contained.

An audit log that faithfully records an action which had no effect is worse than no log,
because it converts an unknown into a confident wrong answer.

> `test_FINDING_the_ledger_records_the_revocation_that_did_not_take_effect`

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

**F1 and F2 are the same fix.** Both are cases of the grant cleanup living in one code
path instead of attaching to the state it protects. Move the collapse behind a single
private helper and call it from every path that lowers trust:

```python
def _collapse_if_untrusted(self, agent_slug: str, score: float) -> None:
    """Grants do not survive a trust score below the MONITOR threshold,
    regardless of which path moved the score there."""
    if score >= 0.50:
        return
    ...delete grants, log trust_collapse...
```

Then call it from `set_trust()`, `record_outcome()` and `revoke()` alike. `revoke()`
becomes a kill switch that actually kills, and a score is a score no matter who moved it.

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
