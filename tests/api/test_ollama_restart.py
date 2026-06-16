"""POST /api/providers/ollama/restart — start/restart the local Ollama server."""
from __future__ import annotations

import subprocess

import pytest
from fastapi.testclient import TestClient

from nexus.api.server import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    return TestClient(create_app())


def test_restart_ollama_spawns_when_binary_found(client, monkeypatch):
    spawned = {}

    class _FakePopen:
        def __init__(self, cmd, **kw):
            spawned["cmd"] = cmd

    monkeypatch.setattr(
        "nexus.api.routes.providers._find_ollama_binary", lambda: "/usr/local/bin/ollama"
    )
    monkeypatch.setattr(subprocess, "Popen", _FakePopen)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a[0], 0))

    r = client.post("/api/providers/ollama/restart")
    assert r.status_code == 200
    body = r.json()
    assert body["started"] is True
    assert body["binary"] == "/usr/local/bin/ollama"
    assert body["killed_existing"] is True
    assert spawned["cmd"] == ["/usr/local/bin/ollama", "serve"]


def test_restart_ollama_404_when_binary_missing(client, monkeypatch):
    monkeypatch.setattr("nexus.api.routes.providers._find_ollama_binary", lambda: None)
    r = client.post("/api/providers/ollama/restart")
    assert r.status_code == 404
    assert "ollama binary not found" in r.json()["detail"]


def test_find_ollama_binary_prefers_path(monkeypatch):
    from nexus.api.routes import providers

    monkeypatch.setattr(providers.shutil, "which", lambda name: "/somewhere/ollama")
    monkeypatch.setattr(providers.Path, "exists", lambda self: True)
    assert providers._find_ollama_binary() == "/somewhere/ollama"
