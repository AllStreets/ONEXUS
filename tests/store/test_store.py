"""The agent store: verified recipes in, confined MCP servers out.

Unit tests use a fake docker and a fake handshake. The end-to-end test at the bottom
builds a real published server from a recipe, installs it, launches it through
AgentLauncher and calls one of its tools; it needs Docker and network and runs when
NEXUS_STORE_DOCKER=1.
"""
from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import time
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from nexus.agents.catalog import AgentCatalog
from nexus.agents.launcher import AgentLauncher, AgentLaunchError
from nexus.api.routes.store import router
from nexus.store.adapters import StoreAwareCatalog
from nexus.store.installer import InstallError, Installer
from nexus.store.recipes import RecipeIndex, is_installable
from nexus.store.state import InstallRecord, StoreState

NODE_BASE = "node:22-slim@sha256:c3de60bf2f9dd0ac6370e6117950ff62d6e339527e7472301c9c78a017978392"


def npm_recipe(slug="everything", ok=True, env=None):
    return {
        "slug": slug, "recipe_version": 1,
        "source": {"repo": "modelcontextprotocol/servers", "commit": "abc"},
        "derived_from": "readme-config",
        "install": {"kind": "npm", "package": "@modelcontextprotocol/server-everything", "version": "2.0.0"},
        "command": ["mcp-server-everything"], "args": [], "transport": "stdio",
        "env": env or [], "license": "MIT",
        "hosts": {"proposed": ["api.example-service.com"], "evidence": {"api.example-service.com": ["dist/x.js:1"]}},
        "dockerfile": (f"FROM {NODE_BASE}\nENV OPENSSL_armcap=0x1fff\n"
                       "RUN npm install -g --omit=dev --no-fund --no-audit @modelcontextprotocol/server-everything@2.0.0 "
                       "&& npm cache clean --force\nUSER 65534:65534\n"),
        "verified": {"at": "2026-10-21T00:00:00Z", "ok": ok, "stage": "done" if ok else "start",
                     "tools": ["echo", "add"] if ok else []},
    }


def make_catalog(tmp_path: Path, recipes: list[dict]) -> Path:
    root = tmp_path / "ONEXUS-Agents"
    (root / "catalog" / "dev-tools").mkdir(parents=True)
    (root / "recipes").mkdir()
    for r in recipes:
        (root / "recipes" / f"{r['slug']}.json").write_text(json.dumps(r))
        (root / "catalog" / "dev-tools" / f"{r['slug']}.json").write_text(json.dumps({
            "slug": r["slug"], "name": r["slug"].title(), "tagline": "A test server", "category": "dev-tools",
            "license": "MIT", "runnable": False, "source": {"github": r["source"]["repo"]},
            "metrics": {"stars": 10}}))
    (root / "recipes" / "_summary.json").write_text(json.dumps({"recipes": len(recipes)}))
    return root


class FakeDocker:
    def __init__(self, fail_build=False):
        self.calls, self.fail_build = [], fail_build

    def __call__(self, *argv, input=None, timeout=0):
        self.calls.append(argv)
        rc = 1 if (self.fail_build and argv[0] == "build") else 0
        return subprocess.CompletedProcess(argv, rc, stdout="", stderr="boom" if rc else "")


def wait(installer, job):
    for _ in range(200):
        if installer.job(job.id).state != "running":
            return installer.job(job.id)
        time.sleep(0.02)
    raise AssertionError("install didn't finish")


# --- recipes ----------------------------------------------------------------------------


def test_only_verified_recipes_with_a_dockerfile_are_installable(tmp_path):
    root = make_catalog(tmp_path, [npm_recipe("good"), npm_recipe("bad", ok=False)])
    idx = RecipeIndex(root)
    assert [r["slug"] for r in idx.installable()] == ["good"]
    r = npm_recipe("nodf")
    r.pop("dockerfile")
    assert not is_installable(r)
    assert RecipeIndex(root / "catalog").get("good")  # either root works


# --- state and secrets ------------------------------------------------------------------


def test_secrets_are_kept_apart_and_private(tmp_path):
    st = StoreState(tmp_path)
    rec = InstallRecord(slug="a", image="img", kind="npm", version="1", env_names=["API_KEY"])
    st.save(rec, {"API_KEY": "sk-very-secret"})
    record_text = (st.root / "installed" / "a.json").read_text()
    assert "sk-very-secret" not in record_text
    mode = stat.S_IMODE((st.root / "secrets.json").stat().st_mode)
    assert mode == 0o600
    assert st.secrets_for("a") == {"API_KEY": "sk-very-secret"}
    assert st.remove("a") and st.get("a") is None and st.secrets_for("a") == {}


