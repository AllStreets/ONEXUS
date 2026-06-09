// ONEXUS standalone — Tauri shell library.
//
// Boots the FastAPI server, waits for /api/health, opens the WebView, and
// tears down the child process when the shell window closes.

use std::io::{BufRead, BufReader};
use std::net::TcpStream;
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::thread;
use std::time::{Duration, Instant};

use tauri::{Manager, RunEvent, WindowEvent};

const HOST: &str = "127.0.0.1";
const PORT: u16 = 8000;
const HEALTH_TIMEOUT_SECS: u64 = 20;

/// Wrapper around the spawned Python child so we can kill it on shutdown.
struct ServerChild(Mutex<Option<Child>>);

impl ServerChild {
    fn take(&self) -> Option<Child> {
        self.0.lock().ok().and_then(|mut g| g.take())
    }
}

/// Resolve where ONEXUS lives on disk so we can `cd` there and run the server.
/// We look for a `nexus/__init__.py` walking up from the executable, falling
/// back to the current working directory for `cargo tauri dev`.
fn resolve_project_root() -> Option<PathBuf> {
    let exe = std::env::current_exe().ok()?;
    let mut cursor = exe.parent().map(PathBuf::from)?;

    for _ in 0..8 {
        if cursor.join("nexus").join("__init__.py").exists() {
            return Some(cursor);
        }
        if !cursor.pop() {
            break;
        }
    }

    let cwd = std::env::current_dir().ok()?;
    if cwd.join("nexus").join("__init__.py").exists() {
        return Some(cwd);
    }
    // dev runs from standalone/ — walk up one
    if let Some(parent) = cwd.parent() {
        if parent.join("nexus").join("__init__.py").exists() {
            return Some(parent.to_path_buf());
        }
    }
    None
}

/// Spawn `python -m nexus.api.server` and return the child. Stdout / stderr
/// are inherited so logs surface in `cargo tauri dev` and can be redirected
/// in production launches.
fn spawn_python_server() -> Result<Child, String> {
    let root = resolve_project_root()
        .ok_or_else(|| "could not locate ONEXUS project root (no nexus/__init__.py found)".to_string())?;

    // Prefer the project-local virtualenv if it exists (production-typical),
    // otherwise look for `onexus` on PATH (pipx / pip install --user),
    // and as a final fallback shell out to python3 -m nexus.cli serve.
    let mut command = if root.join(".venv/bin/onexus").exists() {
        let mut c = Command::new(root.join(".venv/bin/onexus"));
        c.arg("serve").arg("--port").arg(PORT.to_string());
        c
    } else if which::which("onexus").is_ok() {
        let mut c = Command::new("onexus");
        c.arg("serve").arg("--port").arg(PORT.to_string());
        c
    } else {
        let python = ["python3.14", "python3.13", "python3.12", "python3.11", "python3", "python"]
            .iter()
            .find(|name| which::which(name).is_ok())
            .ok_or_else(|| "no python3 found on PATH and no .venv/bin/onexus".to_string())?;
        let mut c = Command::new(python);
        c.arg("-m").arg("nexus.cli").arg("serve").arg("--port").arg(PORT.to_string());
        c
    };

    let mut child = command
        .current_dir(&root)
        .env("ONEXUS_STANDALONE", "1")
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("failed to spawn ONEXUS server: {e}"))?;

    // Mirror child stdout/stderr to ours so logs are visible.
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

/// Poll the API server's TCP port until it accepts a connection or the
/// timeout elapses. Cheap and dependency-free — we don't need an HTTP probe
/// because the kernel doesn't bind until it's ready to serve.
fn wait_for_server() -> Result<(), String> {
    let deadline = Instant::now() + Duration::from_secs(HEALTH_TIMEOUT_SECS);
    let addr = format!("{HOST}:{PORT}");
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

pub fn run() {
    // If something is already listening on 8000 (user ran `python -m nexus.api.server`
    // themselves) we don't double-launch it — just attach.
    let already_up = TcpStream::connect_timeout(
        &format!("{HOST}:{PORT}").parse().unwrap(),
        Duration::from_millis(200),
    )
    .is_ok();

    let server: Option<Child> = if already_up {
        eprintln!("[onexus] server already listening on {HOST}:{PORT}, attaching");
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
        .setup(|_app| Ok(()))
        .build(tauri::generate_context!())
        .expect("error building ONEXUS tauri app");

    app.run(|app_handle, event| match event {
        RunEvent::ExitRequested { .. } | RunEvent::Exit => {
            // Tear the server down on quit.
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
            // Closing the main window also exits — kill the server too.
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
