"""GET / redirects to the Aurora UI so a bookmark to the server root works."""
from __future__ import annotations

from fastapi.testclient import TestClient

from nexus.api.server import create_app


def test_root_redirects_to_aurora() -> None:
    client = TestClient(create_app())
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (307, 308)
    assert r.headers["location"] == "/aurora"


def test_root_redirect_lands_on_aurora_html() -> None:
    client = TestClient(create_app())
    r = client.get("/", follow_redirects=True)
    assert r.status_code == 200
    assert "aurora" in r.text.lower()
