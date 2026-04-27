# tests/modules/test_autonomic.py
import pytest
from nexus.modules.autonomic import (
    AutonomicModule, Pattern, DomainTrust, TrustTier,
    ActionProposal, ProposalVerdict,
)


@pytest.fixture
def autonomic():
    return AutonomicModule()


def test_autonomic_attrs(autonomic):
    assert autonomic.name == "autonomic"
    assert autonomic.version == "0.1.0"
    assert autonomic.description


def test_trust_tiers():
    assert TrustTier.OBSERVER.value == 0
    assert TrustTier.SUGGESTER.value == 1
    assert TrustTier.DRAFTER.value == 2
    assert TrustTier.ACTOR.value == 3
    assert TrustTier.STEWARD.value == 4


def test_pattern_dataclass():
    p = Pattern(
        id="p1",
        category="scheduling",
        description="User checks email at 9am",
        trigger_conditions={"time": "09:00"},
        action_template="open email",
        confidence=0.8,
        times_observed=10,
        times_approved=8,
        times_rejected=1,
        last_seen="2026-04-27T09:00:00Z",
    )
    assert p.category == "scheduling"
    assert p.confidence == 0.8


def test_domain_trust_dataclass():
    dt = DomainTrust(
        domain="scheduling",
        trust_score=75,
        successes=20,
        failures=1,
        last_failure="",
        cooldown_until="",
    )
    assert dt.trust_score == 75


def test_trust_tier_from_score():
    assert TrustTier.from_score(0) == TrustTier.OBSERVER
    assert TrustTier.from_score(20) == TrustTier.OBSERVER
    assert TrustTier.from_score(21) == TrustTier.SUGGESTER
    assert TrustTier.from_score(50) == TrustTier.SUGGESTER
    assert TrustTier.from_score(51) == TrustTier.DRAFTER
    assert TrustTier.from_score(75) == TrustTier.DRAFTER
    assert TrustTier.from_score(76) == TrustTier.ACTOR
    assert TrustTier.from_score(90) == TrustTier.ACTOR
    assert TrustTier.from_score(91) == TrustTier.STEWARD
    assert TrustTier.from_score(100) == TrustTier.STEWARD


def test_get_domain_trust_default(autonomic):
    dt = autonomic.get_domain_trust("scheduling")
    assert dt.domain == "scheduling"
    assert dt.trust_score == 0
    assert dt.successes == 0
    assert dt.failures == 0


def test_record_success_increases_trust(autonomic):
    for _ in range(10):
        autonomic.record_success("scheduling")
    dt = autonomic.get_domain_trust("scheduling")
    assert dt.trust_score == 20
    assert dt.successes == 10


def test_record_failure_drops_trust(autonomic):
    for _ in range(20):
        autonomic.record_success("scheduling")
    dt_before = autonomic.get_domain_trust("scheduling")
    assert dt_before.trust_score == 40
    autonomic.record_failure("scheduling")
    dt_after = autonomic.get_domain_trust("scheduling")
    assert dt_after.trust_score == 20
    assert dt_after.failures == 1


def test_cooldown_after_failure(autonomic):
    autonomic.record_failure("scheduling")
    assert autonomic.is_in_cooldown("scheduling")


def test_success_blocked_during_cooldown(autonomic):
    for _ in range(5):
        autonomic.record_success("test_domain")
    autonomic.record_failure("test_domain")
    score_after_fail = autonomic.get_domain_trust("test_domain").trust_score
    autonomic.record_success("test_domain")
    assert autonomic.get_domain_trust("test_domain").trust_score == score_after_fail


def test_observe_event_creates_pattern(autonomic):
    p = autonomic.observe_event("scheduling", "User checks email", {"time": "09:00"})
    assert p.category == "scheduling"
    assert p.times_observed == 1
    assert p.confidence == 0.05


def test_observe_event_increments_existing(autonomic):
    autonomic.observe_event("scheduling", "User checks email", {"time": "09:00"})
    p = autonomic.observe_event("scheduling", "User checks email", {"time": "09:00"})
    assert p.times_observed == 2
    assert p.confidence > 0.05


