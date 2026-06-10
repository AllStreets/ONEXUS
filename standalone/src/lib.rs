// ONEXUS standalone — Tauri shell library.
//
// Boots the FastAPI server, waits for it to accept TCP, opens the WebView,
// and tears down the child process when the shell window closes.
//
// Project-root resolution:
//   1) $ONEXUS_PROJECT_ROOT environment variable
//   2) ~/Library/Application Support/com.allstreets.onexus/project_root
//      (written automatically the first time the binary runs from inside
//      a checkout that contains nexus/__init__.py)
//   3) Walk up from the executable looking for nexus/__init__.py
//   4) The current working directory
//   5) The parent of the current working directory
//
// Once resolved, the path is cached on disk so /Applications/ONEXUS.app can
// find your code from anywhere it's launched.

use std::fs;
use std::io::{BufRead, BufReader, Read, Write};
use std::net::TcpStream;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::thread;
use std::time::{Duration, Instant};

use notify::RecursiveMode;
use notify_debouncer_mini::new_debouncer;
use tauri::menu::{MenuBuilder, MenuItemBuilder, SubmenuBuilder};
use tauri::{AppHandle, Manager, RunEvent, WindowEvent};

const HOST: &str = "127.0.0.1";
// 8765 by default — chosen to avoid common dev-tool ports (8000 was a magnet
// for FastAPI defaults, jupyter, SMADP, etc.). We probe candidates in order
// and either attach to an existing ONEXUS server or spawn one on the first
// free port.
const PORT_CANDIDATES: &[u16] = &[8765, 8766, 8767, 8768, 8769, 8770, 8771, 8772, 8773];
const HEALTH_TIMEOUT_SECS: u64 = 20;
const BUNDLE_ID: &str = "com.allstreets.onexus";

/// Resolved port for this run. Set once in `run()` before any helper uses it.
/// Read with `current_port()`.
use std::sync::atomic::{AtomicU16, Ordering};
static PORT: AtomicU16 = AtomicU16::new(8765);
fn current_port() -> u16 { PORT.load(Ordering::SeqCst) }

/// Wrapper around the spawned Python child so we can kill it on shutdown
/// and on demand (e.g. the File → Reload Backend menu item).
struct ServerChild(Mutex<Option<Child>>);

impl ServerChild {
    fn take(&self) -> Option<Child> {
        self.0.lock().ok().and_then(|mut g| g.take())
    }
    fn replace(&self, new: Option<Child>) {
        if let Ok(mut g) = self.0.lock() {
            if let Some(old) = g.take() {
                drop(old); // Drop closes pipes; kill is the caller's job.
            }
            *g = new;
        }
    }
}

// ── Project-root resolution + persistence ────────────────────────────────────

fn config_dir() -> Option<PathBuf> {
    let home = std::env::var_os("HOME").map(PathBuf::from)?;
    Some(home.join("Library").join("Application Support").join(BUNDLE_ID))
}

fn config_file() -> Option<PathBuf> {
    config_dir().map(|d| d.join("project_root"))
}

fn read_cached_root() -> Option<PathBuf> {
    let path = config_file()?;
    let contents = fs::read_to_string(&path).ok()?;
    let trimmed = contents.trim();
    if trimmed.is_empty() {
        return None;
    }
    let candidate = PathBuf::from(trimmed);
    if is_valid_project_root(&candidate) {
        Some(candidate)
    } else {
        None
    }
}

fn write_cached_root(root: &Path) {
    let Some(dir) = config_dir() else { return };
    if fs::create_dir_all(&dir).is_err() {
        return;
    }
    let Some(path) = config_file() else { return };
    if let Ok(mut f) = fs::File::create(&path) {
        let _ = writeln!(f, "{}", root.display());
    }
}

fn is_valid_project_root(path: &Path) -> bool {
    path.join("nexus").join("__init__.py").exists()
}

fn walk_up_for_project(start: &Path, max_steps: usize) -> Option<PathBuf> {
    let mut cursor = start.to_path_buf();
    for _ in 0..max_steps {
        if is_valid_project_root(&cursor) {
            return Some(cursor);
        }
        if !cursor.pop() {
            break;
        }
    }
    None
}

fn resolve_project_root() -> Option<PathBuf> {
    // 1. Environment variable.
    if let Some(env) = std::env::var_os("ONEXUS_PROJECT_ROOT") {
        let path = PathBuf::from(env);
        if is_valid_project_root(&path) {
            return Some(path);
        }
    }

    // 2. Cached config file.
    if let Some(cached) = read_cached_root() {
        return Some(cached);
    }

    // 3. Walk up from executable.
    if let Ok(exe) = std::env::current_exe() {
        if let Some(parent) = exe.parent() {
            if let Some(root) = walk_up_for_project(parent, 8) {
                write_cached_root(&root);
                return Some(root);
            }
        }
    }

    // 4. Walk up from cwd.
    if let Ok(cwd) = std::env::current_dir() {
        if let Some(root) = walk_up_for_project(&cwd, 8) {
            write_cached_root(&root);
            return Some(root);
        }
    }

    None
}

