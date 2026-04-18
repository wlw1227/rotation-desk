use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::Mutex;
use tauri::{
    image::Image,
    menu::{Menu, MenuItemBuilder, PredefinedMenuItem},
    tray::{TrayIconBuilder, TrayIconEvent},
    App, AppHandle, Emitter, Manager,
};
use tauri_plugin_notification::NotificationExt;
use tauri_plugin_shell::process::CommandChild;
use tauri_plugin_shell::ShellExt;
use tokio::time::{sleep, Duration};

// ── Constants ──────────────────────────────────────────────────────────────

const SERVER_PORT: u16 = 8000;

// ── Types ──────────────────────────────────────────────────────────────────

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct Credentials {
    pub anthropic_api_key: String,
    pub telegram_api_id: String,
    pub telegram_api_hash: String,
    pub telegram_phone: String,
}

pub struct AppState {
    pub sidecar_child: Mutex<Option<CommandChild>>,
    pub server_port: u16,
}

// ── .env file helpers ──────────────────────────────────────────────────────

/// Parse a simple KEY=VALUE dotenv file into a HashMap.
fn read_dotenv_file(path: &std::path::Path) -> HashMap<String, String> {
    let mut map = HashMap::new();
    if let Ok(content) = std::fs::read_to_string(path) {
        for line in content.lines() {
            let line = line.trim();
            if line.is_empty() || line.starts_with('#') {
                continue;
            }
            if let Some((key, val)) = line.split_once('=') {
                let val = val.trim().trim_matches('"').trim_matches('\'');
                map.insert(key.trim().to_string(), val.to_string());
            }
        }
    }
    map
}

/// Write credentials to a .env file in data_dir.
fn write_dotenv_file(path: &std::path::Path, creds: &Credentials) -> Result<(), String> {
    let content = format!(
        "ANTHROPIC_API_KEY={}\nTELEGRAM_API_ID={}\nTELEGRAM_API_HASH={}\nTELEGRAM_PHONE={}\n",
        creds.anthropic_api_key,
        creds.telegram_api_id,
        creds.telegram_api_hash,
        creds.telegram_phone,
    );
    std::fs::write(path, content).map_err(|e| format!("Failed to write .env: {e}"))
}

fn dotenv_has_api_key(data_dir: &std::path::Path) -> bool {
    let vars = read_dotenv_file(&data_dir.join(".env"));
    vars.get("ANTHROPIC_API_KEY")
        .map(|v| !v.trim().is_empty())
        .unwrap_or(false)
}

// ── IPC Commands ───────────────────────────────────────────────────────────

/// Called by settings.html to save credentials as a .env file and start the sidecar.
#[tauri::command]
fn save_credentials_cmd(
    anthropic_api_key: String,
    telegram_api_id: String,
    telegram_api_hash: String,
    telegram_phone: String,
    app: AppHandle,
) -> Result<(), String> {
    let creds = Credentials {
        anthropic_api_key,
        telegram_api_id,
        telegram_api_hash,
        telegram_phone,
    };
    let data_dir = get_data_dir(&app);
    std::fs::create_dir_all(&data_dir).map_err(|e| e.to_string())?;
    write_dotenv_file(&data_dir.join(".env"), &creds)?;

    tauri::async_runtime::spawn(async move {
        start_sidecar(app, data_dir).await;
    });
    Ok(())
}

/// Called by settings.html on load to pre-fill existing credential values.
#[tauri::command]
fn get_credentials_cmd(app: AppHandle) -> Result<Option<Credentials>, String> {
    let data_dir = get_data_dir(&app);
    let vars = read_dotenv_file(&data_dir.join(".env"));
    if vars.get("ANTHROPIC_API_KEY").map(|v| !v.is_empty()).unwrap_or(false) {
        Ok(Some(Credentials {
            anthropic_api_key: vars.get("ANTHROPIC_API_KEY").cloned().unwrap_or_default(),
            telegram_api_id: vars.get("TELEGRAM_API_ID").cloned().unwrap_or_default(),
            telegram_api_hash: vars.get("TELEGRAM_API_HASH").cloned().unwrap_or_default(),
            telegram_phone: vars.get("TELEGRAM_PHONE").cloned().unwrap_or_default(),
        }))
    } else {
        Ok(None)
    }
}

/// Called by index.html when pipeline status changes — syncs the tray icon.
#[tauri::command]
fn update_tray_status(status: String, app: AppHandle) {
    let icon_name = match status.as_str() {
        "collecting" | "synthesizing" => "tray-collecting.png",
        "ready" => "tray-ready.png",
        "error" => "tray-error.png",
        _ => "tray-ready.png",
    };

    if let Some(tray) = app.tray_by_id("main-tray") {
        let resource_dir = match app.path().resource_dir() {
            Ok(d) => d,
            Err(_) => return,
        };
        let icon_path = resource_dir.join("icons").join(icon_name);
        if let Ok(img) = Image::from_path(&icon_path) {
            let _ = tray.set_icon(Some(img));
        }
    }
}

/// Called by index.html when an EARLY HOT rotation signal is detected.
#[tauri::command]
fn show_notification(title: String, body: String, app: AppHandle) -> Result<(), String> {
    app.notification()
        .builder()
        .title(&title)
        .body(&body)
        .show()
        .map_err(|e| e.to_string())
}

// ── Sidecar management ─────────────────────────────────────────────────────

fn get_data_dir(app: &AppHandle) -> PathBuf {
    app.path()
        .app_data_dir()
        .expect("Could not resolve appDataDir")
}

fn show_settings_window(app: &AppHandle) {
    if let Some(win) = app.get_webview_window("settings") {
        let _ = win.show();
        let _ = win.set_focus();
    }
}

