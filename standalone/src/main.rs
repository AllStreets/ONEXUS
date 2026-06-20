// ONEXUS standalone — Tauri shell that hosts the local FastAPI + Aurora UI.
//
// Boot flow (see lib.rs for the implementation):
//   1. Probe PORT_CANDIDATES (8901–8909). Attach to an already-running ONEXUS
//      server if one is found; otherwise spawn the Python API server on the
//      first free port (.venv/bin/onexus, a global `onexus`, or `python -m
//      nexus.cli serve`, in that order).
//   2. Wait for the chosen port to accept a TCP connection (20s hard timeout).
//   3. Open the WebView at http://127.0.0.1:<port>/aurora.
//   4. Watch the project's nexus/ tree and hot-reload the WebView (Aurora edits)
//      or restart the backend (.py edits); File/View menu items do this too.
//   5. On window close or app exit, kill any child we spawned so the port frees.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    onexus_lib::run()
}
