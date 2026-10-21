# Agent store: install any catalog agent that ships an MCP server

*2026-10-20. Approved in conversation (approach A); this file records it.*

## Goal

A person using ONEXUS picks an agent from the ONEXUS-Agents catalog, clicks Install, and
gets a working MCP server for that agent, running confined. Recipes are produced by
programs from evidence in the agent's repository and package registry. No LLM writes or
chooses anything.

## What it covers, and what it doesn't (v1)

- In: agents whose repository shows they are an MCP server installable from **npm**,
  **PyPI** or a published **container image**, speaking **stdio**.
- Out, with room in the format: building from a repo's own Dockerfile, hosted remote MCP
  servers reached by URL, Hugging Face model templates.
- The catalog's `runnable` flag is keyword-detected and overcounts (a sample of 80 of the
  592 found apps that use MCP, MCP clients and awesome-lists). The verifier is what proves
  an entry installs; the store shows only verified recipes.

## Pieces

```
catalog entry → resolver → recipe (unverified) → verifier (CI) → recipe (verified)
      → ONEXUS store → install (pull prebuilt, or build locally) → permission card → launch confined
```

### Recipe (ONEXUS-Agents `recipes/<slug>.json`)

| Field | Meaning |
|---|---|
| `slug`, `recipe_version` | identity; format version 1 |
| `source` | `{repo, commit}` the evidence was read at |
| `derived_from` | `server.json`, `readme-config` or `package-manifest` |
| `install` | `{kind: npm\|pypi\|oci, package or image, version or digest}`, always exact |
| `command` | argv inside the container; `transport` is `stdio` |
| `env` | `[{name, required, secret}]` |
| `hosts` | `{proposed: [...], evidence: {host: [where it was found]}}` |
| `license` | from the catalog |
| `dockerfile` | the exact Dockerfile the verifier built, so ONEXUS builds the same thing |
| `verified` | `{at, ok, tools, handshake_ms, image_id}` or a failure `{at, ok: false, stage, reason}` |
| `prebuilt` | `{image}` pinned by digest, for the instant-install set |

### Resolver (ONEXUS-Agents `pipeline/recipes/resolve.py`)

Tries sources in order of exactness and stops at the first that yields a recipe:
1. `server.json` at the repo root (the official MCP Registry format): `packages[]` gives
   registry type, identifier, version, transport and environment variables.
2. The README's `"mcpServers"` config block: `npx -y pkg`, `uvx pkg`, `docker run image`
   map to npm, PyPI and oci; `env` gives the variable names.
3. The package manifest: `package.json` depending on `@modelcontextprotocol/sdk` with a
   `bin`, or `pyproject.toml` depending on `mcp`/`fastmcp` with `[project.scripts]`, and the
   package actually published on npm or PyPI.
Unpinned versions are resolved to the registry's current version. Everything else gets no
recipe, and the reason is recorded.

### Verifier (ONEXUS-Agents `pipeline/recipes/verify.py`)

Generates the Dockerfile from a fixed template per install kind (Node 22 slim + `npm install
-g`, Python 3.12 slim + `pip install`, or the image as published), builds it (network only
while installing), then runs it with ONEXUS's confinement flags and no network, sends the
MCP `initialize` and `tools/list`, and records the tool names. Required variables get a
placeholder value so servers that only need a key at call time can start. It scans the
package's own installed files for hosts (`https://host` literals, minus schema, docs and
example hosts) and adds hosts implied by known variables (`GITHUB_TOKEN` → `api.github.com`).
A failure records the stage (build, start, handshake) and the reason.

### ONEXUS (`nexus/store/`)

- `recipes.py` loads verified recipes from the catalog checkout.
- `install.py` pulls the prebuilt image or builds the recorded Dockerfile, streaming
  progress; writes `{data_dir}/store/<slug>.json` with the image, approved hosts and the
  names of keys the person supplied. Key values go to `{data_dir}/store/secrets.json`
  (0600), never to logs or responses, the same way provider keys are kept.
- `AgentCatalog.load_adapter` returns a descriptor built from an install record when one
  exists, with `confinement: {image, hosts}`, so `AgentLauncher` and round 3's `confine.py`
  launch it unchanged.
- API under `/api/store`: list, detail, install (a job with progress), install status,
  approve hosts, uninstall.
- Aurora store page, on the redesign's components: browse and search verified agents,
  agent page (what it does, its tools, where the recipe came from, license, hosts with
  evidence), Install with live steps, then the permission card (tools, keys, hosts to
  approve). Built after the redesign branch lands.

### Prebuilt set

A short list (`recipes/prebuilt.txt`) of popular, verified, permissively licensed (MIT,
Apache-2.0, BSD, ISC) recipes is built and published to GHCR by CI and pinned by digest.
Everything else builds locally on install. No other third-party code is redistributed.

## Errors

Every failure is shown in words with its stage: no recipe (and why), verification failed
(stage and reason), build failed on this machine (the build log tail), Docker not running.
Nothing installs half-way: a failed install leaves no record.

## Testing

- Resolver: unit tests on fixture `server.json` files, README blocks and manifests,
  including the wrong-but-plausible cases (an MCP client, an awesome-list).
- Verifier: an integration test that builds and handshakes one small real npm server and
  one PyPI server (skips without Docker).
- ONEXUS: install record round-trip, secrets file mode and redaction, `load_adapter` from
  an install record, the launch through confinement, the API, and an end-to-end store
  install of one verified recipe.
