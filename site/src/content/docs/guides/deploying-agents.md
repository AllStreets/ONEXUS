---
title: Deploying Agents
description: How to connect the ONEXUS-Agents catalog to your ONEXUS instance and deploy open-source agents via MCP.
sidebar:
  order: 2
---

ONEXUS ships with 9 cognitive modules -- the brain. For task-specific work (coding, browser automation, data engineering, financial modeling), you connect external agents from the [ONEXUS-Agents](https://github.com/AllStreets/ONEXUS-Agents) catalog.

## Setup

Clone the catalog and set the environment variable:

```bash
git clone https://github.com/AllStreets/ONEXUS-Agents.git ~/onexus-agents
export NEXUS_AGENTS_CATALOG=~/onexus-agents
onexus run
```

ONEXUS reads the catalog at startup. The catalog is a directory of JSON files -- one per agent, organized by category. No database, no server. The git history is the audit log.

## Browsing the Catalog

Three MCP tools expose the catalog to any connected client:

### `nexus_agents_browse`

List agents by category, sorted by composite score. Filter to runnable-only to see agents with MCP adapters ready for dispatch.

```json
{ "category": "coding", "runnable_only": true, "limit": 10 }
```

### `nexus_agents_search`

Keyword search across agent names, taglines, tags, and categories.

```json
{ "query": "browser automation", "limit": 5 }
```

### `nexus_agents_info`

Full metadata for a specific agent, including its MCP adapter descriptor (transport, command, env keys, capabilities, trust floor).

```json
{ "slug": "aider" }
```

## Runnable vs Catalogued

Every agent in the catalog has metadata: name, category, stars, license, composite score, rank. But only agents marked `runnable: true` have an MCP adapter -- the bridge that lets ONEXUS actually dispatch work to them.

A runnable agent declares:
- `adapter_ref` -- path to the MCP server descriptor (`adapters/<name>/mcp.json`)
- The adapter specifies transport (stdio/SSE), command, env keys, capabilities, and a `trust_floor`

The trust floor is the minimum Aegis trust score required before ONEXUS will dispatch to the agent. This prevents untrusted agents from executing without earning their way up.

## The Adapter Contract

Each adapter lives under `adapters/<name>/` in the ONEXUS-Agents repo:

```
adapters/aider/
  mcp.json    -- MCP server descriptor
  README.md   -- one-line install + one-line invocation
```

The `mcp.json` shape:

```json
{
  "name": "aider",
  "transport": "stdio",
  "command": "aider-mcp",
  "args": [],
  "env": {
    "OPENAI_API_KEY": { "required": true, "description": "Model API key." }
  },
  "capabilities": {
    "tools": ["edit_file", "run_tests", "git_commit"],
    "resources": ["repo"]
  },
  "trust_floor": 0.55,
  "default_tier": "ADVISOR"
}
```

Agents that don't speak MCP natively can use a thin Python shim (`adapters/<name>/server.py`) that wraps the agent's CLI or library in an `mcp.server` stdio loop.

## Building Your Own Agent

1. Build the agent in any language or framework.
2. Wrap it in an MCP server (stdio transport recommended).
3. Add a catalog entry: `catalog/<category>/<your-agent>.json`
4. Add an adapter: `adapters/<your-agent>/mcp.json`
5. Open a PR to [ONEXUS-Agents](https://github.com/AllStreets/ONEXUS-Agents).

CI validates the schema. The nightly pipeline re-scores every agent, and your submission becomes a first-class member of the ranking pool the next night after merge.

## Keeping the Catalog Updated

The catalog refreshes nightly via a pipeline that crawls GitHub and Hugging Face, scores candidates, and truncates each category to the top 100. Pull the latest:

```bash
cd ~/onexus-agents && git pull
```

ONEXUS will pick up the changes on next startup, or call `reload()` on the catalog if you have a live session.
