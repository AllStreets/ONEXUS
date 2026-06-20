# ONEXUS — standalone (Tauri)

A native macOS / Linux / Windows shell that hosts the ONEXUS FastAPI server
and points a WebView at the Aurora UI. Same code as the webapp; the wrapper
gives you real host-window controls, native drag-and-drop, a system tray, and
a single double-clickable `.app`.

```
standalone/
├── Cargo.toml             ← Rust crate manifest
├── tauri.conf.json        ← window config + bundle settings
├── build.rs               ← Tauri build script
├── capabilities/
│   └── default.json       ← which Tauri APIs the WebView may call
├── icons/                 ← app icons (icon.icns, icon.png, …)
└── src/
    ├── main.rs            ← entrypoint
    └── lib.rs             ← boots the Python server + opens the window
```

## What it does

1. On launch, it probes ports `8901–8909`. If one already hosts an ONEXUS
   server (verified via `/api/system/status`), it **attaches** to it; otherwise
   it spawns a fresh server on the first free port. It never glues the WebView
   onto a foreign service.
2. To start the server it tries, in order: `.venv/bin/onexus serve`, a global
   `onexus serve`, then `python -m nexus.cli serve`. The project root is found
   via `$ONEXUS_PROJECT_ROOT`, a cached path, or by walking up from the binary
   for `nexus/__init__.py` — so `/Applications/ONEXUS.app` finds your code.
3. It waits (max 20s) for the chosen port to accept a TCP connection.
4. It opens a native dark window at `http://127.0.0.1:<port>/aurora` — the host
   OS owns the traffic lights (the title bar is an overlay with the title
   hidden), so Aurora fills the whole surface.
5. It watches the project's `nexus/` tree: editing Aurora (html/css/js) hot-
   reloads the WebView; editing a `.py` restarts the backend. The native
   **File → Reload Backend** (⌘⇧R) and **View → Reload Aurora** (⌘R) menu items
   do the same on demand.
6. On window close or quit, it kills any server it spawned so the port frees.

The standalone binary is **not a re-implementation** — it serves the exact same
HTML/CSS/JS the webapp does. Same Aurora, same live kernel scene, same mood
engine, same Aegis prompts. The only difference is that the host OS owns the
window chrome, making it a real, double-clickable, sovereign appliance.

## Build (one-time setup)

```bash
brew install rust                       # or rustup-init for the official toolchain
cargo install tauri-cli --version "^2"
```

## Run in dev mode

From the repo root:

```bash
cargo tauri dev --config standalone/tauri.conf.json
```

This live-reloads the WebView when the Aurora JS/CSS changes (because Tauri
points at the dev URL, not the bundled `nexus/aurora` directory).

## Produce a release `.app` / `.dmg`

```bash
cargo tauri build --config standalone/tauri.conf.json
```

The signed app lands in `standalone/target/release/bundle/macos/ONEXUS.app`,
and a DMG in `standalone/target/release/bundle/dmg/`. Binary size is ~10 MB
because Tauri uses the host WebView (WKWebView on macOS, WebView2 on Windows,
WebKitGTK on Linux) instead of bundling Chromium.

## Distribution notes

- The `.app` expects to find a runnable ONEXUS server — either a project
  checkout with `.venv/bin/onexus`, a global `onexus` on `PATH`, or a Python
  that can run `python -m nexus.cli serve`. Ship that as an `onexus` Homebrew
  formula, or document `pip install onexus` as a prerequisite.
- For a single-binary truly-standalone build, pair this with
  [PyOxidizer](https://pyoxidizer.readthedocs.io/) or
  [Python.framework embedding](https://docs.python.org/3/extending/embedding.html)
  to bundle the interpreter. Out of scope for the v1 wrapper.
