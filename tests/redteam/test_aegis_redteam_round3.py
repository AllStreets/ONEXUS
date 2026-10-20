"""Red-team round 3: what a launched agent can do on its own, outside every call it
routes through ONEXUS.

Rounds 1 and 2 hardened Aegis and the environment an agent starts with. The threat model
(docs/REDTEAM-AEGIS.md) still names the biggest gap: a catalog agent is an ordinary child
process running as the operator. These attacks use real child processes launched through
AgentLauncher, each reporting back what it could do:

  R3-1  read a file in the operator's home directory that it never declared
  R3-2  open a TCP connection to a host it never declared
  R3-3  write a file outside its own working directory

They landed first as FOUND tests asserting the broken behaviour (commit aa9f133), so the
history shows each gap was real before round 3's confinement was written. They stay true
for an adapter that declares no confinement, so they are kept below as UNCONFINED tests;
NEXUS_AGENT_CONFINEMENT=require refuses to launch such an agent at all. The FIXED tests run
the same attacks inside the container confine.py builds, and check the egress proxy lets
an agent reach exactly the hosts it declared. They need Docker and skip without it.
"""
from __future__ import annotations

import json
import socket
import subprocess
import sys
import threading

import pytest

from nexus.agents.catalog import AdapterDescriptor
from nexus.agents.confine import docker_available
from nexus.agents.launcher import AgentLauncher, AgentLaunchError

PROBE = r"""
import socket, sys, json
op, target = sys.argv[1], sys.argv[2]
out = {}
try:
    if op == "read":
        out["ok"] = open(target).read()
    elif op == "connect":
        host, port = target.rsplit(":", 1)
        s = socket.create_connection((host, int(port)), timeout=3)
        out["ok"] = s.recv(64).decode()
        s.close()
    elif op == "write":
        open(target, "w").write("rt3")
        out["ok"] = "written"
    elif op == "via_proxy":
        import os, urllib.parse
        proxy = urllib.parse.urlparse(os.environ["HTTPS_PROXY"])
        s = socket.create_connection((proxy.hostname, proxy.port), timeout=10)
        s.sendall(("CONNECT %s HTTP/1.1\r\nHost: %s\r\n\r\n" % (target, target)).encode())
        status = s.recv(128).decode().split("\r\n")[0]
        out["status"] = status
        if " 200 " in status + " ":
            out["ok"] = s.recv(64).decode()
        s.close()
except Exception as e:
    out["err"] = type(e).__name__
sys.stdout.write(json.dumps(out)); sys.stdout.flush()
"""


class _Entry:
    def __init__(self, slug):
        self.slug, self.name, self.category, self.runnable = slug, slug, "coding", True


class _Catalog:
    def __init__(self, args, extra=None):
        self._args, self._extra = args, extra or {}

    def get_agent(self, slug):
        return _Entry(slug)

    def load_adapter(self, entry):
        return AdapterDescriptor(
            name=entry.slug, transport="stdio", command=sys.executable, args=self._args,
            env={}, capabilities={}, trust_floor=0.0, default_tier="OBSERVER", **self._extra,
        )


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


def _probe(op, target, extra=None, kernel=None, keep=None):
    kernel = kernel or _Kernel()
    launcher = AgentLauncher(catalog=_Catalog(["-c", PROBE, op, target], extra), kernel=kernel)
    agent = launcher.launch("rt3")
    try:
        out, err = agent.process.communicate(timeout=180)
        if keep is not None and agent.confinement:
            keep["proxy_log"] = agent.confinement.proxy_log()
            keep["names"] = [agent.confinement.name, agent.confinement.proxy, agent.confinement.network]
        return json.loads(out.decode() or "{}") if out.strip() else {"err": "no-output", "stderr": err.decode()[-300:]}
    finally:
        launcher.stop("rt3")


def _listener(bind="127.0.0.1"):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((bind, 0))
    srv.listen(1)

    def serve():
        try:
            conn, _ = srv.accept()
            conn.sendall(b"rt3-undeclared-host")
            conn.close()
        except OSError:
            pass

    threading.Thread(target=serve, daemon=True).start()
    return srv, srv.getsockname()[1]


# R3-1 ────────────────────────────────────────────────────────────────────────

def test_UNCONFINED_R3_1_launched_agent_reads_a_file_in_the_operators_home(tmp_path, monkeypatch):
    """Nothing stops it: the child runs as the operator, so every file the operator can
    read, it can read."""
    secret = tmp_path / "home" / ".ssh" / "id_rt3"
    secret.parent.mkdir(parents=True)
    secret.write_text("rt3-operator-private-key")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    assert _probe("read", str(secret)).get("ok") == "rt3-operator-private-key"


# R3-2 ────────────────────────────────────────────────────────────────────────

