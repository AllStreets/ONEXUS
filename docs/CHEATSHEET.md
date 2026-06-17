# ONEXUS Cheatsheet

Every keyboard shortcut, every CLI command, every useful curl one-liner — in one place.

Lives at `docs/CHEATSHEET.md` so the GitHub homepage stays uncluttered. Bookmark it.

---

## Keyboard shortcuts

### Aurora dashboard (browser / `.app`)

| Key | Action |
|---|---|
| <kbd>⌘ K</kbd> | Workspace switcher |
| <kbd>⌘ N</kbd> | New workspace |
| <kbd>⌘ L</kbd> | **Cortex multi-agent launcher** |
| <kbd>⌘ E</kbd> | Workshop (code + sandbox) |
| <kbd>⌘ /</kbd> | Web search |
| <kbd>⌘ P</kbd> | Settings |
| <kbd>⌘ 0</kbd> | Expanded six-panel cockpit overlay |
| <kbd>⌘ ⏎</kbd> | Send message from composer (or run in Workshop) |
| <kbd>?</kbd> | Open the 13-page guided tour (focus must be on body) |
| <kbd>Esc</kbd> | Close any open overlay / picker / cockpit / tour |

### Composer keyword routing

| Type into composer | What happens |
|---|---|
| `cortex` (alone) | Opens the Cortex launcher |
| `cortex <prompt>` | Opens the Cortex launcher with the rest of the message pre-filled |
| `@oracle hello` | Routes directly to Oracle, skipping Cortex's classifier |
| `@council weigh this option` | Routes directly to Council |
| `@specter red-team my plan` | Routes directly to Specter (any agent slug works after `@`) |

### Standalone `.app` (Tauri shell — native menu)

| Key | Menu item |
|---|---|
| <kbd>⌘ R</kbd> | View → Reload Aurora (refresh the WebView only) |
| <kbd>⌘ ⇧ R</kbd> | File → Reload Backend (kill + respawn the Python server, then reload WebView) |
| <kbd>⌘ Q</kbd> | Quit ONEXUS (cleanly kills the spawned server) |

The `.app` also auto-watches the project tree:
- `.py` edits → backend restart
- `.html / .css / .js / .svg / .png` in `nexus/aurora/` → WebView reload

---

## CLI

Installed by `pip install -e .[llm,api,tui,messaging]` as the `onexus` command.

### Daily

```bash
onexus serve --port 8901           # start the API + Aurora dashboard (default port)
onexus status                      # kernel status: db, modules, providers, port
onexus run                         # interactive REPL session against the kernel
onexus tui                         # rich-terminal dashboard (no browser needed)
onexus dashboard --port 8901       # launch the live web dashboard pointing at a server
```

`--port` defaults to **8901**. The standalone `.app` walks `[8901..8909]` and probes
`/api/system/status` so it never attaches to a non-ONEXUS service on the same port
(e.g., SMADP, jupyter, FastAPI dev servers).

### Trust / permissions

```bash
onexus allow <module>              # grant the module trust-check pass (e.g. allow oracle)
onexus deny <module>               # block all calls from a module
onexus revoke <module>              # reset a module's trust to 0.0 immediately
onexus trust <module>              # show trust history for a module
```

### Agents

```bash
onexus agent list                            # what's installed
onexus agent install <path-or-url>           # install a manifest
onexus agent uninstall <slug>                # remove an installed agent
```

### Federation (peer-to-peer)

```bash
onexus federation enable                     # enable federation on this instance
onexus federation status                     # connected peers
onexus federation discover                   # scan local network for ONEXUS peers
```

### MCP server (Model Context Protocol)

```bash
onexus mcp                                   # start the MCP server (stdio)
```

### Workflows

```bash
onexus workflow list                         # built-in pipelines
onexus workflow run <name> --var k=v         # run one
```

### Time-travel

```bash
onexus replay timeline --limit 50            # last N chronicle events
onexus replay snapshot 2026-06-09T20:00:00Z  # reconstruct state at a point in time
onexus replay diff <t1> <t2>                 # compare two timestamps
```

### Briefings

```bash
onexus briefing daily                        # autonomous "state of the kernel" report
onexus briefing daily --dry                  # preview without persisting
```

### Privacy

```bash
onexus forget                                # erase ALL ONEXUS memory (GDPR Article 17)
onexus forget --yes                          # skip the confirmation prompt
```

---

## Setup

```bash
# 1. Clone (and sibling-clone the catalog)
git clone https://github.com/AllStreets/ONEXUS.git
git clone https://github.com/AllStreets/ONEXUS-Agents.git    # in the same parent dir

cd ONEXUS

# 2. Fresh venv
python -m venv .venv && source .venv/bin/activate
pip install -e ".[llm,api,tui,messaging]"

# 3. Boot
onexus serve --port 8901
# open http://127.0.0.1:8901/aurora
```

### Local LLM (recommended)

```bash
# macOS
brew install ollama
brew services start ollama
ollama pull llama3.1:8b           # 5 GB — default model

# Smaller / bigger options
ollama pull llama3.2:3b           # ~2 GB · for 8 GB Macs
ollama pull qwen2.5:14b           # ~9 GB · better reasoning
```

### Cloud providers

Two ways — pick whichever fits the situation:

**In-app** (recommended for desktop use):
- Open Settings → Providers → CLOUD
- Click `+ add OpenAI API key` or `+ add Anthropic API key`
- Paste, press Enter — the key is stored at `~/.local/share/nexus/provider_keys.json` (`chmod 0600`), registered with the live router immediately, and never re-displayed. Remove from the same row.

**Environment** (CI / Docker):

