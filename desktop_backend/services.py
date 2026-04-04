"""
桌面后端服务层

提供给 sidecar WebSocket 命令调用的业务逻辑。
"""

import asyncio
import os
import sys
import copy
import platform
import shutil
import yaml
from typing import Any

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ─── 默认配置模板 ────────────────────────────────────────────

DEFAULT_CONFIG = {
    "volcengine": {
        "ws_url": "wss://openspeech.bytedance.com/api/v4/ast/v2/translate",
        "app_key": "",
        "access_key": "",
        "resource_id": "volc.service_type.10053",
    },
    "audio": {
        "microphone": {
            "device": "",
            "sample_rate": 16000,
            "channels": 1,
            "chunk_size": 1600,
        },
        "system_audio": {
            "device": "",
            "fallback_device": "",
            "sample_rate": 16000,
            "channels": 1,
            "chunk_size": 1600,
        },
        "vbcable_output": {
            "device": "",
            "sample_rate": 48000,
            "target_format": "pcm",
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
            "enabled": True,
        },
        "en_to_zh": {
            "mode": "s2t",
            "source_language": "en",
            "target_language": "zh",
            "enabled": True,
        },
    },
    "subtitle_window": {
        "font_size": 16,
        "opacity": 0.85,
        "text_color": "#FFFFFF",
    },
}


