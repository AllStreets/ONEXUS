"""Tests for /api/codebases — workspace codebase roots (register/browse/read)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from nexus.api.server import create_app


WS = "hello-world"  # seeded by the workspaces router on first run


@pytest.fixture(autouse=True)
def _seed_workspaces(client):
    # Workspace seeding is lazy — the workspaces router creates the
    # hello-world workspace on its first request.
    client.get("/api/workspaces")


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_repo(tmp_path, name="repo"):
    repo = tmp_path / name
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "main.py").write_text("print('hello')\n")
    (repo / "README.md").write_text("# Repo\n")
    return repo


def _register(client, repo, workspace_id=WS, name=None):
    body = {"workspace_id": workspace_id, "path": str(repo)}
    if name:
        body["name"] = name
    return client.post("/api/codebases", json=body)


# ── registration ─────────────────────────────────────────────────────────────

def test_register_codebase(client, tmp_path):
    repo = _make_repo(tmp_path)
    r = _register(client, repo, name="My Repo")
    assert r.status_code == 200
    body = r.json()
    assert body["workspace_id"] == WS
    assert body["path"] == str(repo.resolve())
    assert body["name"] == "My Repo"
    assert body["id"]
    assert body["registered_at"]

    # Listed, scoped to the workspace.
    r2 = client.get("/api/codebases", params={"workspace_id": WS})
    assert r2.status_code == 200
    assert [c["id"] for c in r2.json()["codebases"]] == [body["id"]]


def test_register_is_idempotent_per_path(client, tmp_path):
    repo = _make_repo(tmp_path)
    id1 = _register(client, repo).json()["id"]
    id2 = _register(client, repo).json()["id"]
    assert id1 == id2
    assert len(client.get("/api/codebases").json()["codebases"]) == 1


def test_register_relative_path_400(client):
    r = client.post("/api/codebases", json={"workspace_id": WS, "path": "src/app"})
    assert r.status_code == 400


def test_register_missing_path_400(client, tmp_path):
    r = _register(client, tmp_path / "does-not-exist")
    assert r.status_code == 400


def test_register_file_not_dir_400(client, tmp_path):
    f = tmp_path / "afile.txt"
    f.write_text("not a dir")
    r = _register(client, f)
    assert r.status_code == 400


def test_register_unknown_workspace_404(client, tmp_path):
    repo = _make_repo(tmp_path)
    r = _register(client, repo, workspace_id="no-such-ws")
    assert r.status_code == 404


def test_register_logs_to_chronicle(client, tmp_path):
    repo = _make_repo(tmp_path)
    cb_id = _register(client, repo).json()["id"]
    entries = client.get("/api/chronicle", params={"source": "codebases"}).json()["entries"]
    reg = [e for e in entries if e["action"] == "registered"]
    assert reg and reg[0]["payload"]["codebase_id"] == cb_id


def test_registrations_persist_across_app_instances(client, tmp_path):
    repo = _make_repo(tmp_path)
    cb_id = _register(client, repo).json()["id"]

    # Same NEXUS_DATA_DIR, fresh app — the registration must survive.
    client2 = TestClient(create_app())
    listed = client2.get("/api/codebases", params={"workspace_id": WS}).json()["codebases"]
    assert [c["id"] for c in listed] == [cb_id]


def test_list_scoped_by_workspace(client, tmp_path):
    client.post("/api/workspaces", json={
        "workspace_id": "ws-beta", "name": "Beta", "tone": "teal",
    })
    repo_a = _make_repo(tmp_path, "repo-a")
    repo_b = _make_repo(tmp_path, "repo-b")
    id_a = _register(client, repo_a, workspace_id=WS).json()["id"]
    id_b = _register(client, repo_b, workspace_id="ws-beta").json()["id"]

    a = client.get("/api/codebases", params={"workspace_id": WS}).json()["codebases"]
    b = client.get("/api/codebases", params={"workspace_id": "ws-beta"}).json()["codebases"]
    assert [c["id"] for c in a] == [id_a]
    assert [c["id"] for c in b] == [id_b]
    # Unscoped list returns both.
    assert len(client.get("/api/codebases").json()["codebases"]) == 2


# ── tree browsing ─────────────────────────────────────────────────────────────

def test_tree_one_level_dirs_first(client, tmp_path):
    repo = _make_repo(tmp_path)
    cb_id = _register(client, repo).json()["id"]

    r = client.get(f"/api/codebases/{cb_id}/tree")
    assert r.status_code == 200
    body = r.json()
    assert body["truncated"] is False
    entries = body["entries"]
    # dirs first, then files; one level only (src/main.py not listed here)
    assert [e["name"] for e in entries] == ["src", "README.md"]
    assert entries[0]["type"] == "dir"
    assert entries[1]["type"] == "file"
    assert entries[1]["size"] == len("# Repo\n")

    # Lazy second level
    r2 = client.get(f"/api/codebases/{cb_id}/tree", params={"path": "src"})
    assert [e["name"] for e in r2.json()["entries"]] == ["main.py"]


def test_tree_traversal_rejected(client, tmp_path):
    repo = _make_repo(tmp_path)
    cb_id = _register(client, repo).json()["id"]
    for evil in ("..", "../..", "src/../../..", "/etc"):
        r = client.get(f"/api/codebases/{cb_id}/tree", params={"path": evil})
        assert r.status_code == 400, evil


def test_tree_skips_symlinks_escaping_root(client, tmp_path):
    repo = _make_repo(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("secret")
    (repo / "escape").symlink_to(outside)
    (repo / "inlink").symlink_to(repo / "src")  # stays inside: kept
    cb_id = _register(client, repo).json()["id"]

    names = [e["name"] for e in client.get(f"/api/codebases/{cb_id}/tree").json()["entries"]]
    assert "escape" not in names
    assert "inlink" in names

    # Asking for the escaping symlink directly is a traversal error.
    r = client.get(f"/api/codebases/{cb_id}/tree", params={"path": "escape"})
    assert r.status_code == 400


def test_tree_caps_entries_at_500(client, tmp_path):
    repo = tmp_path / "big"
    repo.mkdir()
    for i in range(510):
        (repo / f"f{i:04d}.txt").write_text("x")
    cb_id = _register(client, repo).json()["id"]

    body = client.get(f"/api/codebases/{cb_id}/tree").json()
    assert len(body["entries"]) == 500
    assert body["truncated"] is True


def test_tree_unknown_codebase_404(client):
    assert client.get("/api/codebases/deadbeef/tree").status_code == 404


def test_tree_read_logs_to_chronicle(client, tmp_path):
    repo = _make_repo(tmp_path)
    cb_id = _register(client, repo).json()["id"]
    client.get(f"/api/codebases/{cb_id}/tree")
    entries = client.get("/api/chronicle", params={"source": "codebases"}).json()["entries"]
    assert any(e["action"] == "tree_read" for e in entries)


# ── file reads ────────────────────────────────────────────────────────────────

def test_file_read(client, tmp_path):
    repo = _make_repo(tmp_path)
    cb_id = _register(client, repo).json()["id"]

    r = client.get(f"/api/codebases/{cb_id}/file", params={"path": "src/main.py"})
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "main.py"
    assert body["content"] == "print('hello')\n"
    assert body["size"] == len("print('hello')\n")

    entries = client.get("/api/chronicle", params={"source": "codebases"}).json()["entries"]
    reads = [e for e in entries if e["action"] == "file_read"]
    assert reads and reads[0]["payload"]["path"] == "src/main.py"


def test_file_traversal_rejected(client, tmp_path):
    repo = _make_repo(tmp_path)
    (tmp_path / "outside.txt").write_text("secret")
    cb_id = _register(client, repo).json()["id"]
    r = client.get(f"/api/codebases/{cb_id}/file", params={"path": "../outside.txt"})
    assert r.status_code == 400


def test_file_symlink_escape_rejected(client, tmp_path):
    repo = _make_repo(tmp_path)
    (tmp_path / "outside.txt").write_text("secret")
    (repo / "sneaky.txt").symlink_to(tmp_path / "outside.txt")
    cb_id = _register(client, repo).json()["id"]
    r = client.get(f"/api/codebases/{cb_id}/file", params={"path": "sneaky.txt"})
    assert r.status_code == 400


def test_file_size_cap(client, tmp_path):
    repo = _make_repo(tmp_path)
    (repo / "huge.txt").write_text("a" * (512 * 1024 + 1))
    cb_id = _register(client, repo).json()["id"]
    r = client.get(f"/api/codebases/{cb_id}/file", params={"path": "huge.txt"})
    assert r.status_code == 413


def test_file_binary_415(client, tmp_path):
    repo = _make_repo(tmp_path)
    (repo / "blob.bin").write_bytes(b"\x00\x01\x02ELF")
    (repo / "bad-utf8.txt").write_bytes(b"\xff\xfe caf\xe9")
    cb_id = _register(client, repo).json()["id"]
    assert client.get(f"/api/codebases/{cb_id}/file", params={"path": "blob.bin"}).status_code == 415
    assert client.get(f"/api/codebases/{cb_id}/file", params={"path": "bad-utf8.txt"}).status_code == 415


def test_file_missing_404(client, tmp_path):
    repo = _make_repo(tmp_path)
    cb_id = _register(client, repo).json()["id"]
    assert client.get(f"/api/codebases/{cb_id}/file", params={"path": "nope.py"}).status_code == 404


# ── unregister ────────────────────────────────────────────────────────────────

def test_unregister(client, tmp_path):
    repo = _make_repo(tmp_path)
    cb_id = _register(client, repo).json()["id"]

    r = client.delete(f"/api/codebases/{cb_id}")
    assert r.status_code == 200 and r.json()["ok"] is True

    assert client.get("/api/codebases").json()["codebases"] == []
    assert client.get(f"/api/codebases/{cb_id}/tree").status_code == 404
    # The directory itself is untouched.
    assert (repo / "README.md").exists()

    entries = client.get("/api/chronicle", params={"source": "codebases"}).json()["entries"]
    assert any(e["action"] == "unregistered" for e in entries)


def test_unregister_unknown_404(client):
    assert client.delete("/api/codebases/deadbeef").status_code == 404


# ── Aurora UI wiring contracts (style of test_dispatch_ux.py) ────────────────

def test_app_js_ships_codebase_panel(client):
    src = client.get("/aurora/static/app.js").text
    # Composer toggle + panel markup
    assert 'id="nx-codebase-btn"' in src
    assert 'id="nx-codebase-panel"' in src
    # Register / browse / read / unregister all hit the API
    assert '"/api/codebases"' in src
    assert "/tree?path=" in src
    assert "/file?path=" in src
    # Lazy per-level loading is cached per (codebase, path)
    assert "codebaseTrees" in src
    # Clicking a file reuses the existing attachment flow
    assert "await uploadFile(workspaceId, file)" in src


def test_app_css_ships_codebase_styles(client):
    css = client.get("/aurora/static/app.css").text
    assert ".nx-codebase-panel" in css
    assert ".nx-cb-row" in css
    assert ".nx-cb-err" in css


def test_app_js_parses_as_es_module(client, tmp_path):
    """Parse gate: a syntax error anywhere in app.js bricks the whole UI."""
    import shutil
    import subprocess

    node = shutil.which("node")
    if node is None:
        pytest.skip("node not installed — JS parse gate skipped")
    src = client.get("/aurora/static/app.js").text
    mod = tmp_path / "app-check.mjs"
    mod.write_text(src)
    proc = subprocess.run(
        [node, "--check", str(mod)], capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
