# Automation: nightly catalog pipeline

How the ONEXUS-Agents catalog reaches NEXUS, what runs unattended, and how to
stop it.

## Data flow

```
ONEXUS-Agents nightly refresh (cron 13:00 UTC, lands on main ~14:00-20:00 UTC)
        |
        v
Nightly catalog rebuild (.github/workflows/nightly-catalog.yml, cron 06:00 UTC)
  - resolves ONEXUS-Agents main HEAD SHA
  - docker build with CATALOG_REF=<sha>  (catalog baked at /opt/onexus/catalog)
  - pushes ghcr.io/allstreets/onexus/onexus:{nightly, catalog-<sha>, <commit>}
        |
        v
Deployments that pull :nightly get the fresh catalog on next restart.
Local/dev instances read the sibling clone instead (nexus/agents/catalog.py):
NEXUS_AGENTS_CATALOG env var, else ../ONEXUS-Agents. Refresh = git pull of the
ONEXUS-Agents clone + server restart (the catalog loads once at startup).
```

The MCP tools `nexus_agents_browse`, `nexus_agents_search`, and
`nexus_agents_info` (nexus/mcp/tools.py) serve whatever catalog the running
instance loaded.

## Sequencing

The rebuild runs at 06:00 UTC because the upstream refresh fires 13:00 UTC and
in practice lands on main between ~14:00 and ~20:00 UTC; by 06:00 the snapshot
is always complete. The rebuild only reads the upstream repo; it never writes
to it, so it cannot race or re-trigger anything.

## Kill switch

Set the repository Actions variable `AGENTS_SYNC_ENABLED` to `false`
(Settings > Secrets and variables > Actions > Variables, or
`gh variable set AGENTS_SYNC_ENABLED -b false -R AllStreets/ONEXUS`).
The rebuild job skips entirely while the value is `false`. Unset or any other
value means enabled. Re-enable with `gh variable delete AGENTS_SYNC_ENABLED`
or set it to `true`.

## Failure behavior

A failed rebuild opens (or comments on) a GitHub issue labeled `bot-failure`
instead of dying silently. The deployed image keeps serving the previous
catalog snapshot until the failure is fixed; nothing downstream breaks.

## Safety properties

- Idempotent: rebuilding the same catalog SHA produces the same image; tags
  are overwritten in place, nothing accumulates.
- No write-back: the workflow has `contents: read` on this repo and no
  credentials for ONEXUS-Agents, so it cannot create commit loops.
- Other automation in this repo: `daily-briefing.yml` (13:00 UTC, commits
  reports/ via bot PR) and `deploy-site.yml` (push-triggered Pages deploy).
  Neither consumes the image; the briefing reads its own clone of the
  catalog read-only.
