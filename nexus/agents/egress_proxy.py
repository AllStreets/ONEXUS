"""Egress proxy for confined agents (red-team round 3).

A confined agent's container sits on a Docker network with no route out. The only thing
it can reach is this proxy, which runs in its own container on that network and on the
normal bridge. It speaks HTTP CONNECT, the method every HTTPS client uses through
HTTPS_PROXY, and opens a tunnel only to the hosts the agent's adapter declared. Every
decision is printed to stdout as one JSON line, so it can be read back and audited.

Standard library only: it runs as `python egress_proxy.py --allow host[:port],...` in a
stock Python image, read-only, as nobody, with every capability dropped.

Patterns: `api.example.com` (ports 443 and 80), `api.example.com:8443` (that port only),
`*.example.com` (any subdomain, ports 443 and 80).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys

DEFAULT_PORTS = frozenset({443, 80})


def parse_patterns(raw: str) -> list[tuple[str, int | None]]:
    out: list[tuple[str, int | None]] = []
    for item in (raw or "").replace(" ", "").split(","):
        if not item:
            continue
        host, _, port = item.rpartition(":") if item.count(":") == 1 else (item, "", "")
        out.append((host.lower(), int(port) if port else None))
    return out


def allowed(host: str, port: int, patterns: list[tuple[str, int | None]]) -> bool:
    host = host.lower().rstrip(".")
    for pat, pport in patterns:
        if pport is None and port not in DEFAULT_PORTS:
            continue
        if pport is not None and port != pport:
            continue
        if pat.startswith("*."):
            if host.endswith(pat[1:]) and host != pat[2:]:
                return True
        elif host == pat:
            return True
    return False


def _log(**fields) -> None:
    sys.stdout.write(json.dumps(fields, sort_keys=True) + "\n")
    sys.stdout.flush()


async def _pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while data := await reader.read(65536):
            writer.write(data)
            await writer.drain()
    except (ConnectionError, OSError):
        pass
    finally:
        try:
            writer.close()
        except OSError:
            pass


def make_handler(patterns):
    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            line = (await reader.readline()).decode("latin-1").strip()
            while (await reader.readline()) not in (b"\r\n", b"\n", b""):
                pass
            parts = line.split()
            if len(parts) != 3 or parts[0].upper() != "CONNECT":
                _log(decision="deny", reason="only CONNECT is proxied", request=line[:120])
                writer.write(b"HTTP/1.1 405 Method Not Allowed\r\n\r\n")
                return
            host, _, port_s = parts[1].rpartition(":")
            port = int(port_s) if port_s.isdigit() else 0
            if not host or not allowed(host, port, patterns):
                _log(decision="deny", reason="host not declared", host=host, port=port)
                writer.write(b"HTTP/1.1 403 Forbidden\r\n\r\n")
                return
            try:
                up_r, up_w = await asyncio.wait_for(asyncio.open_connection(host, port), 10)
            except (OSError, TimeoutError) as exc:
                _log(decision="allow", outcome="unreachable", host=host, port=port, error=type(exc).__name__)
                writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                return
            _log(decision="allow", host=host, port=port)
            writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            await writer.drain()
            await asyncio.gather(_pipe(reader, up_w), _pipe(up_r, writer))
        finally:
            try:
                await writer.drain()
                writer.close()
            except (ConnectionError, OSError):
                pass
    return handle


async def serve(patterns, port: int) -> None:
    server = await asyncio.start_server(make_handler(patterns), "0.0.0.0", port)
    _log(decision="listening", port=port, allow=[f"{h}:{p}" if p else h for h, p in patterns])
    async with server:
        await server.serve_forever()


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--allow", default="")
    ap.add_argument("--port", type=int, default=3128)
    a = ap.parse_args(argv)
    asyncio.run(serve(parse_patterns(a.allow), a.port))


if __name__ == "__main__":
    main()