def test_state_rejects_path_like_slugs(tmp_path):
    st = StoreState(tmp_path)
    assert st.get("../../etc/passwd") is None
    with pytest.raises(ValueError):
        st.save(InstallRecord(slug="../x", image="i", kind="npm", version="1"), {})


# --- installer --------------------------------------------------------------------------


def installer(tmp_path, recipes, docker=None, check=None):
    root = make_catalog(tmp_path, recipes)
    return Installer(StoreState(tmp_path / "data"), RecipeIndex(root), docker=docker or FakeDocker(),
                     check=check or (lambda r, img, env: {"ok": True, "tools": ["add", "echo"]}))


def test_install_builds_checks_and_records(tmp_path):
    docker = FakeDocker()
    inst = installer(tmp_path, [npm_recipe()], docker=docker)
    job = wait(inst, inst.start("everything", ["api.example-service.com"], {}))
    assert job.state == "done", job.error
    assert [s["status"] for s in job.public()["steps"]] == ["done", "done", "done"]
    assert docker.calls[0][0] == "build"
    rec = inst.state.get("everything")
    assert rec.image == "onexus-store/everything:2.0.0" and rec.tools == ["add", "echo"]
    assert rec.hosts == ["api.example-service.com"] and rec.command == ["mcp-server-everything"]


def test_a_failed_check_records_nothing_and_removes_the_image(tmp_path):
    docker = FakeDocker()
    inst = installer(tmp_path, [npm_recipe()], docker=docker,
                     check=lambda r, i, e: {"ok": False, "reason": "the server exited with code 1"})
    job = wait(inst, inst.start("everything", [], {}))
    assert job.state == "failed" and "didn't start" in job.error
    assert [s["status"] for s in job.public()["steps"]] == ["done", "failed", "pending"]
    assert inst.state.get("everything") is None
    assert ("rmi", "-f", "onexus-store/everything:2.0.0") in docker.calls


def test_a_failed_build_is_reported(tmp_path):
    inst = installer(tmp_path, [npm_recipe()], docker=FakeDocker(fail_build=True))
    job = wait(inst, inst.start("everything", [], {}))
    assert job.state == "failed" and "build failed" in job.error


def test_install_requires_declared_keys_and_rejects_others(tmp_path):
    r = npm_recipe(env=[{"name": "API_KEY", "required": True, "secret": True}])
    inst = installer(tmp_path, [r])
    with pytest.raises(InstallError, match="needs: API_KEY"):
        inst.start("everything", [], {})
    with pytest.raises(InstallError, match="doesn't declare"):
        inst.start("everything", [], {"API_KEY": "k", "OTHER": "x"})
    with pytest.raises(InstallError, match="not host names"):
        inst.start("everything", ["http://evil/path"], {"API_KEY": "k"})


def test_unverified_recipes_cannot_be_installed(tmp_path):
    inst = installer(tmp_path, [npm_recipe("bad", ok=False)])
    with pytest.raises(InstallError, match="no verified recipe"):
        inst.start("bad", [], {})


# --- launching through the store --------------------------------------------------------


class _Recorder:
    def __init__(self):
        self.events = []

    def set_policy(self, *a, **k): ...

    def log(self, *a, **k):
        self.events.append((a, k))


class _Kernel:
    def __init__(self):
        self.provider_router = None
        self.aegis = _Recorder()
        self.chronicle = _Recorder()


def test_an_installed_agent_is_described_as_a_confined_adapter(tmp_path):
    root = make_catalog(tmp_path, [npm_recipe()])
    st = StoreState(tmp_path / "data")
    st.save(InstallRecord(slug="everything", image="onexus-store/everything:2.0.0", kind="npm", version="2.0.0",
                          command=["mcp-server-everything"], env_names=["API_KEY"], hosts=["api.x.com"],
                          tools=["echo"]), {"API_KEY": "k"})
    cat = StoreAwareCatalog(AgentCatalog(root), st)
    entry = cat.get_agent("everything")
    assert entry.runnable  # the catalog said false; the store installed it
    ad = cat.load_adapter(entry)
    assert ad.confinement == {"image": "onexus-store/everything:2.0.0", "command": "mcp-server-everything",
                              "hosts": ["api.x.com"], "entrypoint": False}
    assert ad.secrets == {"API_KEY": "k"} and "k" not in repr(ad)
    assert ad.capabilities == {"tools": ["echo"]}


