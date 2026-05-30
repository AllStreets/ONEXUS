# ONEXUS migration kit

Move a running ONEXUS install to a new Mac in two scripts.

## What gets migrated

| Item                            | How                                    |
|---------------------------------|----------------------------------------|
| Code (`NEXUS`, `ONEXUS-Agents`) | `git clone` from GitHub                |
| `nexus.db` (memory, trust, log) | tarball via `bundle.sh`                |
| Python env                      | recreated by `bootstrap-new-mac.sh`    |
| LLM provider API keys           | re-entered via dashboard (not bundled) |
| macOS Privacy permissions       | re-granted in System Settings          |

## On the OLD Mac

```bash
cd ~/Downloads/NEXUS
bash migrate/bundle.sh
```

Produces `~/Desktop/onexus-migration-bundle.tar.gz` (~200 KB).
Optionally stop the server first; the script uses `sqlite3 .backup` so
it's safe with the server running, but a stopped server is cleaner.

Transfer the tarball to the new Mac (AirDrop is easiest for ~200 KB).

## On the NEW Mac

```bash
# 1. Install prerequisites
xcode-select --install        # gives you git, build tools
brew install python@3.12      # if not present

# 2. Clone the repo
mkdir -p ~/Downloads && cd ~/Downloads
git clone https://github.com/AllStreets/ONEXUS.git NEXUS
cd NEXUS

# 3. Drop onexus-migration-bundle.tar.gz on the Desktop, then:
bash migrate/bootstrap-new-mac.sh
```

The bootstrap script:
1. Verifies the bundle is on Desktop
2. Clones `ONEXUS-Agents` as a sibling directory
3. Creates `.venv` and installs all deps (`llm`, `api`, `tui` extras)
4. Restores `nexus.db` to `~/.local/share/nexus/`
5. Prints the remaining manual steps

## Manual steps the script can't do

1. **macOS Privacy** — grant the new python binary access to your Downloads
   folder so it can read the `ONEXUS-Agents/catalog` directory.
   `System Settings → Privacy & Security → Files and Folders`.
2. **Re-enter API keys** — open the dashboard at
   `http://localhost:8600/dashboard`, click the LLM Providers icon,
   and add your OpenAI / Anthropic keys.

## Verifying the migration

```bash
sqlite3 ~/.local/share/nexus/nexus.db "SELECT module_name, trust_score FROM aegis_policies ORDER BY trust_score DESC;"
```

Trust scores should match the old machine.