// ── Server lifecycle ─────────────────────────────────────────────────────────

fn spawn_python_server() -> Result<Child, String> {
    let root = resolve_project_root()
        .ok_or_else(|| {
            "could not locate ONEXUS project root.\n\
             Set $ONEXUS_PROJECT_ROOT, run the .app once from inside a checkout, \
             or place nexus/__init__.py in a parent dir of the binary."
                .to_string()
        })?;

    let mut command = if root.join(".venv/bin/onexus").exists() {
        let mut c = Command::new(root.join(".venv/bin/onexus"));
        c.arg("serve").arg("--port").arg(current_port().to_string());
        c
    } else if which::which("onexus").is_ok() {
        let mut c = Command::new("onexus");
        c.arg("serve").arg("--port").arg(current_port().to_string());
        c
    } else {
        let python = ["python3.14", "python3.13", "python3.12", "python3.11", "python3", "python"]
            .iter()
            .find(|name| which::which(name).is_ok())
            .ok_or_else(|| "no python3 found on PATH and no .venv/bin/onexus".to_string())?;
        let mut c = Command::new(python);
        c.arg("-m").arg("nexus.cli").arg("serve").arg("--port").arg(current_port().to_string());
        c
    };

    let mut child = command
        .current_dir(&root)
        .env("ONEXUS_STANDALONE", "1")
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("failed to spawn ONEXUS server: {e}"))?;

    if let Some(out) = child.stdout.take() {
        thread::spawn(move || {
            for line in BufReader::new(out).lines().flatten() {
                println!("[onexus] {line}");
            }
        });
    }
    if let Some(err) = child.stderr.take() {
        thread::spawn(move || {
            for line in BufReader::new(err).lines().flatten() {
                eprintln!("[onexus] {line}");
            }
        });
    }

    Ok(child)
}

fn wait_for_server() -> Result<(), String> {
    let deadline = Instant::now() + Duration::from_secs(HEALTH_TIMEOUT_SECS);
    let port = current_port();
    let addr = format!("{HOST}:{port}");
    while Instant::now() < deadline {
        if TcpStream::connect_timeout(
            &addr.parse().map_err(|e| format!("bad address: {e}"))?,
            Duration::from_millis(300),
        )
        .is_ok()
        {
            return Ok(());
        }
        thread::sleep(Duration::from_millis(200));
    }
    Err(format!("server never came up on {addr} within {HEALTH_TIMEOUT_SECS}s"))
}

fn port_is_listening_on(port: u16) -> bool {
    TcpStream::connect_timeout(
        &format!("{HOST}:{port}").parse().unwrap(),
        Duration::from_millis(200),
    )
    .is_ok()
}

fn port_is_listening() -> bool {
    port_is_listening_on(current_port())
}

/// Talk HTTP/1.1 to whatever's on `port` and decide whether it's ONEXUS.
///
/// ONEXUS responds to `/api/system/status` with JSON containing `"data_dir"`
/// and `"modules_loaded"`. Any other service (SMADP's FastAPI, jupyter, a
/// random dev server) either 404s or returns unrelated content — we'd
/// rather pick another port than glue our WebView onto someone else's UI.
fn probe_is_onexus(port: u16) -> bool {
    let addr = match format!("{HOST}:{port}").parse() {
        Ok(a) => a,
        Err(_) => return false,
    };
    let mut stream = match TcpStream::connect_timeout(&addr, Duration::from_millis(500)) {
        Ok(s) => s,
        Err(_) => return false,
    };
    let _ = stream.set_read_timeout(Some(Duration::from_millis(1000)));
    let req = format!(
        "GET /api/system/status HTTP/1.1\r\nHost: {HOST}\r\nConnection: close\r\nUser-Agent: onexus-standalone\r\n\r\n",
    );
    if stream.write_all(req.as_bytes()).is_err() {
        return false;
    }
    let mut buf = Vec::with_capacity(4096);
    let _ = stream.take(8192).read_to_end(&mut buf);
    let body = String::from_utf8_lossy(&buf);
    // Markers from nexus.api.routes.system.status — these wouldn't co-occur
    // accidentally in another project's 200 response.
    body.contains("\"data_dir\"") && body.contains("\"modules_loaded\"")
}

/// Walk PORT_CANDIDATES, returning (port, already_up_as_onexus).
/// - If a candidate is free → spawn a fresh server there.
/// - If a candidate is occupied AND the occupant is ONEXUS → attach.
/// - If occupied by something else → skip to the next candidate.
fn pick_port() -> Option<(u16, bool)> {
    for &p in PORT_CANDIDATES {
        if !port_is_listening_on(p) {
            return Some((p, false));
        }
        if probe_is_onexus(p) {
            return Some((p, true));
        }
        eprintln!("[onexus] port {p} is taken by a non-ONEXUS service, trying next");
    }
    None
}

