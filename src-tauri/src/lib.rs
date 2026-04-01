//! 实时同传桌面应用 — Tauri 后端
//!
//! 负责：
//! 1. 拉起 Python sidecar (rt-engine.exe / python)
//! 2. 读取 stdout 获取 WS port
//! 3. 通过 event 通知前端连接 WS
//! 4. 管理 Python 进程生命周期

use serde::Serialize;
use std::io::BufRead;
use std::process::{Command, Stdio};
use std::sync::Mutex;
use tauri::{AppHandle, Emitter, LogicalSize, Manager, Size, State, WebviewUrl, WebviewWindowBuilder};

/// Python sidecar 就绪后发给前端的事件
#[derive(Clone, Serialize)]
struct SidecarReady {
    port: u16,
}

/// 管理 Python 子进程
struct SidecarState {
    child: Mutex<Option<std::process::Child>>,
    port: Mutex<u16>,
}

/// 切换字幕窗口显示/隐藏，返回当前可见状态
#[tauri::command]
fn toggle_subtitle(app: AppHandle, state: State<SidecarState>) -> Result<bool, String> {
    let win = app
        .get_webview_window("subtitle-overlay")
        .ok_or("subtitle-overlay 窗口不存在")?;
    let visible = win.is_visible().unwrap_or(false);
    if visible {
        win.hide().map_err(|e| e.to_string())?;
        eprintln!("[subtitle] 字幕窗口已隐藏");
        Ok(false)
    } else {
        // 显示前确保 navigate 到正确的端口 URL
        let port = *state.port.lock().map_err(|e| e.to_string())?;
        if port > 0 {
            let url = format!("http://tauri.localhost/subtitle?port={}", port);
            if let Ok(parsed) = url.parse() {
                let _ = win.navigate(parsed);
            }
        }
        let _ = win.set_decorations(false);
        let _ = win.set_shadow(false);
        let _ = win.set_resizable(true);
        let _ = win.set_size(Size::Logical(LogicalSize::new(1000.0, 300.0)));
        win.show().map_err(|e| e.to_string())?;
        eprintln!("[subtitle] 字幕窗口已显示, port={}", port);
        Ok(true)
    }
}

/// 启动 Python sidecar，返回 WS 端口
#[tauri::command]
fn launch_sidecar(app: AppHandle, state: State<SidecarState>) -> Result<u16, String> {
    let mut guard = state.child.lock().map_err(|e| e.to_string())?;

    // 已经在运行
    if let Some(ref mut child) = *guard {
        if child.try_wait().ok().flatten().is_none() {
            return Err("sidecar 已在运行".into());
        }
    }

    // 获取 Tauri PID
    let tauri_pid = std::process::id();

    // 查找 Python sidecar：多策略，优先级从高到低
    // 1. Tauri resource_dir（标准位置）
    // 2. exe 同级目录（NSIS 安装后资源在 exe 旁边）
    // 3. 开发模式（系统 python）
    let (program, script, deps_path, work_dir);

    let resource_dir = app
        .path()
        .resource_dir()
        .ok()
        .map(|p| strip_verbatim_prefix(&p));

    // 获取 exe 所在目录（NSIS 安装时资源就在 exe 旁边）
    let exe_dir = std::env::current_exe()
        .ok()
        .map(|p| strip_verbatim_prefix(&p))
        .and_then(|p| p.parent().map(|d| d.to_path_buf()));

    // 在候选目录中查找 python/rt-engine.exe
    let bundle_dir = [resource_dir.as_ref(), exe_dir.as_ref()]
        .into_iter()
        .flatten()
        .find(|dir| dir.join("python").join("rt-engine.exe").exists());

    if let Some(base) = bundle_dir {
        // 生产模式: 找到了 bundle 内的 Python
        eprintln!("[sidecar] 生产模式: base={}", base.display());
        program = base.join("python").join("rt-engine.exe");
        // 源码在 backend/realtime_translator/ 下，保持包结构
        // sidecar.py 用 dirname(dirname(__file__)) 推算 PROJECT_ROOT
        // → backend/realtime_translator/ → 能找到 core/、pb2/ 等
        script = base.join("backend").join("realtime_translator").join("desktop_backend").join("sidecar.py");
        deps_path = Some(base.join("deps"));
        work_dir = Some(base.join("backend").join("realtime_translator"));
    } else {
        // 开发模式: 使用系统 python，直接从项目根运行
        eprintln!("[sidecar] 开发模式: resource_dir={:?}, exe_dir={:?}",
            resource_dir.as_ref().map(|p| p.display().to_string()),
            exe_dir.as_ref().map(|p| p.display().to_string()),
        );
        program = which_python();
        let project_root = std::env::current_dir().unwrap_or_default();
        script = project_root.join("desktop_backend").join("sidecar.py");
        deps_path = None;
        work_dir = None;
    }

    let mut cmd = Command::new(&program);
    cmd.arg(&script)
        .arg("--parent-pid")
        .arg(tauri_pid.to_string())
        .stdout(Stdio::piped())
        .stderr(Stdio::inherit());

    // 生产模式: 设置工作目录为 backend/
    if let Some(ref wd) = work_dir {
        cmd.current_dir(wd);
    }

    // 生产模式设置 PYTHONPATH
    if let Some(ref deps) = deps_path {
        // PYTHONPATH 需要包含:
        //   1. deps/ — pip 依赖
        //   2. backend/ — 包含 realtime_translator 包（from realtime_translator.pb2... 需要）
        //   3. backend/realtime_translator/ — 直接导入（from desktop_backend.services 等）
        let pkg_parent = work_dir.as_ref()
            .and_then(|p| p.parent())
            .map(|p| p.to_path_buf())
            .unwrap_or_default();
        let pkg_dir = work_dir.as_ref().cloned().unwrap_or_default();
        let pythonpath = format!("{};{};{}", deps.display(), pkg_parent.display(), pkg_dir.display());
        eprintln!("[sidecar] PYTHONPATH={}", pythonpath);
        cmd.env("PYTHONPATH", pythonpath);

        // 传递 AppData 路径，ConfigService 用于存储 config.yaml（升级不丢失）
        if let Ok(app_data) = app.path().app_data_dir() {
            let app_data = strip_verbatim_prefix(&app_data);
            eprintln!("[sidecar] RT_APP_DATA={}", app_data.display());
            cmd.env("RT_APP_DATA", app_data);
        }
    }

    eprintln!("[sidecar] program={} script={} work_dir={:?}",
        program.display(), script.display(),
        work_dir.as_ref().map(|p| p.display().to_string()));
    let mut child = cmd.spawn().map_err(|e| format!("启动 sidecar 失败: {} (program={}, script={})", e, program.display(), script.display()))?;

    // 读 stdout 第一行拿到 port
    let stdout = child.stdout.take().ok_or("无法读取 stdout")?;
    let reader = std::io::BufReader::new(stdout);
    let mut port: u16 = 0;

    for line in reader.lines() {
        let line = line.map_err(|e| format!("读取 stdout 失败: {}", e))?;
        if let Ok(json) = serde_json::from_str::<serde_json::Value>(&line) {
            if json.get("ready").and_then(|v| v.as_bool()) == Some(true) {
                port = json
                    .get("port")
                    .and_then(|v| v.as_u64())
                    .unwrap_or(0) as u16;
                break;
            }
        }
    }

    if port == 0 {
        let _ = child.kill();
        return Err("sidecar 未返回有效端口".into());
    }

    *guard = Some(child);

    // 保存端口供 toggle_subtitle 使用
    if let Ok(mut p) = state.port.lock() {
        *p = port;
    }

    // 通知前端
    let _ = app.emit("sidecar-ready", SidecarReady { port });

    // 预加载字幕浮窗（不显示，由前端按钮控制 show/hide）
    if let Some(subtitle_win) = app.get_webview_window("subtitle-overlay") {
        let url = format!("http://tauri.localhost/subtitle?port={}", port);
        if let Ok(parsed) = url.parse() {
            let _ = subtitle_win.navigate(parsed);
        }
        eprintln!("[sidecar] 字幕浮窗已预加载, port={}", port);
    } else {
        eprintln!("[sidecar] 未找到 subtitle-overlay 窗口");
    }

    Ok(port)
}

