"""N2.3 — /api/atlas/graph force-layout data route."""


def test_graph_nodes_and_edges(client):
    kernel = client.app.state.kernel
    a = kernel.engram.atlas.observe("acme", "ceo", "Jane", confidence=0.9,
                                    source_ref="chronicle:1")
    b = kernel.engram.atlas.observe("jane", "role", "ceo", confidence=0.8,
                                    source_ref="chronicle:2")
    kernel.engram.atlas.link(a, b, label="mentions")
    r = client.get("/api/atlas/graph")
    assert r.status_code == 200
    body = r.json()
    ids = {n["id"] for n in body["nodes"]}
    assert a in ids and b in ids
    for n in body["nodes"]:
        assert "confidence" in n
    edge_pairs = {(e["src"], e["dst"]) for e in body["edges"]}
    assert (a, b) in edge_pairs


def test_graph_empty_when_no_facts(client):
    r = client.get("/api/atlas/graph")
    assert r.status_code == 200
    body = r.json()
    assert body["nodes"] == []
    assert body["edges"] == []
