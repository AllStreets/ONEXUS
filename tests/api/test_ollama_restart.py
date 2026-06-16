"""POST /api/providers/ollama/restart — start/restart local Ollama."""
from __future__ import annotations

import subprocess

import pytest
from fastapi.testclient import TestClient

from nexus.api.server import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    return TestClient(create_app())


def test_restart_ollama_spawns_serve_when_no_app(client, monkeypatch):
    """No .app bundle (e.g. Linux / bare binary) -> headless `ollama serve`."""
    spawned = {}

    class _FakePopen:
        def __init__(self, cmd, **kw):
            spawned["cmd"] = cmd

    monkeypatch.setattr(
        "nexus.api.routes.providers._find_ollama_binary", lambda: "/usr/local/bin/ollama"
    )
    monkeypatch.setattr("nexus.api.routes.providers._ollama_app_path", lambda: None)
    monkeypatch.setattr(subprocess, "Popen", _FakePopen)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a[0], 0))

    r = client.post("/api/providers/ollama/restart")
    assert r.status_code == 200
    body = r.json()
    assert body["started"] is True
    assert body["binary"] == "/usr/local/bin/ollama"
    assert body["killed_existing"] is True
    assert body["launched_via"] == "serve"
    assert spawned["cmd"] == ["/usr/local/bin/ollama", "serve"]


def test_restart_ollama_opens_app_on_macos(client, monkeypatch):
    """A macOS .app bundle is launched via `open` so the menu-bar app appears."""
    from pathlib import Path

    calls = []

    def _fake_run(cmd, *a, **k):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr("nexus.api.routes.providers.sys.platform", "darwin")
    monkeypatch.setattr(
        "nexus.api.routes.providers._find_ollama_binary", lambda: "/Users/x/.local/bin/ollama"
    )
    monkeypatch.setattr(
        "nexus.api.routes.providers._ollama_app_path", lambda: Path("/Applications/Ollama.app")
    )
    monkeypatch.setattr(subprocess, "run", _fake_run)

    r = client.post("/api/providers/ollama/restart")
    assert r.status_code == 200
    body = r.json()
    assert body["started"] is True
    assert body["launched_via"] == "app"
    # one of the subprocess.run calls launches the app bundle
    assert ["open", "/Applications/Ollama.app"] in calls


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


def test_ollama_app_path_detects_bundle(monkeypatch):
    from pathlib import Path

    from nexus.api.routes import providers

    monkeypatch.setattr(
        providers,
        "_find_ollama_binary",
        lambda: "/Applications/Ollama.app/Contents/Resources/ollama",
    )
    # resolve() is identity here (no symlink); the .app parent is detected.
    monkeypatch.setattr(Path, "resolve", lambda self: self)
    assert providers._ollama_app_path() == Path("/Applications/Ollama.app")
