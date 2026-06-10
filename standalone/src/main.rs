// ONEXUS standalone — Tauri shell that hosts the local FastAPI + Aurora UI.
//
// Boot flow:
//   1. Spawn the Python API server as a child process.
//   2. Wait for /api/health to respond (with a hard timeout).
//   3. Open the WebView at http://127.0.0.1:<port>/aurora (default 8765,
//      with automatic fallback to the next free port — see PORT_CANDIDATES).
//   4. On window close, kill the child process so the port frees up.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    onexus_lib::run()
}