/// Reads credentials from $appDataDir/.env, injects them as env vars,
/// spawns the Python sidecar, polls until ready, then shows the main window.
async fn start_sidecar(app: AppHandle, data_dir: PathBuf) {
    // Read credentials from .env file
    let env_vars = read_dotenv_file(&data_dir.join(".env"));

    // Spawn sidecar with env vars injected directly
    let state = app.state::<AppState>();
    let port = state.server_port;

    let sidecar_result = app
        .shell()
        .sidecar("rotation-intel-server")
        .expect("sidecar 'rotation-intel-server' not found — run build.sh first")
        .args([
            "--data-dir",
            data_dir.to_str().unwrap_or(""),
            "--port",
            &port.to_string(),
        ])
        .envs(env_vars)
        .spawn();

    let (mut rx, child) = match sidecar_result {
        Ok(pair) => pair,
        Err(e) => {
            eprintln!("[tauri] Failed to spawn sidecar: {e}");
            update_tray_status("error".to_string(), app);
            return;
        }
    };

    // Store child handle so we can kill it on Quit
    {
        let mut guard = state.sidecar_child.lock().unwrap();
        *guard = Some(child);
    }

    // Background task: log sidecar stdout/stderr
    tauri::async_runtime::spawn(async move {
        use tauri_plugin_shell::process::CommandEvent;
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(line) => {
                    eprintln!("[sidecar] {}", String::from_utf8_lossy(&line));
                }
                CommandEvent::Stderr(line) => {
                    eprintln!("[sidecar-err] {}", String::from_utf8_lossy(&line));
                }
                CommandEvent::Terminated(status) => {
                    eprintln!("[sidecar] terminated: {:?}", status);
                    break;
                }
                _ => {}
            }
        }
    });

    // Poll /api/state until server responds (max 30s)
    let client = reqwest::Client::new();
    let health_url = format!("http://localhost:{port}/api/state");
    let mut ready = false;
    for _ in 0..60 {
        sleep(Duration::from_millis(500)).await;
        if client.get(&health_url).send().await.is_ok() {
            ready = true;
            break;
        }
    }

    if ready {
        if let Some(window) = app.get_webview_window("main") {
            let _ = window.show();
            let _ = window.set_focus();
        }
        update_tray_status("ready".to_string(), app);
    } else {
        eprintln!("[tauri] Server did not become ready within 30 seconds");
        update_tray_status("error".to_string(), app);
    }
}

// ── System tray ────────────────────────────────────────────────────────────

fn build_tray(app: &App) -> tauri::Result<()> {
    let show_item = MenuItemBuilder::with_id("show", "Show Dashboard").build(app)?;
    let run_item = MenuItemBuilder::with_id("run_now", "Run Now").build(app)?;
    let settings_item = MenuItemBuilder::with_id("settings", "Settings…").build(app)?;
    let sep = PredefinedMenuItem::separator(app)?;
    let quit_item = MenuItemBuilder::with_id("quit", "Quit RotationDesk").build(app)?;

    let menu = Menu::with_items(app, &[&show_item, &run_item, &settings_item, &sep, &quit_item])?;

    TrayIconBuilder::with_id("main-tray")
        .menu(&menu)
        .tooltip("RotationDesk")
        .on_menu_event(|app, event| match event.id.as_ref() {
            "show" => {
                if let Some(win) = app.get_webview_window("main") {
                    let _ = win.show();
                    let _ = win.unminimize();
                    let _ = win.set_focus();
                }
            }
            "run_now" => {
                if let Some(win) = app.get_webview_window("main") {
                    let _ = win.emit("run-now", ());
                }
            }
            "settings" => {
                show_settings_window(app);
            }
            "quit" => {
                let state = app.state::<AppState>();
                if let Ok(mut guard) = state.sidecar_child.lock() {
                    if let Some(child) = guard.take() {
                        let _ = child.kill();
                    }
                }
                app.exit(0);
            }
            _ => {}
        })
        .on_tray_icon_event(|tray, event| {
            if let TrayIconEvent::DoubleClick { .. } = event {
                let app = tray.app_handle();
                if let Some(win) = app.get_webview_window("main") {
                    let _ = win.show();
                    let _ = win.unminimize();
                    let _ = win.set_focus();
                }
            }
        })
        .build(app)?;

    Ok(())
}

// ── App entry point ────────────────────────────────────────────────────────

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_single_instance::init(|app, _argv, _cwd| {
            if let Some(win) = app.get_webview_window("main") {
                let _ = win.show();
                let _ = win.unminimize();
                let _ = win.set_focus();
            }
        }))
        .plugin(tauri_plugin_autostart::init(
            tauri_plugin_autostart::MacosLauncher::LaunchAgent,
            Some(vec![]),
        ))
        .manage(AppState {
            sidecar_child: Mutex::new(None),
            server_port: SERVER_PORT,
        })
        .invoke_handler(tauri::generate_handler![
            save_credentials_cmd,
            get_credentials_cmd,
            update_tray_status,
            show_notification,
        ])
        .setup(|app| {
            #[cfg(target_os = "macos")]
            app.set_activation_policy(tauri::ActivationPolicy::Accessory);

            build_tray(app)?;

            let app_handle = app.handle().clone();
            let data_dir = get_data_dir(&app_handle);

            if dotenv_has_api_key(&data_dir) {
                tauri::async_runtime::spawn(async move {
                    start_sidecar(app_handle, data_dir).await;
                });
            } else {
                show_settings_window(&app_handle);
            }

            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                if window.label() == "main" {
                    api.prevent_close();
                    let _ = window.hide();
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running RotationDesk");
}
