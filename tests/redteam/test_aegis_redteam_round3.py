"""Red-team round 3: what a launched agent can do on its own, outside every call it
routes through ONEXUS.

Rounds 1 and 2 hardened Aegis and the environment an agent starts with. The threat model
(docs/REDTEAM-AEGIS.md) still names the biggest gap: a catalog agent is an ordinary child
process running as the operator. These attacks use real child processes launched through
AgentLauncher, each reporting back what it could do:

  R3-1  read a file in the operator's home directory that it never declared
  R3-2  open a TCP connection to a host it never declared
  R3-3  write a file outside its own working directory

They land first as FOUND tests asserting the broken behaviour, so the history shows each
gap was real before round 3's confinement was written.
"""
from __future__ import annotations

import socket
import sys
import threading

from nexus.agents.catalog import AdapterDescriptor
from nexus.agents.launcher import AgentLauncher

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


def _probe(op, target, extra=None):
    import json
    launcher = AgentLauncher(catalog=_Catalog(["-c", PROBE, op, target], extra), kernel=_Kernel())
    agent = launcher.launch("rt3")
    out, _ = agent.process.communicate(timeout=120)
    return json.loads(out.decode() or "{}")


def _listener():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
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

def test_FOUND_R3_1_launched_agent_reads_a_file_in_the_operators_home(tmp_path, monkeypatch):
    """Nothing stops it: the child runs as the operator, so every file the operator can
    read, it can read."""
    secret = tmp_path / "home" / ".ssh" / "id_rt3"
    secret.parent.mkdir(parents=True)
    secret.write_text("rt3-operator-private-key")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    assert _probe("read", str(secret)).get("ok") == "rt3-operator-private-key"


# R3-2 ────────────────────────────────────────────────────────────────────────

def test_FOUND_R3_2_launched_agent_connects_to_a_host_it_never_declared():
    """Aegis decides the network calls an agent routes through ONEXUS. A socket the agent
    opens itself never reaches Aegis."""
    srv, port = _listener()
    try:
        assert _probe("connect", f"127.0.0.1:{port}").get("ok") == "rt3-undeclared-host"
    finally:
        srv.close()


# R3-3 ────────────────────────────────────────────────────────────────────────

def test_FOUND_R3_3_launched_agent_writes_outside_its_working_directory(tmp_path):
    target = tmp_path / "outside" / "planted.txt"
    target.parent.mkdir()
    assert _probe("write", str(target)).get("ok") == "written"
    assert target.read_text() == "rt3"
