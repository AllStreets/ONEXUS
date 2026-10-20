"""The first catalog adapters that run confined: haystack and faster-whisper.

Round 3 (docs/REDTEAM-AEGIS.md) added container confinement for any adapter that declares
it, and said plainly that none did yet. These tests launch the two that now do, from the
real ONEXUS-Agents catalog, through the real AgentLauncher, and speak MCP to them over
the container's stdio. Then they check from inside each running container that it has no
network and none of the operator's files.

They need Docker, a sibling ONEXUS-Agents checkout (or NEXUS_AGENTS_CATALOG), and the two
adapter images (built from adapters/<name>/Dockerfile there); they skip without them.
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
from pathlib import Path

import pytest

from nexus.agents.catalog import AgentCatalog
from nexus.agents.confine import docker_available
from nexus.agents.launcher import AgentLauncher

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
CATALOG = Path(os.environ.get("NEXUS_AGENTS_CATALOG") or Path(__file__).resolve().parents[3] / "ONEXUS-Agents")


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


def _image_present(image: str) -> bool:
    return subprocess.run(["docker", "image", "inspect", image], capture_output=True, check=False).returncode == 0


class _MCP:
    """Just enough of an MCP client to drive a stdio server: newline-delimited JSON-RPC."""

    def __init__(self, proc):
        self.proc, self.next_id = proc, 1

    def _send(self, msg):
        self.proc.stdin.write((json.dumps(msg) + "\n").encode())
        self.proc.stdin.flush()

    def request(self, method, params=None):
        rid, self.next_id = self.next_id, self.next_id + 1
        self._send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}})
        while True:
            line = self.proc.stdout.readline()
            if not line:
                raise RuntimeError("server closed: " + self.proc.stderr.read().decode()[-500:])
            msg = json.loads(line)
            if msg.get("id") == rid:
                if "error" in msg:
                    raise RuntimeError(msg["error"])
                return msg["result"]

    def initialize(self):
        self.request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                    "clientInfo": {"name": "nexus-test", "version": "0"}})
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def call(self, tool, **arguments):
        res = self.request("tools/call", {"name": tool, "arguments": arguments})
        assert not res.get("isError"), res
        if res.get("structuredContent") is not None:
            out = res["structuredContent"]
            return out.get("result", out) if isinstance(out, dict) and set(out) == {"result"} else out
        return json.loads(res["content"][0]["text"])


@pytest.fixture
def launched(request):
    slug = request.param
    if not docker_available():
        pytest.skip("Docker is not available")
    if not (CATALOG / "catalog").is_dir():
        pytest.skip(f"no ONEXUS-Agents catalog at {CATALOG}")
    catalog = AgentCatalog(CATALOG)
    adapter = catalog.load_adapter(catalog.get_agent(slug))
    if not _image_present(adapter.confinement["image"]):
        pytest.skip(f"image {adapter.confinement['image']} is not built")
    kernel = _Kernel()
    launcher = AgentLauncher(catalog=catalog, kernel=kernel)
    agent = launcher.launch(slug)
    try:
        client = _MCP(agent.process)
        client.initialize()
        yield agent, client, adapter, kernel
    finally:
        launcher.stop(slug)


def _inside(agent, code):
    """Run Python inside the agent's own running container and return what it printed."""
    out = subprocess.run(["docker", "exec", agent.confinement.name, "python", "-c", code],
                         capture_output=True, text=True, timeout=60, check=False)
    return out.stdout.strip()


ESCAPES = r"""
import json, os, socket
r = {}
try:
    socket.create_connection(("1.1.1.1", 443), timeout=3); r["net"] = "connected"
except OSError as e:
    r["net"] = type(e).__name__
r["home"] = os.path.exists("/Users") or os.path.exists("/home/" + os.environ.get("USER", "x"))
try:
    open("/app/escape", "w").write("x"); r["write"] = "wrote"
except OSError as e:
    r["write"] = type(e).__name__
print(json.dumps(r))
"""


def _assert_confined(agent, adapter, kernel):
    assert agent.confined
    argv = agent.confinement.argv
    assert argv[argv.index("--network") + 1] == "none"
    assert adapter.confinement["image"] in argv
    payload = next(a[2] for a, _ in kernel.chronicle.events if a[:2] == ("agents", "agent_launched"))
    assert payload["confined"] is True
    escapes = json.loads(_inside(agent, ESCAPES))
    assert escapes["net"] != "connected"
    assert escapes["home"] is False
    assert escapes["write"] != "wrote"


@pytest.mark.parametrize("launched", ["haystack"], indirect=True)
def test_haystack_runs_confined_and_searches(launched):
    agent, client, adapter, kernel = launched
    tools = {t["name"] for t in client.request("tools/list")["tools"]}
    assert tools == set(adapter.capabilities["tools"])

    written = client.call("index_documents", documents=[
        "The Chicago River is dyed green every March for the parade.",
        {"content": "Lake Michigan freezes along the shore in hard winters.", "meta": {"src": "b"}},
        "Deep dish pizza is baked in a tall pan.",
    ])
    assert written["total"] == 3
    hits = client.call("search", query="frozen lake shore winter", top_k=1)
    assert "Lake Michigan" in hits[0]["content"]
    assert {p["name"] for p in client.call("list_pipelines")} == {"search", "split-and-index"}
    _assert_confined(agent, adapter, kernel)


@pytest.mark.parametrize("launched", ["faster-whisper"], indirect=True)
def test_faster_whisper_runs_confined_and_transcribes(launched):
    agent, client, adapter, kernel = launched
    tools = {t["name"] for t in client.request("tools/list")["tools"]}
    assert tools == set(adapter.capabilities["tools"])

    audio = base64.b64encode((FIXTURES / "speech-river.wav").read_bytes()).decode()
    out = client.call("transcribe", audio_base64=audio)
    assert out["language"] == "en"
    text = out["text"].lower()
    assert "river" in text and "bridge" in text and "january" in text
    _assert_confined(agent, adapter, kernel)
