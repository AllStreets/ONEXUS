"""Ask a freshly installed MCP server for its tools, the way the catalog's verifier does,
so an install that wouldn't start on this machine fails before it's recorded."""
from __future__ import annotations

import json
import queue
import subprocess
import threading
import time

EXIT_MEANING = {
    1: "it reported an error",
    127: "its command wasn't found in the image",
    132: "illegal instruction: a native library needs CPU features this machine lacks",
    137: "it was killed, most likely by the memory limit",
    139: "it crashed",
}


def handshake(argv: list[str], env: dict[str, str] | None = None, timeout: float = 60.0) -> dict:
    t0 = time.monotonic()
    proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    lines: queue.Queue = queue.Queue()
    err: list[bytes] = []
    threading.Thread(target=lambda: [lines.put(x) for x in iter(proc.stdout.readline, b"")] or lines.put(None),
                     daemon=True).start()
    er = threading.Thread(target=lambda: [err.append(x) for x in iter(proc.stderr.readline, b"")], daemon=True)
    er.start()

    def send(m):
        proc.stdin.write((json.dumps(m) + "\n").encode())
        proc.stdin.flush()

    def wait_for(rid):
        while True:
            left = timeout - (time.monotonic() - t0)
            if left <= 0:
                raise TimeoutError(f"no answer within {int(timeout)}s")
            try:
                line = lines.get(timeout=left)
            except queue.Empty:
                raise TimeoutError(f"no answer within {int(timeout)}s") from None
            if line is None:
                raise EOFError("the server exited")
            try:
                m = json.loads(line)
            except ValueError:
                continue
            if isinstance(m, dict) and m.get("id") == rid:
                if "error" in m:
                    raise RuntimeError(str(m["error"])[:300])
                return m.get("result") or {}

    try:
        send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "onexus-store", "version": "1"}}})
        wait_for(1)
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        tools = sorted(t.get("name", "") for t in wait_for(2).get("tools") or [] if t.get("name"))
        return {"ok": True, "tools": tools, "ms": int((time.monotonic() - t0) * 1000)}
    except (TimeoutError, EOFError, RuntimeError, BrokenPipeError, OSError) as exc:
        why = str(exc)
        if isinstance(exc, (EOFError, BrokenPipeError)):
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            er.join(timeout=2)
            code = proc.poll()
            if code is not None:
                why = f"the server exited with code {code}" + (f" ({EXIT_MEANING[code]})" if code in EXIT_MEANING else "")
        tail = b"".join(err[-6:]).decode(errors="replace").strip()
        return {"ok": False, "reason": (why + ". " + tail[-400:]).strip()}
    finally:
        proc.kill()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass
