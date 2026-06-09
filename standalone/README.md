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

1. On launch, the binary checks whether port `8000` is already in use.
2. If not, it spawns `python -m nexus.api.server` from the project root.
3. It polls the port until the FastAPI server accepts connections (max 20s).
4. It opens a native window pointing at `http://127.0.0.1:8000/aurora`.
5. On window close, it kills the child process so the port frees up cleanly.

The standalone binary is **not a re-implementation** — it embeds the exact same
HTML/CSS/JS the webapp serves. Same Aurora, same mood engine, same Aegis
prompts. The only difference is that the host OS owns the window chrome.

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

- The `.app` expects to find a Python with the ONEXUS package installed and
  importable as `nexus.api.server`. Either ship that as an `onexus`
  Homebrew formula, or document `pip install onexus` as a prerequisite.
- For a single-binary truly-standalone build, pair this with
  [PyOxidizer](https://pyoxidizer.readthedocs.io/) or
  [Python.framework embedding](https://docs.python.org/3/extending/embedding.html)
  to bundle the interpreter. Out of scope for the v1 wrapper.