/// Reload the backend: kill any child we spawned, kill any other onexus
/// server we can find on the port, then spawn a fresh one. Used by the
/// File → Reload Backend menu item.
fn reload_backend(app: &AppHandle) {
    eprintln!("[onexus] Reload Backend requested");
    // 1) Kill our spawned child if any.
    if let Some(state) = app.try_state::<ServerChild>() {
        if let Some(mut child) = state.take() {
            let _ = child.kill();
            let _ = child.wait();
        }
    }

    // 2) Kill any leftover onexus process on the port (in case the user
    //    started one themselves from a terminal).
    #[cfg(target_os = "macos")]
    {
        let _ = Command::new("pkill")
            .args(["-9", "-f", "onexus serve"])
            .status();
    }

    // 3) Wait briefly for the port to free, then spawn a fresh server.
    for _ in 0..10 {
        if !port_is_listening() {
            break;
        }
        thread::sleep(Duration::from_millis(200));
    }

    match spawn_python_server() {
        Ok(child) => {
            if let Err(e) = wait_for_server() {
                eprintln!("[onexus] reload: {e}");
            }
            if let Some(state) = app.try_state::<ServerChild>() {
                state.replace(Some(child));
            }
            // Tell the WebView to reload now that the new server is up.
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.eval("location.reload()");
            }
        }
        Err(e) => {
            eprintln!("[onexus] reload failed: {e}");
        }
    }
}

fn reload_aurora(app: &AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.eval("location.reload()");
    }
}

// ── File watcher ─────────────────────────────────────────────────────────────

/// Categorise a changed path. Paths we don't care about (caches, build output,
/// editor backup files) return `None` so the watcher ignores them.
enum ChangeKind {
    Backend,  // .py — needs full server restart
    Aurora,   // html/css/js in nexus/aurora/ — just reload the WebView
}

fn classify_change(path: &Path) -> Option<ChangeKind> {
    let s = path.to_string_lossy();

    // Skip caches, vcs, virtualenv, target output.
    for skip in [
        "__pycache__",
        "/.git/",
        "/.venv/",
        "/target/",
        "/.worktrees/",
        "/node_modules/",
        "/site-packages/",
        ".pyc",
        ".pyo",
        ".swp",
        ".swo",
        "~",      // editor backups
        ".DS_Store",
    ] {
        if s.contains(skip) {
            return None;
        }
    }

    let aurora_marker = format!("{}aurora{}", std::path::MAIN_SEPARATOR, std::path::MAIN_SEPARATOR);
    let is_aurora_subtree = s.contains(&aurora_marker);

    let ext = path
        .extension()
        .and_then(|e| e.to_str())
        .unwrap_or("")
        .to_ascii_lowercase();

    // Aurora subtree → frontend reload (any html/css/js/svg/png edit there is
    // visible after a WebView refresh).
    if is_aurora_subtree {
        if matches!(ext.as_str(), "html" | "css" | "js" | "svg" | "png" | "jpg" | "jpeg") {
            return Some(ChangeKind::Aurora);
        }
        return None;
    }

    // Anything else .py → backend restart.
    if ext == "py" {
        return Some(ChangeKind::Backend);
    }
    None
}

/// Spawn a background thread that watches `project_root/nexus/` and triggers
/// the appropriate reload when files change. Uses a debouncer so a batch
/// save (e.g. find-and-replace across 12 files) coalesces into one reload.
fn start_watcher(app: AppHandle, project_root: PathBuf) {
    let watch_dir = project_root.join("nexus");
    if !watch_dir.exists() {
        eprintln!("[onexus] watcher: {} does not exist; auto-reload disabled", watch_dir.display());
        return;
    }

    thread::spawn(move || {
        let (tx, rx) = std::sync::mpsc::channel();
        let mut debouncer = match new_debouncer(Duration::from_millis(800), tx) {
            Ok(d) => d,
            Err(e) => {
                eprintln!("[onexus] watcher: failed to create debouncer: {e}");
                return;
            }
        };

        if let Err(e) = debouncer.watcher().watch(&watch_dir, RecursiveMode::Recursive) {
            eprintln!("[onexus] watcher: failed to watch {}: {e}", watch_dir.display());
            return;
        }
        eprintln!("[onexus] watcher: watching {}", watch_dir.display());

        for batch in rx {
            let Ok(events) = batch else { continue };

            // Decide what kind of reload this batch warrants. Backend wins
            // over Aurora because restarting the server also reloads the
            // WebView at the end of the cycle.
            let mut need_backend = false;
            let mut need_aurora = false;
            let mut paths_changed: Vec<PathBuf> = Vec::new();

            for ev in events {
                let path = ev.path;
                paths_changed.push(path.clone());
                match classify_change(&path) {
                    Some(ChangeKind::Backend) => need_backend = true,
                    Some(ChangeKind::Aurora) => need_aurora = true,
                    None => {}
                }
            }

            if need_backend {
                eprintln!("[onexus] watcher: backend change detected ({} path{}); reloading server",
                          paths_changed.len(),
                          if paths_changed.len() == 1 { "" } else { "s" });
                reload_backend(&app);
            } else if need_aurora {
                eprintln!("[onexus] watcher: aurora change detected ({} path{}); reloading WebView",
                          paths_changed.len(),
                          if paths_changed.len() == 1 { "" } else { "s" });
                reload_aurora(&app);
            }
        }
    });
}

