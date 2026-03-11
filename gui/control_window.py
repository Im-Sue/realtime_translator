"""
桌面主控制窗口
负责配置、设备选择、启动停止和日志查看
"""

import shutil
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import sounddevice as sd
import yaml


SURFACE = "#11151c"
PANEL = "#1a1f29"
CARD = "#222834"
TEXT = "#f4f7fb"
MUTED = "#96a0b5"
ACCENT = "#4fc3f7"
SUCCESS = "#57d18c"
WARN = "#ffb454"
DANGER = "#ff6b6b"


class ControlWindow:
    """Realtime Translator 桌面主控制面板"""

    def __init__(self, config_path: str, runtime_dir: Path, log_path: Path):
        self.runtime_dir = Path(runtime_dir)
        self.config_path = Path(config_path)
        self.log_path = Path(log_path)
        self.example_config_path = self.runtime_dir / "config.yaml.example"
        self.worker_process = None
        self.last_log_text = ""

        self.root = tk.Tk()
        self.root.title("Realtime Translator Control Center")
        self.root.geometry("1180x820")
        self.root.minsize(1080, 760)
        self.root.configure(bg=SURFACE)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self._init_style()
        self._ensure_config_file()
        self.config_data = self._load_config()
        self._init_vars()
        self._build_layout()
        self.refresh_devices()
        self.refresh_runtime_state()
        self.refresh_log_view()

        self.root.after(1200, self._tick_runtime)
        self.root.after(1500, self._tick_log)

    def _init_style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(
            "App.TCombobox",
            fieldbackground=CARD,
            background=CARD,
            foreground=TEXT,
            arrowcolor=ACCENT,
        )

    def _ensure_config_file(self):
        if self.config_path.exists():
            return
        if self.example_config_path.exists():
            self.config_path.write_text(
                self.example_config_path.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
        else:
            self.config_path.write_text("{}", encoding="utf-8")

    def _load_config(self):
        config = yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}
        config.setdefault("volcengine", {})
        config.setdefault("audio", {})
        config["audio"].setdefault("microphone", {})
        config["audio"].setdefault("system_audio", {})
        config["audio"].setdefault("vbcable_output", {})
        config.setdefault("channels", {})
        config["channels"].setdefault("zh_to_en", {})
        config["channels"].setdefault("en_to_zh", {})
        config.setdefault("subtitle_window", {})
        return config

    def _init_vars(self):
        volc = self.config_data["volcengine"]
        audio = self.config_data["audio"]
        channels = self.config_data["channels"]
        subtitle = self.config_data["subtitle_window"]

        self.vars = {
            "app_key": tk.StringVar(value=volc.get("app_key", "")),
            "access_key": tk.StringVar(value=volc.get("access_key", "")),
            "resource_id": tk.StringVar(value=volc.get("resource_id", "volc.service_type.10053")),
            "ws_url": tk.StringVar(value=volc.get("ws_url", "wss://openspeech.bytedance.com/api/v4/ast/v2/translate")),
            "mic_device": tk.StringVar(value=audio["microphone"].get("device", "")),
            "system_device": tk.StringVar(value=audio["system_audio"].get("device", "")),
            "fallback_device": tk.StringVar(value=audio["system_audio"].get("fallback_device", "")),
            "vbcable_device": tk.StringVar(value=audio["vbcable_output"].get("device", "")),
            "subtitle_position": tk.StringVar(value=subtitle.get("position", "top_right")),
            "subtitle_font_size": tk.StringVar(value=str(subtitle.get("font_size", 14))),
            "channel1_enabled": tk.BooleanVar(value=channels["zh_to_en"].get("enabled", True)),
            "channel2_enabled": tk.BooleanVar(value=channels["en_to_zh"].get("enabled", True)),
            "ffmpeg_status": tk.StringVar(value="检测中"),
            "worker_status": tk.StringVar(value="未启动"),
            "config_status": tk.StringVar(value=str(self.config_path)),
        }

    def _build_layout(self):
        container = tk.Frame(self.root, bg=SURFACE)
        container.pack(fill="both", expand=True, padx=20, pady=20)

        self._build_header(container)

        body = tk.Frame(container, bg=SURFACE)
        body.pack(fill="both", expand=True, pady=(18, 0))
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=2)
        body.grid_rowconfigure(0, weight=1)

        left = tk.Frame(body, bg=SURFACE)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 14))

        right = tk.Frame(body, bg=SURFACE)
        right.grid(row=0, column=1, sticky="nsew")

        self._build_config_cards(left)
        self._build_runtime_panel(right)

    def _build_header(self, parent):
        header = tk.Frame(parent, bg=PANEL, highlightbackground="#2c3443", highlightthickness=1)
        header.pack(fill="x")

        title_wrap = tk.Frame(header, bg=PANEL)
        title_wrap.pack(side="left", fill="both", expand=True, padx=18, pady=16)

        tk.Label(
            title_wrap,
            text="Realtime Translator Control Center",
            bg=PANEL,
            fg=TEXT,
            font=("Segoe UI Semibold", 20),
        ).pack(anchor="w")
        tk.Label(
            title_wrap,
            text="会议同传控制台：配置、设备、运行状态与日志集中管理",
            bg=PANEL,
            fg=MUTED,
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(4, 0))

        status_wrap = tk.Frame(header, bg=PANEL)
        status_wrap.pack(side="right", padx=18, pady=16)

        self.worker_badge = tk.Label(
            status_wrap,
            textvariable=self.vars["worker_status"],
            bg=CARD,
            fg=TEXT,
            padx=12,
            pady=8,
            font=("Segoe UI Semibold", 10),
        )
        self.worker_badge.pack(anchor="e")

    def _build_config_cards(self, parent):
        self._card(parent, "服务配置", self._build_service_card).pack(fill="x")
        self._card(parent, "通道与设备", self._build_audio_card).pack(fill="x", pady=(14, 0))
        self._card(parent, "字幕与运行", self._build_subtitle_card).pack(fill="x", pady=(14, 0))

    def _build_runtime_panel(self, parent):
        self._card(parent, "运行状态", self._build_status_card).pack(fill="x")
        self._card(parent, "运行日志", self._build_log_card).pack(fill="both", expand=True, pady=(14, 0))

    def _card(self, parent, title, builder):
        frame = tk.Frame(parent, bg=PANEL, highlightbackground="#2c3443", highlightthickness=1)
        tk.Label(
            frame,
            text=title,
            bg=PANEL,
            fg=TEXT,
            font=("Segoe UI Semibold", 13),
        ).pack(anchor="w", padx=16, pady=(14, 10))

        content = tk.Frame(frame, bg=PANEL)
        content.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        builder(content)
        return frame

    def _build_service_card(self, parent):
        self._field(parent, "App Key", self.vars["app_key"])
        self._field(parent, "Access Key", self.vars["access_key"], show="*")
        self._field(parent, "Resource ID", self.vars["resource_id"])
        self._field(parent, "WS URL", self.vars["ws_url"])

        button_row = tk.Frame(parent, bg=PANEL)
        button_row.pack(fill="x", pady=(10, 0))
        self._action_button(button_row, "保存配置", self.save_config, ACCENT).pack(side="left")
        self._action_button(button_row, "重新加载", self.reload_config, "#5468ff").pack(side="left", padx=(10, 0))

    def _build_audio_card(self, parent):
        toggle_row = tk.Frame(parent, bg=PANEL)
        toggle_row.pack(fill="x", pady=(0, 10))

        self._toggle(toggle_row, "启用 Channel 1 语音输出", self.vars["channel1_enabled"]).pack(side="left")
        self._toggle(toggle_row, "启用 Channel 2 字幕翻译", self.vars["channel2_enabled"]).pack(side="left", padx=(18, 0))

        self.mic_combo = self._combo_field(parent, "麦克风设备", self.vars["mic_device"])
        self.system_combo = self._combo_field(parent, "系统音频设备", self.vars["system_device"])
        self.fallback_combo = self._combo_field(parent, "系统音频回退设备", self.vars["fallback_device"])
        self.vbcable_combo = self._combo_field(parent, "Channel 1 输出设备", self.vars["vbcable_device"])

        button_row = tk.Frame(parent, bg=PANEL)
        button_row.pack(fill="x", pady=(10, 0))
        self._action_button(button_row, "刷新设备", self.refresh_devices, "#14b8a6").pack(side="left")

    def _build_subtitle_card(self, parent):
        self._combo_field(
            parent,
            "字幕窗口位置",
            self.vars["subtitle_position"],
            values=["top_right", "top_left", "top_center", "bottom_center"],
        )
        self._field(parent, "字幕字体大小", self.vars["subtitle_font_size"])

        button_row = tk.Frame(parent, bg=PANEL)
        button_row.pack(fill="x", pady=(10, 0))
        self._action_button(button_row, "启动翻译器", self.start_worker, SUCCESS).pack(side="left")
        self._action_button(button_row, "停止翻译器", self.stop_worker, DANGER).pack(side="left", padx=(10, 0))

    def _build_status_card(self, parent):
        self.ffmpeg_value = self._status_line(parent, "FFmpeg", self.vars["ffmpeg_status"])
        self.config_value = self._status_line(parent, "配置文件", self.vars["config_status"])
        self.runtime_value = self._status_line(parent, "Worker 状态", self.vars["worker_status"])

    def _build_log_card(self, parent):
        self.log_text = tk.Text(
            parent,
            bg="#0d1016",
            fg="#d5d9e2",
            insertbackground=TEXT,
            relief=tk.FLAT,
            height=20,
            font=("Consolas", 10),
            wrap=tk.WORD,
            padx=10,
            pady=10,
        )
        self.log_text.pack(fill="both", expand=True)
        self.log_text.configure(state=tk.DISABLED)

    def _field(self, parent, label, variable, show=None):
        wrap = tk.Frame(parent, bg=PANEL)
        wrap.pack(fill="x", pady=6)

        tk.Label(wrap, text=label, bg=PANEL, fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w")
        entry = tk.Entry(
            wrap,
            textvariable=variable,
            bg=CARD,
            fg=TEXT,
            insertbackground=TEXT,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground="#30384a",
            highlightcolor=ACCENT,
            font=("Segoe UI", 11),
            show=show,
        )
        entry.pack(fill="x", pady=(5, 0), ipady=8)
        return entry

    def _combo_field(self, parent, label, variable, values=None):
        wrap = tk.Frame(parent, bg=PANEL)
        wrap.pack(fill="x", pady=6)

        tk.Label(wrap, text=label, bg=PANEL, fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w")
        combo = ttk.Combobox(
            wrap,
            textvariable=variable,
            values=values or [],
            style="App.TCombobox",
            state="readonly" if values else "normal",
            font=("Segoe UI", 10),
        )
        combo.pack(fill="x", pady=(5, 0), ipady=4)
        return combo

    def _toggle(self, parent, text, variable):
        return tk.Checkbutton(
            parent,
            text=text,
            variable=variable,
            bg=PANEL,
            fg=TEXT,
            selectcolor=CARD,
            activebackground=PANEL,
            activeforeground=TEXT,
            font=("Segoe UI", 10),
            highlightthickness=0,
        )

    def _action_button(self, parent, text, command, bg):
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg="#081018",
            activebackground=bg,
            activeforeground="#081018",
            relief=tk.FLAT,
            padx=14,
            pady=10,
            font=("Segoe UI Semibold", 10),
            cursor="hand2",
        )

    def _status_line(self, parent, label, variable):
        wrap = tk.Frame(parent, bg=PANEL)
        wrap.pack(fill="x", pady=5)
        tk.Label(wrap, text=label, bg=PANEL, fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w")
        value = tk.Label(wrap, textvariable=variable, bg=CARD, fg=TEXT, padx=10, pady=8, anchor="w", font=("Segoe UI", 10))
        value.pack(fill="x", pady=(4, 0))
        return value

    def refresh_devices(self):
        try:
            devices = sd.query_devices()
        except Exception as exc:
            messagebox.showerror("设备刷新失败", str(exc))
            return

        input_devices = [d["name"] for d in devices if d["max_input_channels"] > 0]
        output_devices = [d["name"] for d in devices if d["max_output_channels"] > 0]

        self.mic_combo.configure(values=input_devices)
        self.system_combo.configure(values=input_devices)
        self.fallback_combo.configure(values=input_devices)
        self.vbcable_combo.configure(values=output_devices)

    def _collect_config(self):
        try:
            font_size = int(self.vars["subtitle_font_size"].get().strip())
        except ValueError:
            raise ValueError("字幕字体大小必须是整数")

        config = {
            "volcengine": {
                "ws_url": self.vars["ws_url"].get().strip(),
                "app_key": self.vars["app_key"].get().strip(),
                "access_key": self.vars["access_key"].get().strip(),
                "resource_id": self.vars["resource_id"].get().strip(),
            },
            "audio": {
                "microphone": {
                    "device": self.vars["mic_device"].get().strip(),
                    "sample_rate": 16000,
                    "channels": 1,
                    "chunk_size": 1600,
                },
                "system_audio": {
                    "device": self.vars["system_device"].get().strip(),
                    "fallback_device": self.vars["fallback_device"].get().strip(),
                    "sample_rate": 16000,
                    "channels": 1,
                    "chunk_size": 1600,
                },
                "vbcable_output": {
                    "device": self.vars["vbcable_device"].get().strip(),
                    "sample_rate": 24000,
                    "use_ffmpeg": True,
                    "monitor_device": None,
                    "enable_monitor": False,
                },
            },
            "channels": {
                "zh_to_en": {
                    "mode": "s2s",
                    "source_language": "zh",
                    "target_language": "en",
                    "enabled": self.vars["channel1_enabled"].get(),
                },
                "en_to_zh": {
                    "mode": "s2t",
                    "source_language": "en",
                    "target_language": "zh",
                    "enabled": self.vars["channel2_enabled"].get(),
                },
            },
            "subtitle_window": {
                "enabled": True,
                "width": 600,
                "height": 800,
                "font_size": font_size,
                "bg_color": "#000000",
                "text_color": "#FFFFFF",
                "opacity": 0.85,
                "position": self.vars["subtitle_position"].get().strip(),
                "max_history": 1000,
                "show_timestamp": False,
            },
        }
        return config

    def save_config(self):
        try:
            config = self._collect_config()
        except Exception as exc:
            messagebox.showerror("保存失败", str(exc))
            return False

        self.config_path.write_text(
            yaml.safe_dump(config, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        self.config_data = config
        self.vars["config_status"].set(str(self.config_path))
        return True

    def reload_config(self):
        self.config_data = self._load_config()
        self._init_vars()
        self.root.destroy()
        launch_control_window(str(self.config_path), self.runtime_dir, self.log_path)

    def _resolve_ffmpeg(self):
        local_name = "ffmpeg.exe" if sys.platform.startswith("win") else "ffmpeg"
        local_ffmpeg = self.runtime_dir / local_name
        if local_ffmpeg.exists():
            return str(local_ffmpeg)
        ffmpeg = shutil.which("ffmpeg")
        return ffmpeg or ""

    def _worker_command(self):
        if getattr(sys, "frozen", False):
            return [sys.executable, "--worker", str(self.config_path)]
        return [sys.executable, str(self.runtime_dir / "main.py"), "--worker", str(self.config_path)]

    def start_worker(self):
        if self.worker_process and self.worker_process.poll() is None:
            messagebox.showinfo("提示", "翻译器已经在运行")
            return

        if not self.save_config():
            return

        kwargs = {
            "cwd": str(self.runtime_dir),
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }
        if sys.platform.startswith("win"):
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

        try:
            self.worker_process = subprocess.Popen(self._worker_command(), **kwargs)
        except Exception as exc:
            messagebox.showerror("启动失败", str(exc))
            return

        self.refresh_runtime_state()

    def stop_worker(self):
        if not self.worker_process or self.worker_process.poll() is not None:
            self.worker_process = None
            self.refresh_runtime_state()
            return

        self.worker_process.terminate()
        try:
            self.worker_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.worker_process.kill()
            self.worker_process.wait(timeout=5)

        self.worker_process = None
        self.refresh_runtime_state()

    def refresh_runtime_state(self):
        ffmpeg_path = self._resolve_ffmpeg()
        self.vars["ffmpeg_status"].set(ffmpeg_path if ffmpeg_path else "未检测到")

        if self.worker_process and self.worker_process.poll() is None:
            self.vars["worker_status"].set("运行中")
            self.worker_badge.configure(bg=SUCCESS, fg="#081018")
        else:
            self.vars["worker_status"].set("未启动")
            self.worker_badge.configure(bg=CARD, fg=TEXT)

    def refresh_log_view(self):
        if not self.log_path.exists():
            log_text = "日志文件尚未生成。启动翻译器后，这里会显示运行日志。"
        else:
            content = self.log_path.read_text(encoding="utf-8", errors="ignore")
            log_text = "\n".join(content.splitlines()[-160:]) or "日志为空"

        if log_text == self.last_log_text:
            return

        self.last_log_text = log_text
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.insert("1.0", log_text)
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _tick_runtime(self):
        self.refresh_runtime_state()
        self.root.after(1200, self._tick_runtime)

    def _tick_log(self):
        self.refresh_log_view()
        self.root.after(1500, self._tick_log)

    def on_close(self):
        if self.worker_process and self.worker_process.poll() is None:
            if not messagebox.askyesno("退出", "翻译器仍在运行，是否停止后退出？"):
                return
            self.stop_worker()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def launch_control_window(config_path: str, runtime_dir: Path, log_path: Path):
    window = ControlWindow(config_path=config_path, runtime_dir=runtime_dir, log_path=log_path)
    window.run()