```bash
export NEXUS_OPENAI_KEY=sk-...
export NEXUS_ANTHROPIC_KEY=sk-ant-...
export NEXUS_DEFAULT_PROVIDER=openai   # or anthropic / local / ollama
```

---

## Standalone `.app` (Tauri wrapper)

```bash
cd standalone

# Build the .app (release, no DMG)
cargo tauri build --bundles app

# Install to /Applications
cp -R target/release/bundle/macos/ONEXUS.app /Applications/

# First-run launch
open /Applications/ONEXUS.app
```

The `.app` resolves the project root in this order: `$ONEXUS_PROJECT_ROOT`,
`~/Library/Application Support/com.allstreets.onexus/project_root` (cached on
first run), walk up from the binary looking for `nexus/__init__.py`, `cwd`,
`cwd/..`.

---

## Useful API one-liners

All against `http://127.0.0.1:8901` by default.

### Status / health

```bash
curl -s http://127.0.0.1:8901/api/system/status | jq
curl -s http://127.0.0.1:8901/api/providers | jq
```

### Chat — single agent (Cortex picks)

```bash
curl -s -X POST -H "Content-Type: application/json" \
  -d '{"message":"hello","workspace_id":"hello-world"}' \
  http://127.0.0.1:8901/api/messages | jq
```

### Cortex multi-agent launch

```bash
# Fan one prompt to oracle + council in parallel
curl -s -X POST -H "Content-Type: application/json" \
  -d '{"message":"How should I structure this?","agents":["oracle","council"]}' \
  http://127.0.0.1:8901/api/cortex/launch | jq

# Let Cortex's classifier pick the top 3 for the prompt
curl -s -X POST -H "Content-Type: application/json" \
  -d '{"message":"red-team my plan","top_k":3}' \
  http://127.0.0.1:8901/api/cortex/launch | jq

# See which agents Cortex would pre-tick for a prompt
curl -s "http://127.0.0.1:8901/api/cortex/candidates?message=red-team+my+plan" | jq
```

### Trust feedback (thumb up / down)

```bash
# Thumb up — +0.12 to oracle's trust
curl -s -X POST -H "Content-Type: application/json" \
  -d '{"module":"oracle","accepted":true}' \
  http://127.0.0.1:8901/api/messages/feedback | jq

# Thumb down — −0.22
curl -s -X POST -H "Content-Type: application/json" \
  -d '{"module":"oracle","accepted":false}' \
  http://127.0.0.1:8901/api/messages/feedback | jq
```

### Provider keys

```bash
# Save a key (returns fingerprint only, never the key)
curl -s -X POST -H "Content-Type: application/json" \
  -d '{"provider":"openai","api_key":"sk-..."}' \
  http://127.0.0.1:8901/api/providers/keys | jq

# List configured keys (fingerprints only)
curl -s http://127.0.0.1:8901/api/providers/keys | jq

# Remove a key
curl -s -X DELETE http://127.0.0.1:8901/api/providers/keys/openai | jq
```

### Chat history (the same data the Settings tab shows)

```bash
# All workspaces with chat activity
curl -s http://127.0.0.1:8901/api/chat-history/workspaces | jq

# Agents you've talked to in one workspace
curl -s http://127.0.0.1:8901/api/chat-history/workspaces/hello-world/agents | jq

# Page of chats with one agent (50/page)
curl -s "http://127.0.0.1:8901/api/chat-history/workspaces/hello-world/agents/council/chats?offset=0&limit=50" | jq
```

### Workspaces

```bash
curl -s http://127.0.0.1:8901/api/workspaces | jq

# Create
curl -s -X POST -H "Content-Type: application/json" \
  -d '{"workspace_id":"build","name":"Build","tone":"emerald"}' \
  http://127.0.0.1:8901/api/workspaces | jq

# Switch
curl -s -X POST http://127.0.0.1:8901/api/workspaces/build/switch | jq

# Delete
curl -s -X DELETE http://127.0.0.1:8901/api/workspaces/build | jq
```

### Chronicle (audit log)

```bash
# Last 50 events
curl -s "http://127.0.0.1:8901/api/chronicle?limit=50" | jq

# Filter by source + event type
curl -s "http://127.0.0.1:8901/api/chronicle?source=aegis&event_type=aegis.trust_change&limit=20" | jq

# Aggregate stats
curl -s http://127.0.0.1:8901/api/chronicle/stats | jq
```

---

## Troubleshooting

### "detail not found" on a blank page

Something else is on port 8000 (often `smadp` if you have that project, jupyter,
random FastAPI dev servers). The `.app` and `onexus serve` both default to
**8901** now and walk forward through `8901..8773` if 8901 is also taken. If
you're seeing the old behavior, you're running a stale `.app` — rebuild:

```bash
cd standalone
cargo clean && cargo tauri build --bundles app
cp -R target/release/bundle/macos/ONEXUS.app /Applications/
```

### Where things live

| Thing | Path |
|---|---|
| Kernel data | `~/.local/share/nexus/` |
| Workspaces | `~/.local/share/nexus/workspaces/` |
| Per-workspace Engram | `~/.local/share/nexus/workspaces/<id>/engram/episodic.sqlite` |
| Chronicle audit log | `~/.local/share/nexus/nexus.db` |
| Saved provider keys | `~/.local/share/nexus/provider_keys.json` (`chmod 0600`) |
| `.app` project-root cache | `~/Library/Application Support/com.allstreets.onexus/project_root` |
| `.app` binary | `/Applications/ONEXUS.app/Contents/MacOS/onexus` |
| Tauri build output | `standalone/target/release/bundle/macos/ONEXUS.app` |