def test_get_patterns_by_category(autonomic):
    autonomic.observe_event("scheduling", "Email check", {"time": "09:00"})
    autonomic.observe_event("research", "News scan", {"source": "rss"})
    assert len(autonomic.get_patterns("scheduling")) == 1
    assert len(autonomic.get_patterns("research")) == 1
    assert len(autonomic.get_patterns()) == 2


def test_approve_pattern_increases_confidence(autonomic):
    p = autonomic.observe_event("scheduling", "Email check", {"time": "09:00"})
    autonomic.approve_pattern(p.id)
    updated = autonomic.get_patterns("scheduling")[0]
    assert updated.times_approved == 1
    assert updated.confidence > 0.05


def test_reject_pattern_decreases_confidence(autonomic):
    p = autonomic.observe_event("scheduling", "Email check", {"time": "09:00"})
    for _ in range(10):
        autonomic.observe_event("scheduling", "Email check", {"time": "09:00"})
    autonomic.reject_pattern(p.id)
    updated = autonomic.get_patterns("scheduling")[0]
    assert updated.times_rejected == 1


def test_assess_stakes_high_domain(autonomic):
    assert autonomic.assess_stakes("financial", "anything") == "high"


def test_assess_stakes_high_words(autonomic):
    assert autonomic.assess_stakes("misc", "delete all records") == "high"


def test_assess_stakes_medium(autonomic):
    assert autonomic.assess_stakes("misc", "update the schedule") == "medium"


def test_assess_stakes_low(autonomic):
    assert autonomic.assess_stakes("misc", "check status") == "low"


def test_propose_action_rejected_at_observer(autonomic):
    proposal = autonomic.propose_action("scheduling", "Send email", reasoning="routine")
    assert proposal.verdict == ProposalVerdict.REJECTED


def test_propose_action_approved_at_actor(autonomic):
    dt = autonomic.get_domain_trust("scheduling")
    dt.trust_score = 80  # Actor tier
    proposal = autonomic.propose_action("scheduling", "check status", reasoning="routine")
    assert proposal.verdict == ProposalVerdict.APPROVED


def test_propose_action_high_stakes_always_needs_review(autonomic):
    dt = autonomic.get_domain_trust("scheduling")
    dt.trust_score = 95  # Steward tier
    proposal = autonomic.propose_action("scheduling", "delete all records", reasoning="cleanup")
    assert proposal.verdict == ProposalVerdict.NEEDS_REVIEW


def test_propose_action_rejected_during_cooldown(autonomic):
    dt = autonomic.get_domain_trust("scheduling")
    dt.trust_score = 80
    autonomic.record_failure("scheduling")
    proposal = autonomic.propose_action("scheduling", "check status", reasoning="routine")
    assert proposal.verdict == ProposalVerdict.REJECTED


def test_kill_switch(autonomic):
    dt = autonomic.get_domain_trust("scheduling")
    dt.trust_score = 80
    autonomic.observe_event("scheduling", "test", {"a": 1})
    autonomic.kill_switch()
    assert autonomic.get_domain_trust("scheduling").trust_score == 0


@pytest.mark.asyncio
async def test_handle_status(autonomic):
    autonomic.get_domain_trust("scheduling").trust_score = 50
    result = await autonomic.handle("Show autonomic trust status", {"llm": None})
    assert "[Autonomic]" in result
    assert "scheduling" in result


@pytest.mark.asyncio
async def test_handle_kill(autonomic):
    autonomic.get_domain_trust("scheduling").trust_score = 80
    result = await autonomic.handle("kill all autonomous permissions", {"llm": None, "chronicle": None})
    assert "revoked" in result.lower()
    assert autonomic.get_domain_trust("scheduling").trust_score == 0


@pytest.mark.asyncio
async def test_handle_default(autonomic):
    result = await autonomic.handle("hello", {"llm": None})
    assert "[Autonomic]" in result
    assert "Observing" in result
