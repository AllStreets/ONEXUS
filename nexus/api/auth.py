"""Optional per-instance API authentication.

By default ONEXUS binds to 127.0.0.1 and trusts every caller, which is fine
for the local single-user loopback case the Tauri shell uses. The moment an
instance is exposed beyond loopback (LAN, a tunnel, a shared host) that trust
is a liability.

This module adds a bearer-token gate that is **off by default and opt-in**,
implemented as a pure-ASGI middleware so it covers both HTTP routes and
WebSocket handshakes uniformly:

- If the ``NEXUS_API_TOKEN`` environment variable is unset or empty, the gate
  passes everything through — existing local behavior and the whole test
  suite are unchanged.
- If it is set, every request must carry ``Authorization: Bearer <token>``
  (constant-time compared) except a small allowlist of unauthenticated paths
  (health probe + the Aurora dashboard shell + API docs) so the deploy
  healthcheck and a browser landing still work. The dashboard's own API/WS
  calls must carry the token.

Set the token to lock an exposed instance down:

    NEXUS_API_TOKEN=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
"""

from __future__ import annotations

import hmac
import os

from starlette.types import ASGIApp, Receive, Scope, Send

#: Paths served without a token even when the gate is enabled. Keep this tight.
_UNAUTHENTICATED_PREFIXES = (
    "/api/system/health",
    "/aurora",  # dashboard shell (static); its API/WS calls still need the token
    "/docs",
    "/openapi.json",
    "/redoc",
)


def _configured_token() -> str:
    return os.environ.get("NEXUS_API_TOKEN", "").strip()


def _is_exempt(path: str) -> bool:
    return any(path == p or path.startswith(p + "/") for p in _UNAUTHENTICATED_PREFIXES)


def _token_ok(headers: list[tuple[bytes, bytes]], expected: str) -> bool:
    raw = b""
    for k, v in headers:
        if k.lower() == b"authorization":
            raw = v
            break
    scheme, _, presented = raw.decode("latin-1").partition(" ")
    if scheme.lower() != "bearer" or not presented:
        return False
    return hmac.compare_digest(presented, expected)


class ApiTokenMiddleware:
    """ASGI middleware enforcing the optional bearer-token gate.

    No-op unless NEXUS_API_TOKEN is set, so loopback use and tests are
    unaffected. Fail-closed only once an operator opts in. Handles HTTP and
    WebSocket scopes; other scopes (lifespan) pass straight through.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        expected = _configured_token()
        if not expected or _is_exempt(scope.get("path", "")):
            await self.app(scope, receive, send)
            return

        if _token_ok(scope.get("headers", []), expected):
            await self.app(scope, receive, send)
            return

        # Reject, transport-appropriately.
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"www-authenticate", b"Bearer"),
                ],
            }
        )
        await send(
            {"type": "http.response.body", "body": b'{"detail":"Unauthorized"}'}
        )
