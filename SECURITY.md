# Security Policy

## Reporting a vulnerability

Please report security issues privately via GitHub's
[private vulnerability reporting](https://github.com/AllStreets/ONEXUS/security/advisories/new)
or by emailing connorevans29@gmail.com.

We will acknowledge within 72 hours and aim to patch within 14 days. Please do
not open a public issue for security problems.

## Hardening notes for operators

ONEXUS binds to `127.0.0.1` by default and trusts the local caller. If you
expose an instance beyond loopback (LAN, tunnel, shared host):

- Set `NEXUS_API_TOKEN` to a strong random value. Every API/WS request then
  requires `Authorization: Bearer <token>` (the health probe and dashboard
  shell stay open so deploy healthchecks work):

  ```bash
  export NEXUS_API_TOKEN=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
  ```

- Agent adapters are launched only if their command is on a built-in
  allowlist (`python`, `node`, `npx`, `uvx`, `docker`, ...). Extend it
  explicitly with `NEXUS_AGENT_COMMAND_ALLOWLIST` if you trust an additional
  launcher; a catalog update alone can never widen it.

## Kernel invariants

- The kernel (`nexus/kernel/`) makes no direct network calls; outbound HTTP
  routes through the aegis-gated client. Enforced by
  `tests/release/test_v1_acceptance.py`.
