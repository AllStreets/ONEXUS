"""Container confinement for launched agents (red-team round 3).

Rounds 1 and 2 governed what an agent asks ONEXUS for. Round 3 limits what it can do on
its own. An adapter that declares a `confinement` block runs in a container instead of as
a child process of the operator:

    "confinement": {
      "image": "python:3.12-alpine",       # what the agent runs in
      "command": "python",                 # optional: the program inside the image
      "hosts": ["api.anthropic.com"]       # optional: the only places it may connect to
    }

The container gets a read-only root, a private tmpfs for its work, no capabilities, no
privilege escalation, a non-root user, and limits on memory, CPU and process count. It
sees none of the operator's files. With no hosts declared it has no network at all
(`--network none`). With hosts declared it sits on an internal Docker network whose only
other member is an egress proxy (egress_proxy.py) that tunnels to those hosts and refuses
everything else, logging each decision.

The hardening flags follow SMADP's sandbox profile (smadp/sandbox/isolation.py), minus the
pieces that need a custom runtime (gVisor) or a pinned-image allowlist; see the report.
"""
from __future__ import annotations

import os
import re
import secrets
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

PROXY_PORT = 3128
EGRESS_IMAGE = os.environ.get("NEXUS_EGRESS_IMAGE", "python:3.12-alpine")
_HOST_RE = re.compile(r"^(\*\.)?[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)*(:\d{1,5})?$")
_IMAGE_RE = re.compile(r"^[a-z0-9][a-z0-9._/:@-]*$", re.IGNORECASE)


class ConfinementError(ValueError):
    pass


@dataclass(frozen=True)
class Confinement:
    image: str
    command: str | None = None
    hosts: tuple[str, ...] = ()
    memory: str = "1g"
    cpus: str = "1"
    pids: int = 256

    @classmethod
    def from_adapter(cls, raw: dict | None) -> Confinement | None:
        if not raw:
            return None
        image = str(raw.get("image") or "")
        if not _IMAGE_RE.match(image):
            raise ConfinementError(f"confinement.image is missing or invalid: {image!r}")
        hosts = tuple(str(h).lower() for h in raw.get("hosts") or ())
        bad = [h for h in hosts if not _HOST_RE.match(h)]
        if bad:
            raise ConfinementError(f"confinement.hosts has invalid entries: {bad}")
        command = raw.get("command")
        if command is not None and (not isinstance(command, str) or not command or "/" in command and not command.startswith("/")):
            raise ConfinementError(f"confinement.command is invalid: {command!r}")
        return cls(image=image, command=command, hosts=hosts)


def docker_available() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        return subprocess.run(["docker", "info"], capture_output=True, timeout=10, check=False).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _run(*argv: str) -> str:
    return subprocess.run(list(argv), capture_output=True, text=True, check=True, timeout=120).stdout.strip()


@dataclass
class ConfinedLaunch:
    """Everything one confined agent needs, and how to take it down again."""

    argv: list[str]
    name: str
    network: str | None = None
    proxy: str | None = None
    _cleaned: bool = field(default=False, repr=False)

    def cleanup(self) -> None:
        if self._cleaned:
            return
        self._cleaned = True
        for argv in (["docker", "rm", "-f", self.name], ["docker", "rm", "-f", self.proxy or ""], ["docker", "network", "rm", self.network or ""]):
            if argv[-1]:
                subprocess.run(argv, capture_output=True, timeout=60, check=False)

    def proxy_log(self) -> list[str]:
        """The egress proxy's decisions so far, one JSON line each."""
        if not self.proxy:
            return []
        out = subprocess.run(["docker", "logs", self.proxy], capture_output=True, text=True, timeout=30, check=False)
        return [ln for ln in out.stdout.splitlines() if ln.strip()]


def prepare(conf: Confinement, slug: str, command: str, args: list[str], env_keys) -> ConfinedLaunch:
    """Build the container, and the egress proxy if hosts are declared. Returns the argv to
    exec; the caller passes the agent's environment to that process, and `-e KEY` forwards
    exactly those keys into the container."""
    tag = f"{re.sub(r'[^a-z0-9-]', '-', slug.lower())[:40]}-{secrets.token_hex(3)}"
    name = f"nx-agent-{tag}"
    network = proxy = None
    proxy_env: list[str] = []
    if conf.hosts:
        network = f"nx-net-{tag}"
        proxy = f"nx-egress-{tag}"
        _run("docker", "network", "create", "--internal", network)
        script = Path(__file__).with_name("egress_proxy.py").resolve()
        _run(
            "docker", "run", "-d", "--rm", "--name", proxy, "--network", network,
            "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--user", "65534:65534", "--memory", "128m", "--pids-limit", "64",
            "--add-host", "host.docker.internal:host-gateway",
            "-v", f"{script}:/egress_proxy.py:ro",
            EGRESS_IMAGE, "python", "/egress_proxy.py", "--port", str(PROXY_PORT), "--allow", ",".join(conf.hosts),
        )
        _run("docker", "network", "connect", "bridge", proxy)
        url = f"http://{proxy}:{PROXY_PORT}"
        proxy_env = ["-e", f"HTTPS_PROXY={url}", "-e", f"HTTP_PROXY={url}", "-e", f"https_proxy={url}", "-e", f"http_proxy={url}", "-e", "NO_PROXY="]
    inner = conf.command or os.path.basename(command)
    argv = [
        "docker", "run", "--rm", "-i", "--name", name,
        "--network", network or "none",
        "--read-only", "--tmpfs", "/tmp:rw,size=64m,mode=1777",
        # owned by the agent's user: with -w, Docker would otherwise create /work root-only
        "--tmpfs", "/work:rw,size=256m,uid=65534,gid=65534", "-w", "/work",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--user", "65534:65534",
        "--memory", conf.memory, "--cpus", conf.cpus, "--pids-limit", str(conf.pids),
        "-e", "HOME=/work", *proxy_env,
    ]
    for key in sorted(set(env_keys) - {"HOME", "PATH"}):
        argv += ["-e", key]
    argv += [conf.image, inner, *args]
    return ConfinedLaunch(argv=argv, name=name, network=network, proxy=proxy)