/// 去除 Windows `\\?\` (verbatim path) 前缀
/// Windows API 返回的路径可能带此前缀，但 Python 无法识别
fn strip_verbatim_prefix(path: &std::path::Path) -> std::path::PathBuf {
    let s = path.to_string_lossy();
    if s.starts_with(r"\\?\") {
        std::path::PathBuf::from(&s[4..])
    } else {
        path.to_path_buf()
    }
}

/// 在 PATH 中查找 python
fn which_python() -> std::path::PathBuf {
    #[cfg(target_os = "windows")]
    {
        std::path::PathBuf::from("python")
    }
    #[cfg(not(target_os = "windows"))]
    {
        std::path::PathBuf::from("python3")
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(SidecarState {
            child: Mutex::new(None),
            port: Mutex::new(0),
        })
        .invoke_handler(tauri::generate_handler![launch_sidecar, toggle_subtitle])
        .setup(|app| {
            // 确保 subtitle-overlay 窗口存在（config 可能偶发创建失败）
            if app.get_webview_window("subtitle-overlay").is_none() {
                eprintln!("[setup] subtitle-overlay 窗口未从 config 创建，动态补建...");
                let _ = WebviewWindowBuilder::new(
                    app,
                    "subtitle-overlay",
                    WebviewUrl::App("/subtitle".into()),
                )
                .title("")
                .decorations(false)
                .transparent(false)
                .shadow(false)
                .always_on_top(true)
                .skip_taskbar(true)
                .inner_size(1000.0, 300.0)
                .resizable(true)
                .visible(false)
                .position(460.0, 920.0)
                .build()
                .map_err(|e| eprintln!("[setup] 动态创建 subtitle-overlay 失败: {}", e));
            } else {
                eprintln!("[setup] subtitle-overlay 窗口已从 config 创建");
            }
            Ok(())
        })
        .on_window_event(|window, event| {
            // 主窗口关闭时退出应用
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                if window.label() == "main" {
                    let app = window.app_handle();
                    // 杀掉 sidecar
                    if let Some(state) = app.try_state::<SidecarState>() {
                        if let Ok(mut guard) = state.child.lock() {
                            if let Some(ref mut child) = *guard {
                                let _ = child.kill();
                            }
                        }
                    }
                    // 先显式销毁 subtitle-overlay 窗口，释放 WebView2 资源
                    if let Some(subtitle_win) = app.get_webview_window("subtitle-overlay") {
                        eprintln!("[exit] 销毁 subtitle-overlay 窗口...");
                        let _ = subtitle_win.destroy();
                    }
                    // 再正常退出
                    app.exit(0);
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