def test_a_confined_store_command_skips_the_host_allowlist_but_off_mode_does_not(tmp_path, monkeypatch):
    root = make_catalog(tmp_path, [npm_recipe()])
    st = StoreState(tmp_path / "data")
    st.save(InstallRecord(slug="everything", image="img", kind="npm", version="1",
                          command=["mcp-server-everything"]), {})
    launcher = AgentLauncher(catalog=StoreAwareCatalog(AgentCatalog(root), st), kernel=_Kernel())
    monkeypatch.setenv("NEXUS_AGENT_CONFINEMENT", "off")
    with pytest.raises(AgentLaunchError, match="allowlist"):
        launcher.launch("everything")


# --- API --------------------------------------------------------------------------------


def api(tmp_path, recipes, **kw):
    inst = installer(tmp_path, recipes, **kw)
    app = FastAPI()
    app.include_router(router)
    app.state.store_installer = inst
    app.state.agent_catalog = AgentCatalog(tmp_path / "ONEXUS-Agents")
    app.state.agent_launcher = None
    return TestClient(app), inst


def test_api_lists_details_installs_and_removes(tmp_path):
    client, inst = api(tmp_path, [npm_recipe(env=[{"name": "API_KEY", "required": True, "secret": True}]),
                                  npm_recipe("bad", ok=False)])
    listing = client.get("/api/store/agents").json()
    assert [a["slug"] for a in listing["agents"]] == ["everything"]
    assert listing["agents"][0]["needs_keys"] == ["API_KEY"] and listing["agents"][0]["tools"] == ["echo", "add"]
    detail = client.get("/api/store/agents/everything").json()
    assert detail["installable"] and detail["hosts"]["proposed"] == ["api.example-service.com"]
    assert client.post("/api/store/agents/everything/install", json={"hosts": [], "env": {}}).status_code == 400
    r = client.post("/api/store/agents/everything/install", json={"hosts": [], "env": {"API_KEY": "sk-secret"}})
    assert r.status_code == 202 and "sk-secret" not in r.text
    job = wait(inst, inst.job(r.json()["id"]))
    status = client.get(f"/api/store/jobs/{job.id}")
    assert status.json()["state"] == "done" and "sk-secret" not in status.text
    detail = client.get("/api/store/agents/everything")
    assert detail.json()["record"]["keys_given"] == ["API_KEY"] and "sk-secret" not in detail.text
    assert client.put("/api/store/agents/everything/hosts", json={"hosts": ["api.github.com"]}).json()["hosts"] == ["api.github.com"]
    assert client.put("/api/store/agents/everything/hosts", json={"hosts": ["not a host"]}).status_code == 400
    assert client.delete("/api/store/agents/everything").json()["removed"]
    assert client.delete("/api/store/agents/everything").status_code == 404


def test_api_without_a_catalog_says_why():
    app = FastAPI()
    app.include_router(router)
    r = TestClient(app).get("/api/store/agents")
    assert r.status_code == 503 and "catalog" in r.json()["detail"]


# --- end to end -------------------------------------------------------------------------


@pytest.mark.skipif(os.environ.get("NEXUS_STORE_DOCKER") != "1" or not shutil.which("docker"),
                    reason="set NEXUS_STORE_DOCKER=1 (needs Docker and network)")
def test_install_launch_and_call_a_real_server(tmp_path):
    root = make_catalog(tmp_path, [npm_recipe()])
    st = StoreState(tmp_path / "data")
    inst = Installer(st, RecipeIndex(root))
    job = inst.start("everything", [], {})
    for _ in range(900):
        if inst.job(job.id).state != "running":
            break
        time.sleep(1)
    job = inst.job(job.id)
    assert job.state == "done", job.public()
    assert "echo" in job.tools
    kernel = _Kernel()
    launcher = AgentLauncher(catalog=StoreAwareCatalog(AgentCatalog(root), st), kernel=kernel)
    agent = launcher.launch("everything")
    try:
        assert agent.confined
        p = agent.process
        def send(m):
            p.stdin.write((json.dumps(m) + "\n").encode())
            p.stdin.flush()
        def read(rid):
            while True:
                m = json.loads(p.stdout.readline())
                if m.get("id") == rid:
                    return m["result"]
        send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}})
        read(1)
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        send({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "echo", "arguments": {"message": "store works"}}})
        res = read(2)
        assert "store works" in json.dumps(res)
        launched = next(a[2] for a, _ in kernel.chronicle.events if a[:2] == ("agents", "agent_launched"))
        assert launched["confined"] is True
    finally:
        launcher.stop("everything")
        inst.uninstall("everything")
