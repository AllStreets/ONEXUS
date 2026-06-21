"""Local-model switcher — list / switch / persist the active Ollama model."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from nexus.api.server import create_app
from nexus.inference.ollama import OllamaProvider


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    return TestClient(create_app())


def test_provider_set_model_switches_and_returns_previous():
    p = OllamaProvider(model="llama3.1:8b")
    assert p.model == "llama3.1:8b"
    prev = p.set_model("qwen2.5:14b")
    assert prev == "llama3.1:8b"
    assert p.model == "qwen2.5:14b"   # the old model is just deactivated, switch back anytime


def test_models_endpoint_lists_recommended_qwen(client):
    r = client.get("/api/providers/ollama/models")
    assert r.status_code == 200
    body = r.json()
    assert "recommended" in body and "installed" in body and "active" in body
    names = {m["name"] for m in body["recommended"]}
    # Qwen2.5 is the ONEXUS-recommended family for tool-calling fidelity.
    assert "qwen2.5:32b" in names and "qwen2.5:14b" in names
    qwen32 = next(m for m in body["recommended"] if m["name"] == "qwen2.5:32b")
    assert qwen32["recommended"] is True


def test_switch_to_uninstalled_model_is_guarded(client):
    # No Ollama running in the test env → nothing installed → switching is rejected
    # with a clear "add it first" message instead of silently breaking inference.
    r = client.post("/api/providers/ollama/model", json={"model": "qwen2.5:32b"})
    assert r.status_code == 409
    assert "not installed" in r.json()["detail"].lower()


def test_active_model_persists_across_boot(tmp_path, monkeypatch):
    # A persisted choice is honoured when the kernel reconstructs the provider.
    (tmp_path / "active_local_model").write_text("qwen2.5:14b\n")
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    client = TestClient(create_app())
    body = client.get("/api/providers/ollama/models").json()
    assert body["active"] == "qwen2.5:14b"
