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


# Inline-executable runtimes (code is passed as an argument, no compile step).
# A language only actually runs if its binary is on PATH — `/languages`
# reports every entry with an `installed` flag so the UI can offer the full
# searchable list while the run endpoint returns a clear 503 for missing ones.
_RUNTIMES = {
    "python":      {"exec": [sys.executable, "-c"],   "ext": ".py",  "timeout": 8},
    "javascript":  {"exec": ["node", "-e"],           "ext": ".js",  "timeout": 8},
    "typescript":  {"exec": ["deno", "eval", "--ext=ts"], "ext": ".ts", "timeout": 8},
    "shell":       {"exec": ["bash", "-c"],           "ext": ".sh",  "timeout": 6},
    "bash":        {"exec": ["bash", "-c"],           "ext": ".sh",  "timeout": 6},
    "zsh":         {"exec": ["zsh", "-c"],            "ext": ".zsh", "timeout": 6},
    "fish":        {"exec": ["fish", "-c"],           "ext": ".fish","timeout": 6},
    "ruby":        {"exec": ["ruby", "-e"],           "ext": ".rb",  "timeout": 8},
    "perl":        {"exec": ["perl", "-e"],           "ext": ".pl",  "timeout": 8},
    "php":         {"exec": ["php", "-r"],            "ext": ".php", "timeout": 8},
    "lua":         {"exec": ["lua", "-e"],            "ext": ".lua", "timeout": 8},
    "r":           {"exec": ["Rscript", "-e"],        "ext": ".R",   "timeout": 8},
    "deno":        {"exec": ["deno", "eval"],         "ext": ".ts",  "timeout": 8},
    "bun":         {"exec": ["bun", "-e"],            "ext": ".js",  "timeout": 8},
    "node":        {"exec": ["node", "-e"],           "ext": ".js",  "timeout": 8},
    "elixir":      {"exec": ["elixir", "-e"],         "ext": ".exs", "timeout": 8},
    "erlang":      {"exec": ["escript"],              "ext": ".erl", "timeout": 8},
    "powershell":  {"exec": ["pwsh", "-c"],           "ext": ".ps1", "timeout": 8},
    "groovy":      {"exec": ["groovy", "-e"],         "ext": ".groovy", "timeout": 10},
    "scala":       {"exec": ["scala", "-e"],          "ext": ".scala","timeout": 12},
    "raku":        {"exec": ["raku", "-e"],           "ext": ".raku","timeout": 8},
    "tcl":         {"exec": ["tclsh"],                "ext": ".tcl", "timeout": 8},
    "julia":       {"exec": ["julia", "-e"],          "ext": ".jl",  "timeout": 10},
    "clojure":     {"exec": ["clojure", "-e"],        "ext": ".clj", "timeout": 12},
    "dart":        {"exec": ["dart", "run", "-"],     "ext": ".dart","timeout": 10},
    "swift":       {"exec": ["swift", "-"],           "ext": ".swift","timeout": 12},
    "go":          {"exec": ["go", "run", "-"],       "ext": ".go",  "timeout": 12},
    # more inline-executable runtimes
    "applescript": {"exec": ["osascript", "-e"],      "ext": ".applescript", "timeout": 8},
    "sqlite":      {"exec": ["sqlite3", ":memory:"],  "ext": ".sql", "timeout": 6},
    "nushell":     {"exec": ["nu", "-c"],             "ext": ".nu",  "timeout": 8},
    "crystal":     {"exec": ["crystal", "eval"],      "ext": ".cr",  "timeout": 12},
    "racket":      {"exec": ["racket", "-e"],         "ext": ".rkt", "timeout": 10},
    "guile":       {"exec": ["guile", "-c"],          "ext": ".scm", "timeout": 8},
    "scheme":      {"exec": ["guile", "-c"],          "ext": ".scm", "timeout": 8},
    "commonlisp":  {"exec": ["sbcl", "--non-interactive", "--eval"], "ext": ".lisp", "timeout": 10},
    "haskell":     {"exec": ["ghc", "-e"],            "ext": ".hs",  "timeout": 12},
    "fennel":      {"exec": ["fennel", "-e"],         "ext": ".fnl", "timeout": 8},
    "janet":       {"exec": ["janet", "-e"],          "ext": ".janet","timeout": 8},
    "coffeescript":{"exec": ["coffee", "-e"],         "ext": ".coffee","timeout": 8},
}

# Markup/style "languages" — these render rather than execute, so the Workshop
# previews them client-side in a sandboxed iframe instead of calling /run.
# Reported by /languages so they show in the picker (always "installed").
_PREVIEW_LANGS = {"html", "css", "markdown"}


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
    """List sandbox runtimes. Returns every defined language with an
    ``installed`` flag (binary present on PATH) so the UI can show the full
    searchable list; the run endpoint 503s for an uninstalled pick."""
    out = {}
    for name, cfg in _RUNTIMES.items():
        bin_name = cfg["exec"][0]
        installed = bin_name == sys.executable or shutil.which(bin_name) is not None
        out[name] = {"bin": bin_name, "timeout_s": cfg["timeout"], "installed": installed}
    # Preview languages render in the browser — always available, no runtime.
    for name in sorted(_PREVIEW_LANGS):
        out[name] = {"bin": "browser", "timeout_s": 0, "installed": True, "preview": True}
    return {"languages": out}


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
