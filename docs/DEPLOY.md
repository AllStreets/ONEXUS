# Deploying ONEXUS

ONEXUS is a single container — kernel + API + Aurora dashboard. You can
run it locally, on Railway, on Fly.io, or on any Docker host.

## Local (development)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[llm,api,tui,messaging]"
onexus serve --port 8901
```

Open <http://127.0.0.1:8901/aurora>.

## Docker

```bash
docker build -t onexus:local .
docker run -p 8000:8000 -v $(pwd)/.data:/data onexus:local
```

The agent catalog is baked into the image at build time (`/opt/onexus/catalog`)
so the OS runs offline. Mount `/data` for workspace memory + chronicle to
persist across container restarts.

## Railway (one-click)

A `railway.json` is included. From the Railway dashboard:

1. **New Project → Deploy from GitHub repo → AllStreets/ONEXUS**.
2. Railway reads `railway.json` and builds with the Dockerfile.
3. Set environment variables (any are optional):
   - `NEXUS_OPENAI_KEY` / `NEXUS_ANTHROPIC_KEY` — LLM providers.
   - `NEXUS_SEARCH_PROVIDER=duckduckgo` (default) or `brave` + `NEXUS_BRAVE_KEY`.
   - `NEXUS_FEDERATION_ENABLED=1` to enable federation between instances.
4. Add a volume mounted at `/data` for persistent workspace storage.
5. Health probe is automatic via `/api/system/health`.

The default plan ($5/mo) is enough for personal use.

## Fly.io / Render / Vercel

Any Docker host works. For Fly.io:

```bash
fly launch --image onexus:local --vm-memory 1024 --vm-cpu-kind shared
```

Vercel does not run long-lived processes natively — use Railway or Fly.io
for the kernel + API, and you can host the Aurora dashboard's static assets
on Vercel if you want CDN edge delivery. The dashboard is just HTML/CSS/JS;
point it at your Railway API URL via a build-time env var.

## Nightly catalog rebuild

The included GitHub Actions workflow (`.github/workflows/nightly-catalog.yml`)
runs every night at 06:00 UTC:

1. Reads the head SHA of `AllStreets/ONEXUS-Agents`.
2. Builds the Dockerfile with `CATALOG_REF=<sha>` so the new agents land
   inside the image.
3. Pushes to GHCR under three tags:
   - `:nightly` — latest rolling
   - `:catalog-<sha>` — reproducible reference
   - `:<commit-sha>` — code reference

Trigger manually via the Actions tab or push to `main` to refresh on demand.

## What gets bundled

| Path inside the image      | Purpose |
|----------------------------|---------|
| `/opt/onexus/nexus`        | Python package |
| `/opt/onexus/catalog`      | Agents catalog (6,700+ manifests, ~570 with MCP adapters) |
| `/data`                    | Workspace memory, chronicle, aegis grants (mount this) |

## Security notes

- The kernel itself never touches the network — there's a static test
  (`tests/release/test_v1_acceptance.py`) that enforces this.
- The Aurora **Workshop** runs code in a subprocess sandbox with a stripped
  environment. For stronger isolation, use a container-per-run runner
  (planned).
- Aegis gates every outbound HTTP request — if you set `NEXUS_DEFAULT_PROVIDER=local`
  the OS reaches **no** network endpoints at all.
