"""Unit tests for the Herald negotiation state machine (pure)."""
from __future__ import annotations

import pytest

from nexus.society.herald import (
    Forge, IllegalTransition, NegotiationState, NegotiationStatus,
)


def _offer():
    return Forge.offer(
        initiator="agent-a", responder="agent-b",
        capability="engram.write.workspace", workspace_id="ws1",
        terms={"scope": "summaries", "ttl_s": 600}, value=0.4,
    )


def test_offer_opens_negotiation():
    neg = NegotiationState.start(_offer())
    assert neg.status is NegotiationStatus.OPEN
    assert neg.capability == "engram.write.workspace"
    assert len(neg.transcript) == 1
    assert neg.transcript[0]["kind"] == "offer"


def test_counter_moves_to_countered_and_records():
    neg = NegotiationState.start(_offer())
    neg.counter(Forge.counter(by="agent-b", terms={"ttl_s": 300}, value=0.3))
    assert neg.status is NegotiationStatus.COUNTERED
    assert neg.transcript[-1]["kind"] == "counter"
    assert neg.current_value == 0.3


def test_accept_then_commit_is_terminal():
    neg = NegotiationState.start(_offer())
    neg.accept(by="agent-b")
    assert neg.status is NegotiationStatus.ACCEPTED
    token = neg.commit(by="agent-a")
    assert neg.status is NegotiationStatus.COMMITTED
    assert token.capability == "engram.write.workspace"
    assert token.workspace_id == "ws1"


def test_reject_is_terminal():
    neg = NegotiationState.start(_offer())
    neg.reject(by="agent-b", reason="terms too broad")
    assert neg.status is NegotiationStatus.REJECTED
    assert neg.transcript[-1]["reason"] == "terms too broad"


def test_cannot_commit_without_accept():
    neg = NegotiationState.start(_offer())
    with pytest.raises(IllegalTransition):
        neg.commit(by="agent-a")


def test_cannot_act_after_terminal():
    neg = NegotiationState.start(_offer())
    neg.reject(by="agent-b", reason="no")
    with pytest.raises(IllegalTransition):
        neg.counter(Forge.counter(by="agent-b", terms={}, value=0.1))


def test_auto_accept_only_when_counter_dominates():
    neg = NegotiationState.start(_offer())  # value 0.4
    neg.counter(Forge.counter(by="agent-b", terms={"ttl_s": 300}, value=0.3))
    assert neg.counter_dominates() is True
    neg2 = NegotiationState.start(_offer())
    neg2.counter(Forge.counter(by="agent-b", terms={"ttl_s": 1200}, value=0.9))
    assert neg2.counter_dominates() is False