// ── App bootstrap ────────────────────────────────────────────────────────────

pub fn run() {
    // Pick a port: prefer free, fall back to attaching to an existing
    // ONEXUS server, never glue ourselves onto a foreign service.
    let (chosen_port, already_up_onexus) = pick_port()
        .expect("no free or ONEXUS-occupied port in PORT_CANDIDATES");
    PORT.store(chosen_port, Ordering::SeqCst);
    eprintln!(
        "[onexus] using {HOST}:{chosen_port} (already_up_onexus={already_up_onexus})"
    );

    let server: Option<Child> = if already_up_onexus {
        eprintln!("[onexus] attaching to existing ONEXUS server on port {chosen_port}");
        None
    } else {
        match spawn_python_server() {
            Ok(child) => {
                if let Err(e) = wait_for_server() {
                    eprintln!("[onexus] {e}");
                }
                Some(child)
            }
            Err(e) => {
                eprintln!("[onexus] failed to start server: {e}");
                None
            }
        }
    };

    let server_state = ServerChild(Mutex::new(server));

    let app = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(server_state)
        .setup(|app| {
            // Native macOS menu — File → Reload Backend / View → Reload Aurora.
            let handle = app.handle().clone();

            let reload_backend_item = MenuItemBuilder::new("Reload Backend")
                .id("reload_backend")
                .accelerator("CmdOrCtrl+Shift+R")
                .build(app)?;
            let reload_aurora_item = MenuItemBuilder::new("Reload Aurora")
                .id("reload_aurora")
                .accelerator("CmdOrCtrl+R")
                .build(app)?;
            let quit_item = MenuItemBuilder::new("Quit ONEXUS")
                .id("quit")
                .accelerator("CmdOrCtrl+Q")
                .build(app)?;

            let file_menu = SubmenuBuilder::new(app, "File")
                .item(&reload_backend_item)
                .separator()
                .item(&quit_item)
                .build()?;
            let view_menu = SubmenuBuilder::new(app, "View")
                .item(&reload_aurora_item)
                .build()?;
            let menu = MenuBuilder::new(app)
                .item(&file_menu)
                .item(&view_menu)
                .build()?;
            app.set_menu(menu)?;

            app.on_menu_event(move |_app, event| match event.id().as_ref() {
                "reload_backend" => reload_backend(&handle),
                "reload_aurora" => reload_aurora(&handle),
                "quit" => handle.exit(0),
                _ => {}
            });

            // Auto-reload: watch the resolved project_root for code changes
            // and trigger the right reload kind (backend vs aurora).
            if let Some(root) = resolve_project_root() {
                let watcher_handle = app.handle().clone();
                start_watcher(watcher_handle, root);
            }

            // Navigate the main WebView to the resolved port. tauri.conf.json
            // can only encode a constant URL, but we may have picked any port
            // from PORT_CANDIDATES — override after the window is built.
            if let Some(window) = app.get_webview_window("main") {
                let port = current_port();
                let target = format!("http://{HOST}:{port}/aurora");
                if let Ok(url) = target.parse::<tauri::Url>() {
                    if let Err(e) = window.navigate(url) {
                        eprintln!("[onexus] failed to navigate WebView to {target}: {e}");
                    }
                }
            }

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error building ONEXUS tauri app");

    app.run(|app_handle, event| match event {
        RunEvent::ExitRequested { .. } | RunEvent::Exit => {
            if let Some(state) = app_handle.try_state::<ServerChild>() {
                if let Some(mut child) = state.take() {
                    let _ = child.kill();
                    let _ = child.wait();
                }
            }
        }
        RunEvent::WindowEvent {
            event: WindowEvent::CloseRequested { .. },
            ..
        } => {
            if let Some(state) = app_handle.try_state::<ServerChild>() {
                if let Some(mut child) = state.take() {
                    let _ = child.kill();
                    let _ = child.wait();
                }
            }
        }
        _ => {}
    });
}