def _deep_merge_config(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """深度合并配置，确保旧配置也能补齐新增字段。"""
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_config(merged[key], value)
        else:
            merged[key] = value
    return merged


def _resolve_config_dir() -> str:
    """
    确定配置文件存储目录。

    优先级：
    1. 环境变量 RT_APP_DATA（Tauri 生产模式注入）
    2. %APPDATA%/RealtimeTranslator（Windows 生产回退）
    3. PROJECT_ROOT（开发模式）
    """
    # Tauri 传入的 app data 目录
    app_data = os.environ.get("RT_APP_DATA")
    if app_data:
        return app_data

    # 检测是否为生产模式（从 rt-engine.exe 启动）
    exe_name = os.path.basename(sys.executable).lower()
    if exe_name.startswith("rt-engine"):
        # 生产模式：使用 %APPDATA%
        appdata = os.environ.get("APPDATA")
        if appdata:
            return os.path.join(appdata, "RealtimeTranslator")

    # 开发模式
    return PROJECT_ROOT


# ─── ConfigService ──────────────────────────────────────────

class ConfigService:
    """配置文件读写，支持首次启动无配置文件"""

    def __init__(self, config_path: str = None):
        if config_path is None:
            config_dir = _resolve_config_dir()
            config_path = os.path.join(config_dir, "config.yaml")
        self.config_path = config_path
        self._data: dict = {}

    def load(self) -> dict:
        """
        加载配置文件。

        若 config.yaml 不存在，返回内置默认模板（首次启动场景）。
        用户在 UI 保存后会创建实际文件。
        """
        if not os.path.exists(self.config_path):
            self._data = copy.deepcopy(DEFAULT_CONFIG)
            return self.get_safe_config()
        with open(self.config_path, 'r', encoding='utf-8') as f:
            loaded = yaml.safe_load(f) or {}
        self._data = _deep_merge_config(DEFAULT_CONFIG, loaded)
        return self.get_safe_config()

    def save(self, data: dict) -> dict:
        """保存配置到文件，自动创建目录。

        如果前端传回的密钥是脱敏值（含 ****），则保留原始密钥不覆盖。
        """
        # 合并脱敏字段：前端可能传回 ****，此时保留原始值
        volc_new = data.get("volcengine", {})
        volc_old = self._data.get("volcengine", {})
        for key in ("app_key", "access_key"):
            val = volc_new.get(key, "")
            if "****" in str(val):
                # 脱敏值 → 恢复原始密钥
                volc_new[key] = volc_old.get(key, "")

        # 统一按默认模板补齐缺失字段，避免旧配置保存后继续缺字段
        normalized = _deep_merge_config(DEFAULT_CONFIG, data)
        self._data = normalized
        config_dir = os.path.dirname(self.config_path)
        if config_dir and not os.path.exists(config_dir):
            os.makedirs(config_dir, exist_ok=True)
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(normalized, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        return {"saved": True}

    def get_safe_config(self) -> dict:
        """返回脱敏配置（隐藏密钥）"""
        safe = copy.deepcopy(self._data)
        volc = safe.get("volcengine", {})
        for key in ("app_key", "access_key"):
            val = volc.get(key, "")
            if val and len(val) > 8:
                volc[key] = val[:4] + "****" + val[-4:]
        return safe

    def get_raw_config(self) -> dict:
        """返回原始配置（含密钥，仅内部使用）"""
        return self._data

    def exists(self) -> bool:
        return os.path.exists(self.config_path)


# ─── DeviceService ──────────────────────────────────────────

class DeviceService:
    """音频设备扫描"""

    @staticmethod
    def scan() -> dict:
        """扫描系统音频设备，返回输入/输出设备列表"""
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            inputs = []
            outputs = []
            for i, d in enumerate(devices):
                entry = {
                    "index": i,
                    "name": d["name"],
                    "hostapi": sd.query_hostapis(d["hostapi"])["name"],
                    "max_input_channels": d["max_input_channels"],
                    "max_output_channels": d["max_output_channels"],
                    "default_samplerate": d["default_samplerate"],
                }
                if d["max_input_channels"] > 0:
                    inputs.append(entry)
                if d["max_output_channels"] > 0:
                    outputs.append(entry)
            return {"inputs": inputs, "outputs": outputs}
        except ImportError:
            return {"error": "sounddevice 未安装", "inputs": [], "outputs": []}
        except Exception as e:
            return {"error": str(e), "inputs": [], "outputs": []}


# ─── HealthService ──────────────────────────────────────────

class HealthService:
    """环境检测"""

    @staticmethod
    def check() -> dict:
        """检查运行环境依赖"""
        results = {}

        # Python 版本
        results["python"] = {
            "version": platform.python_version(),
            "ok": sys.version_info >= (3, 10),
        }

        # 关键依赖
        for mod_name, display in [
            ("sounddevice", "sounddevice"),
            ("websockets", "websockets"),
            ("yaml", "PyYAML"),
            ("google.protobuf", "protobuf"),
        ]:
            try:
                __import__(mod_name)
                results[display] = {"ok": True}
            except ImportError:
                results[display] = {"ok": False, "error": "未安装"}

        # ffmpeg（用于 ogg opus 解码）
        ffmpeg_path = shutil.which("ffmpeg")
        results["ffmpeg"] = {
            "ok": ffmpeg_path is not None,
            "path": ffmpeg_path,
        }

        # 平台信息
        results["platform"] = {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        }

        return results

    @staticmethod
    async def test_volcengine(config: dict) -> dict:
        """测试火山引擎连接（带认证头的真实握手）"""
        volc_cfg = config.get("volcengine", {})
        ws_url = volc_cfg.get("ws_url", "")
        app_key = volc_cfg.get("app_key", "")
        access_key = volc_cfg.get("access_key", "")
        resource_id = volc_cfg.get("resource_id", "volc.service_type.10053")

        if not ws_url or not app_key or app_key.startswith("YOUR_"):
            return {"ok": False, "error": "火山引擎凭据未配置"}
        if not access_key or access_key.startswith("YOUR_"):
            return {"ok": False, "error": "Access Key 未配置"}
        if "****" in app_key or "****" in access_key:
            return {"ok": False, "error": "密钥显示为脱敏值，请重新输入完整密钥后保存"}

        try:
            import websockets
            import uuid
            headers = {
                "X-Api-App-Key": app_key,
                "X-Api-Access-Key": access_key,
                "X-Api-Resource-Id": resource_id,
                "X-Api-Connect-Id": str(uuid.uuid4()),
            }
            async with websockets.connect(
                ws_url,
                additional_headers=headers,
                close_timeout=5,
            ) as ws:
                await ws.close()
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}


# ─── RuntimeService ─────────────────────────────────────────

class RuntimeService:
    """
    翻译器运行时管理。

    封装 DualChannelTranslator 的启停生命周期，
    提供状态查询和回调注入（字幕推送、状态变更通知）。
    """

    def __init__(self):
        self._translator = None
        self._task: Any = None  # asyncio.Task
        self._running = False
        self._start_time: float = 0
        self._ch1_state = "idle"
        self._ch2_state = "idle"

        # 外部注入的回调
        self.on_subtitle = None      # (**subtitle_payload) -> None
        self.on_state_change = None  # (state_dict) -> None

    @property
    def status(self) -> dict:
        import time as _time
        uptime = 0
        if self._running and self._start_time:
            uptime = int(_time.time() - self._start_time)
        return {
            "running": self._running,
            "ch1": self._ch1_state,
            "ch2": self._ch2_state,
            "uptime": uptime,
        }

    async def start(self, config: dict) -> dict:
        """启动翻译器"""
        import time as _time

        if self._running:
            return {"msg": "已在运行中"}

        # 启动前校验凭据
        volc = config.get("volcengine", {})
        app_key = volc.get("app_key", "")
        access_key = volc.get("access_key", "")
        if not app_key or not access_key:
            raise ValueError("火山引擎凭据未配置，请在配置页输入 App Key 和 Access Key 后保存")
        if "****" in str(app_key) or "****" in str(access_key):
            raise ValueError("密钥为脱敏值，请重新输入完整密钥后保存")

        # 延迟导入，避免 sounddevice 在 sidecar 启动时就被加载
        from main import DualChannelTranslator

        # 写入临时配置文件供 DualChannelTranslator 读取
        import tempfile
        tmp = tempfile.NamedTemporaryFile(
            mode='w', suffix='.yaml', delete=False, encoding='utf-8'
        )
        yaml.dump(config, tmp, allow_unicode=True, default_flow_style=False)
        tmp.close()

        try:
            self._translator = DualChannelTranslator(
                config_path=tmp.name,
                subtitle_callback=self.on_subtitle,
            )
        finally:
            os.unlink(tmp.name)

        self._running = True
        self._start_time = _time.time()
        self._ch1_state = "running"
        self._ch2_state = "running"
        self._notify_state_change()

        # 在后台 task 中运行翻译器
        self._task = asyncio.get_event_loop().create_task(self._run())

        return {"msg": "started"}

    async def _run(self):
        """后台运行翻译器"""
        try:
            await self._translator.start()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self._ch1_state = "error"
            self._ch2_state = "error"
            self._notify_state_change()
            raise
        finally:
            self._running = False
            self._ch1_state = "idle"
            self._ch2_state = "idle"
            self._notify_state_change()

    async def stop(self) -> dict:
        """停止翻译器"""
        if not self._running:
            return {"msg": "未在运行"}

        if self._translator:
            self._translator.is_running = False

        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        if self._translator:
            try:
                await self._translator.stop()
            except Exception:
                pass
            self._translator = None

        self._running = False
        self._start_time = 0
        self._ch1_state = "idle"
        self._ch2_state = "idle"
        self._notify_state_change()

        return {"msg": "stopped"}

    def _notify_state_change(self):
        if self.on_state_change:
            try:
                self.on_state_change(self.status)
            except Exception:
                pass
