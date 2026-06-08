"""Tests for the Spatial catalog grid backend."""


def test_spatial_agents_returns_unified_list(client):
    r = client.get("/api/spatial/agents")
    assert r.status_code == 200
    body = r.json()
    assert "agents" in body
    assert isinstance(body["agents"], list)


def test_spatial_route_in_app_js(client):
    r = client.get("/aurora/static/app.js")
    assert "renderSpatial" in r.text
    assert "#/spatial" in r.text


def test_spatial_css_present(client):
    r = client.get("/aurora/static/app.css")
    assert ".nx-spatial" in r.text
    assert ".nx-spatial-card" in r.text


def test_spatial_button_in_header(client):
    r = client.get("/aurora")
    assert "nx-spatial-btn" in r.text
