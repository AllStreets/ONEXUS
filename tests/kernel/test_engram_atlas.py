"""N1.2 — Atlas temporal knowledge graph in Engram's semantic tier."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from nexus.kernel.engram import Engram


def _engram(tmp_path):
    e = Engram(tmp_path / "engram.db")
    e.init_db()
    return e


T0 = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)


def test_observe_and_beliefs_with_citation(tmp_path):
    e = _engram(tmp_path)
    fid = e.atlas.observe("acme", "ceo", "Jane Doe", confidence=0.9,
                          source_ref="chronicle:abc123", now=T0)
    beliefs = e.atlas.beliefs("acme", now=T0)
    assert len(beliefs) == 1
    b = beliefs[0]
    assert b["id"] == fid
    assert b["object"] == "Jane Doe"
    assert b["source_ref"] == "chronicle:abc123"
    assert abs(b["confidence"] - 0.9) < 1e-9


def test_confidence_decays_deterministically_at_read_time(tmp_path):
    e = _engram(tmp_path)
    e.atlas.set_half_life("default", 24.0)
    e.atlas.observe("acme", "hq", "berlin", confidence=0.8, now=T0)
    b = e.atlas.beliefs("acme", now=T0 + timedelta(hours=24))[0]
    assert abs(b["confidence"] - 0.4) < 1e-6      # one half-life
    assert b["stored_confidence"] == 0.8           # storage untouched


def test_reconfirmation_restores_confidence(tmp_path):
    e = _engram(tmp_path)
    e.atlas.set_half_life("default", 24.0)
    fid = e.atlas.observe("acme", "hq", "berlin", confidence=0.8, now=T0)
    later = T0 + timedelta(hours=24)
    fid2 = e.atlas.observe("acme", "hq", "berlin", confidence=0.8, now=later)
    assert fid2 == fid                              # same fact, not a duplicate
    beliefs = e.atlas.beliefs("acme", now=later)
    assert len(beliefs) == 1
    assert abs(beliefs[0]["confidence"] - 0.8) < 1e-9
    assert beliefs[0]["last_confirmed_at"] == later.isoformat()


def test_contradictory_facts_coexist_with_competing_confidence(tmp_path):
    e = _engram(tmp_path)
    e.atlas.observe("acme", "hq", "berlin", confidence=0.9, now=T0)
    e.atlas.observe("acme", "hq", "munich", confidence=0.6, now=T0)
    beliefs = e.atlas.beliefs("acme", relation="hq", now=T0)
    assert [b["object"] for b in beliefs] == ["berlin", "munich"]  # sorted by confidence
    assert len(beliefs) == 2


def test_half_life_is_per_fact_class(tmp_path):
    e = _engram(tmp_path)
    e.atlas.set_half_life("volatile", 1.0)
    e.atlas.observe("market", "mood", "risk-on", confidence=0.8,
                    fact_class="volatile", now=T0)
    e.atlas.observe("market", "currency", "eur", confidence=0.8, now=T0)
    later = T0 + timedelta(hours=2)
    by_rel = {b["relation"]: b for b in e.atlas.beliefs("market", now=later)}
    assert abs(by_rel["mood"]["confidence"] - 0.2) < 1e-6    # two half-lives
    assert by_rel["currency"]["confidence"] > 0.79           # barely decayed


def test_edges_link_related_facts(tmp_path):
    e = _engram(tmp_path)
    a = e.atlas.observe("acme", "ceo", "Jane Doe", now=T0)
    b = e.atlas.observe("jane doe", "based_in", "berlin", now=T0)
    e.atlas.link(a, b, label="person")
    neigh = e.atlas.neighbors(a, now=T0)
    assert len(neigh) == 1
    assert neigh[0]["id"] == b
    assert neigh[0]["label"] == "person"
