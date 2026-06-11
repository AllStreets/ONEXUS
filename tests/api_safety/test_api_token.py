"""Tests for the optional per-instance API token gate (nexus/api/auth.py)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from nexus.api.server import create_app

TOKEN = "test-secret-token-value"


@pytest.fixture
def app_factory(tmp_path, monkeypatch):
    def _make():
        monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
        return TestClient(create_app())

    return _make


def test_no_token_configured_is_open(app_factory, monkeypatch):
    # Default: NEXUS_API_TOKEN unset -> gate is a no-op (loopback trust).
    monkeypatch.delenv("NEXUS_API_TOKEN", raising=False)
    client = app_factory()
    assert client.get("/api/system/health").status_code == 200
    assert client.get("/api/permissions/pending").status_code == 200


def test_health_is_exempt_even_when_token_set(app_factory, monkeypatch):
    monkeypatch.setenv("NEXUS_API_TOKEN", TOKEN)
    client = app_factory()
    # Deploy healthcheck must keep working without a token.
    assert client.get("/api/system/health").status_code == 200


def test_protected_route_401_without_token(app_factory, monkeypatch):
    monkeypatch.setenv("NEXUS_API_TOKEN", TOKEN)
    client = app_factory()
    resp = client.get("/api/permissions/pending")
    assert resp.status_code == 401


def test_protected_route_401_with_wrong_token(app_factory, monkeypatch):
    monkeypatch.setenv("NEXUS_API_TOKEN", TOKEN)
    client = app_factory()
    resp = client.get(
        "/api/permissions/pending",
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert resp.status_code == 401


def test_protected_route_200_with_correct_token(app_factory, monkeypatch):
    monkeypatch.setenv("NEXUS_API_TOKEN", TOKEN)
    client = app_factory()
    resp = client.get(
        "/api/permissions/pending",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert resp.status_code == 200
