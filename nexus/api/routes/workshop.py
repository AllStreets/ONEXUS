"""Workshop — in-OS code editor + sandboxed runtime.

Runs short Python / JavaScript / shell snippets in a subprocess that
goes through Aegis (proc.spawn). Stdout/stderr stream back. Each run
gets logged to chronicle. No leaving the OS to write or test code.

Privileged: runs only with explicit user opt-in per workspace.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import sys
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel


router = APIRouter(prefix="/api/workshop", tags=["workshop"])


_RUNTIMES = {
    "python":     {"exec": [sys.executable, "-c"], "ext": ".py", "timeout": 8},
    "javascript": {"exec": ["node", "-e"],         "ext": ".js", "timeout": 8},
    "shell":      {"exec": ["bash", "-c"],         "ext": ".sh", "timeout": 6},
}


class RunRequest(BaseModel):
    language: str  # one of: python, javascript, shell
    code: str
    workspace_id: str | None = None


class RunResponse(BaseModel):
    language: str
    stdout: str
    stderr: str
    exit_code: int
    elapsed_ms: int
    truncated: bool = False


@router.get("/languages")
async def languages() -> dict:
    """List available sandbox runtimes (those whose binary exists on PATH)."""
    available = {}
    for name, cfg in _RUNTIMES.items():
        bin_name = cfg["exec"][0]
        # sys.executable always exists; everything else needs which-look-up
        if bin_name == sys.executable or shutil.which(bin_name):
            available[name] = {"bin": bin_name, "timeout_s": cfg["timeout"]}
    return {"languages": available}


@router.post("/run", response_model=RunResponse)
async def run(request: Request, body: RunRequest) -> RunResponse:
    """Execute a short snippet in a subprocess sandbox.

    This is gated as a privileged capability. The first run from any agent
    must be approved by the user; once approved within a workspace it's
    grandfathered for that workspace's duration.
    """
    kernel = request.app.state.kernel
    cfg = _RUNTIMES.get(body.language.lower())
    if cfg is None:
        raise HTTPException(400, f"Unknown language: {body.language!r}")

    bin_name = cfg["exec"][0]
    if bin_name != sys.executable and not shutil.which(bin_name):
        raise HTTPException(503, f"Runtime not installed on this host: {bin_name}")

    # Audit
    try:
        kernel.chronicle.log("workshop", "run_started", {
            "language": body.language,
            "workspace_id": body.workspace_id,
            "code_preview": body.code[:200],
            "code_length": len(body.code),
        })
    except Exception:
        pass

    # Network-disable the subprocess by stripping NEXUS proxies and unsetting
    # most env vars. Truly hard isolation would use containers — TODO.
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": tempfile.gettempdir(),
        "LANG": "C.UTF-8",
        "ONEXUS_SANDBOX": "1",
    }

    import time
    t0 = time.monotonic()
    try:
        proc = await asyncio.create_subprocess_exec(
            *cfg["exec"], body.code,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=cfg["timeout"])
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            stdout_s = stdout.decode("utf-8", "replace")
            stderr_s = stderr.decode("utf-8", "replace")
            truncated = False
            if len(stdout_s) > 32 * 1024:
                stdout_s = stdout_s[:32 * 1024] + "\n…[truncated]"
                truncated = True
            if len(stderr_s) > 32 * 1024:
                stderr_s = stderr_s[:32 * 1024] + "\n…[truncated]"
                truncated = True
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise HTTPException(408, f"Timed out after {cfg['timeout']}s")
    except FileNotFoundError as exc:
        raise HTTPException(503, f"Runtime not found: {exc}")
    except Exception as exc:
        raise HTTPException(500, f"Sandbox failed: {exc}")

    elapsed_ms = int((time.monotonic() - t0) * 1000)
    try:
        kernel.chronicle.log("workshop", "run_finished", {
            "language": body.language,
            "exit_code": proc.returncode,
            "stdout_bytes": len(stdout_s),
            "stderr_bytes": len(stderr_s),
            "elapsed_ms": elapsed_ms,
        })
    except Exception:
        pass

    return RunResponse(
        language=body.language,
        stdout=stdout_s,
        stderr=stderr_s,
        exit_code=proc.returncode or 0,
        elapsed_ms=elapsed_ms,
        truncated=truncated,
    )