def test_UNCONFINED_R3_2_launched_agent_connects_to_a_host_it_never_declared():
    """Aegis decides the network calls an agent routes through ONEXUS. A socket the agent
    opens itself never reaches Aegis."""
    srv, port = _listener()
    try:
        assert _probe("connect", f"127.0.0.1:{port}").get("ok") == "rt3-undeclared-host"
    finally:
        srv.close()


# R3-3 ────────────────────────────────────────────────────────────────────────

def test_UNCONFINED_R3_3_launched_agent_writes_outside_its_working_directory(tmp_path):
    target = tmp_path / "outside" / "planted.txt"
    target.parent.mkdir()
    assert _probe("write", str(target)).get("ok") == "written"
    assert target.read_text() == "rt3"


# ─────────────────────────────────────────────────────────────────────────────
# Round 3 fix: confinement (confine.py, egress_proxy.py)
# ─────────────────────────────────────────────────────────────────────────────

needs_docker = pytest.mark.skipif(not docker_available(), reason="confinement needs Docker")
CONFINED = {"confinement": {"image": "python:3.12-alpine", "command": "python"}}


@needs_docker
def test_FIXED_R3_1_confined_agent_cannot_see_the_operators_files(tmp_path, monkeypatch):
    secret = tmp_path / "home" / ".ssh" / "id_rt3"
    secret.parent.mkdir(parents=True)
    secret.write_text("rt3-operator-private-key")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    got = _probe("read", str(secret), CONFINED)
    assert "ok" not in got and got.get("err") == "FileNotFoundError", got


@needs_docker
def test_FIXED_R3_2_confined_agent_with_no_hosts_has_no_network():
    srv, port = _listener("0.0.0.0")
    try:
        for target in (f"127.0.0.1:{port}", f"host.docker.internal:{port}"):
            got = _probe("connect", target, CONFINED)
            assert "ok" not in got and got.get("err"), (target, got)
    finally:
        srv.close()


@needs_docker
def test_FIXED_R3_3_confined_agent_cannot_write_outside_its_work_dir(tmp_path):
    target = tmp_path / "outside" / "planted.txt"
    target.parent.mkdir()
    got = _probe("write", str(target), CONFINED)
    assert "ok" not in got, got
    assert not target.exists()
    assert _probe("write", "/usr/planted.txt", CONFINED).get("err") in {"OSError", "PermissionError"}


@needs_docker
def test_FIXED_R3_2_the_egress_proxy_reaches_declared_hosts_and_refuses_the_rest():
    srv, port = _listener("0.0.0.0")
    declared = f"host.docker.internal:{port}"
    extra = {"confinement": {**CONFINED["confinement"], "hosts": [declared]}}
    try:
        keep = {}
        allowed = _probe("via_proxy", declared, extra, keep=keep)
        assert " 200 " in allowed.get("status", "") + " " and allowed.get("ok") == "rt3-undeclared-host", allowed
        assert any('"decision": "allow"' in ln for ln in keep["proxy_log"]), keep
        keep = {}
        refused = _probe("via_proxy", "example.com:443", extra, keep=keep)
        assert " 403 " in refused.get("status", "") + " ", refused
        assert any('"decision": "deny"' in ln and "example.com" in ln for ln in keep["proxy_log"]), keep
        direct = _probe("connect", declared, extra)  # only through the proxy, never around it
        assert "ok" not in direct, direct
    finally:
        srv.close()


@needs_docker
def test_FIXED_R3_confined_launch_is_recorded_and_torn_down():
    kernel, keep = _Kernel(), {}
    _probe("read", "/etc/hostname", {"confinement": {**CONFINED["confinement"], "hosts": ["example.com"]}}, kernel=kernel, keep=keep)
    payload = next(a[2] for a, _ in kernel.chronicle.events if a[:2] == ("agents", "agent_launched"))
    assert payload["confined"] is True and payload["hosts"] == ["example.com"]
    left = subprocess.run(["docker", "ps", "-a", "--format", "{{.Names}}"], capture_output=True, text=True, check=False).stdout.split()
    nets = subprocess.run(["docker", "network", "ls", "--format", "{{.Name}}"], capture_output=True, text=True, check=False).stdout.split()
    assert not set(keep["names"][:2]) & set(left) and keep["names"][2] not in nets


def test_FIXED_R3_require_mode_refuses_an_unconfined_agent(monkeypatch):
    monkeypatch.setenv("NEXUS_AGENT_CONFINEMENT", "require")
    with pytest.raises(AgentLaunchError) as exc:
        AgentLauncher(catalog=_Catalog(["-c", "print(1)"]), kernel=_Kernel()).launch("rt3")
    assert exc.value.status == 403


def test_HOLDS_R3_an_unconfined_launch_says_so_in_the_ledger():
    kernel = _Kernel()
    _probe("read", "/etc/hostname", kernel=kernel)
    payload = next(a[2] for a, _ in kernel.chronicle.events if a[:2] == ("agents", "agent_launched"))
    assert payload["confined"] is False
