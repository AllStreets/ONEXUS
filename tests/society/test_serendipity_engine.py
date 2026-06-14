"""Unit tests for the Serendipity anti-optimization engine (pure)."""
from __future__ import annotations

from nexus.society.serendipity import Candidate, SerendipityEngine


def _candidates():
    return [
        Candidate(id="a", text="obvious top hit", relevance=0.95, novelty=0.1,
                  source="atlas:a"),
        Candidate(id="b", text="off-axis bright", relevance=0.2, novelty=0.9,
                  source="atlas:b"),
        Candidate(id="c", text="quiet outlier", relevance=0.3, novelty=0.8,
                  source="atlas:c"),
        Candidate(id="d", text="dull near-miss", relevance=0.4, novelty=0.2,
                  source="atlas:d"),
    ]


def test_surfaces_high_novelty_under_ceiling():
    eng = SerendipityEngine(relevance_ceiling=0.5)
    out = eng.discover(_candidates(), budget=2)
    ids = [c["id"] for c in out]
    assert ids == ["b", "c"]  # highest novelty under ceiling, excludes 0.95 hit
    assert all(c["id"] != "a" for c in out)


def test_respects_budget():
    eng = SerendipityEngine(relevance_ceiling=0.5)
    out = eng.discover(_candidates(), budget=1)
    assert len(out) == 1
    assert out[0]["id"] == "b"


def test_every_item_cites_a_source():
    eng = SerendipityEngine(relevance_ceiling=0.5)
    out = eng.discover(_candidates(), budget=3)
    assert all(c["source"] for c in out)


def test_empty_when_nothing_below_ceiling():
    eng = SerendipityEngine(relevance_ceiling=0.1)
    out = eng.discover(_candidates(), budget=3)
    assert out == []
