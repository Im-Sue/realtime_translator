"""
桌面后端 sidecar 入口 - WebSocket Server

Tauri 通过子进程拉起本文件，Python 端启动 WebSocket server 提供：
  /ws/control   — 请求/响应式命令（配置、启停、设备扫描）
  /ws/logs      — 服务端推送日志流
  /ws/subtitle  — 服务端推送字幕流

启动流程：
  1. 绑定 127.0.0.1:0（自动分配端口）
  2. stdout 输出 {"ready": true, "port": N}
  3. Tauri 前端连接 ws://127.0.0.1:N

用法：
  # 生产模式（Tauri 拉起）
  rt-engine.exe desktop_backend/sidecar.py --parent-pid 12345

  # 开发模式（手动跑，固定端口）
  python desktop_backend/sidecar.py --dev --port 18923
"""

import asyncio
import argparse
import json
import os
import sys
import signal
import threading
import time
from typing import Set

import websockets
try:
    from websockets import serve  # websockets >= 14
except ImportError:
    from websockets.server import serve  # fallback

# 确保项目根目录在 Python 路径中
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# 直接按文件路径加载 logging_utils，绕过 core/__init__.py（避免拉起音频依赖）
import importlib.util as _ilu
_spec = _ilu.spec_from_file_location(
    "core.logging_utils",
    os.path.join(PROJECT_ROOT, "core", "logging_utils.py"),
)
_logging_utils = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_logging_utils)
setup_logging = _logging_utils.setup_logging
ChannelLogger = _logging_utils.ChannelLogger
get_ws_handler = _logging_utils.get_ws_handler

from desktop_backend.services import ConfigService, DeviceService, HealthService, RuntimeService


# ─── 全局状态 ───────────────────────────────────────────────

# 各端点的已连接客户端集合
control_clients: Set = set()
log_clients: Set = set()
subtitle_clients: Set = set()

# 日志
_logger = setup_logging(enable_ws_handler=True)
sys_log = ChannelLogger(_logger, "SYS")

# 服务实例
config_service = ConfigService()
device_service = DeviceService()
health_service = HealthService()
runtime_service = RuntimeService()


# ─── 心跳 Watchdog ──────────────────────────────────────────

def _is_process_alive(pid: int) -> bool:
    """检查进程是否存活（跨平台）"""
    if sys.platform == "win32":
        import ctypes
        kernel32 = ctypes.windll.kernel32
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if handle:
            kernel32.CloseHandle(handle)
            return True
        return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def start_watchdog(parent_pid: int, interval: int = 3):
    """守护线程：父进程消失则自杀"""
    def _watch():
        while True:
            if not _is_process_alive(parent_pid):
                sys_log.warning("父进程 %d 已退出，sidecar 自动终止", parent_pid)
                os._exit(1)
            time.sleep(interval)

    t = threading.Thread(target=_watch, daemon=True)
    t.start()
    sys_log.info("Watchdog 已启动，监控父进程 PID=%d", parent_pid)


# ─── WebSocket 广播工具 ─────────────────────────────────────

async def broadcast_to(clients: Set, message: dict):
    """向一组客户端广播 JSON 消息"""
    if not clients:
        return
    data = json.dumps(message, ensure_ascii=False)
    dead = set()
    for ws in clients:
        try:
            await ws.send(data)
        except websockets.ConnectionClosed:
            dead.add(ws)
    clients -= dead


# 事件循环引用（在 start_server 中设置）
_loop: asyncio.AbstractEventLoop = None


def broadcast_log_sync(entry: dict):
    """同步广播日志（从 logging Handler 调用，非 async 上下文）"""
    if not log_clients or not _loop:
        return
    data = json.dumps(entry, ensure_ascii=False)
    for ws in list(log_clients):
        try:
            _loop.call_soon_threadsafe(
                asyncio.ensure_future, ws.send(data)
            )
        except Exception:
            pass


def broadcast_subtitle_sync(subtitle_data: dict):
    """同步广播字幕（从 DualChannelTranslator 回调调用）"""
    if not subtitle_clients or not _loop:
        return
    data = json.dumps(subtitle_data, ensure_ascii=False)
    for ws in list(subtitle_clients):
        try:
            _loop.call_soon_threadsafe(
                asyncio.ensure_future, ws.send(data)
            )
        except Exception:
            pass


# ─── /ws/control 处理 ───────────────────────────────────────

async def handle_control(websocket):
    """处理 /ws/control 连接"""
    control_clients.add(websocket)
    sys_log.info("control 客户端已连接 (共 %d)", len(control_clients))
    try:
        async for raw in websocket:
            try:
                msg = json.loads(raw)
                req_id = msg.get("id", "")
                cmd = msg.get("cmd", "")
                payload = msg.get("payload", {})

                sys_log.debug("← control cmd=%s id=%s", cmd, req_id)

                # 命令分发（P2-2 中实现具体逻辑）
                result = await dispatch_command(cmd, payload)

                await websocket.send(json.dumps({
                    "id": req_id,
                    "ok": True,
                    "data": result,
                }, ensure_ascii=False))

            except Exception as e:
                req_id = msg.get("id", "") if isinstance(msg, dict) else ""
                await websocket.send(json.dumps({
                    "id": req_id,
                    "ok": False,
                    "error": str(e),
                }, ensure_ascii=False))
                sys_log.error("control 命令处理错误: %s", e)

    except websockets.ConnectionClosed:
        pass
    finally:
        control_clients.discard(websocket)
        sys_log.info("control 客户端已断开 (剩余 %d)", len(control_clients))


async def dispatch_command(cmd: str, payload: dict) -> dict:
    """命令分发路由"""

    if cmd == "status":
        return runtime_service.status

    elif cmd == "load_config":
        return config_service.load()

    elif cmd == "save_config":
        data = payload.get("config")
        if not data:
            raise ValueError("payload.config 不能为空")
        result = config_service.save(data)
        await broadcast_subtitle_config()
        return result

    elif cmd == "scan_devices":
        return device_service.scan()

    elif cmd == "env_check":
        return health_service.check()

    elif cmd == "test_connection":
        raw_cfg = config_service.get_raw_config()
        return await health_service.test_volcengine(raw_cfg)

    elif cmd == "start":
        config = config_service.get_raw_config()
        if not config:
            # 自动加载配置
            config = config_service.load()
            config = config_service.get_raw_config()
        return await runtime_service.start(config)

    elif cmd == "stop":
        return await runtime_service.stop()

    else:
        raise ValueError(f"未知命令: {cmd}")


# ─── /ws/logs 处理 ──────────────────────────────────────────

async def handle_logs(websocket):
    """处理 /ws/logs 连接，推送历史日志后持续推送新日志"""
    log_clients.add(websocket)
    sys_log.info("logs 客户端已连接 (共 %d)", len(log_clients))

    # 推送历史日志
    ws_handler = get_ws_handler()
    if ws_handler:
        for entry in ws_handler.get_history():
            try:
                await websocket.send(json.dumps(entry, ensure_ascii=False))
            except websockets.ConnectionClosed:
                log_clients.discard(websocket)
                return

    # 保持连接（日志通过 broadcast_log_sync 推送）
    try:
        async for _ in websocket:
            pass  # 客户端不应发消息，忽略
    except websockets.ConnectionClosed:
        pass
    finally:
        log_clients.discard(websocket)
        sys_log.info("logs 客户端已断开 (剩余 %d)", len(log_clients))


# ─── 字幕配置推送 ──────────────────────────────────────────

def _get_subtitle_config() -> dict:
    """从 config_service 读取字幕配置，包装为推送格式"""
    raw = config_service.get_raw_config()
    sw = raw.get("subtitle_window", {})
    return {
        "type": "subtitle_config",
        "font_size": sw.get("font_size", 16),
        "opacity": sw.get("opacity", 0.85),
        "text_color": sw.get("text_color", "#FFFFFF"),
    }


async def broadcast_subtitle_config():
    """广播字幕配置更新到所有 subtitle 客户端"""
    await broadcast_to(subtitle_clients, _get_subtitle_config())


# ─── /ws/subtitle 处理 ──────────────────────────────────────

async def handle_subtitle(websocket):
    """处理 /ws/subtitle 连接"""
    subtitle_clients.add(websocket)
    sys_log.info("subtitle 客户端已连接 (共 %d)", len(subtitle_clients))

    # 连接时推送当前字幕配置
    try:
        subtitle_cfg = _get_subtitle_config()
        await websocket.send(json.dumps(subtitle_cfg, ensure_ascii=False))
    except websockets.ConnectionClosed:
        subtitle_clients.discard(websocket)
        return

    try:
        async for _ in websocket:
            pass  # 客户端不应发消息
    except websockets.ConnectionClosed:
        pass
    finally:
        subtitle_clients.discard(websocket)
        sys_log.info("subtitle 客户端已断开 (剩余 %d)", len(subtitle_clients))


# ─── 路由分发 ───────────────────────────────────────────────

async def ws_handler(websocket):
    """根据 path 分发到对应 handler"""
    path = websocket.request.path if hasattr(websocket, 'request') else getattr(websocket, 'path', '/')

    if path == "/ws/control":
        await handle_control(websocket)
    elif path == "/ws/logs":
        await handle_logs(websocket)
    elif path == "/ws/subtitle":
        await handle_subtitle(websocket)
    else:
        await websocket.close(4004, f"未知路径: {path}")


# ─── 主入口 ─────────────────────────────────────────────────

async def start_server(host: str = "127.0.0.1", port: int = 0):
    """启动 WebSocket server"""
    global _loop
    _loop = asyncio.get_event_loop()

    # 绑定 WS 日志广播
    ws_handler_inst = get_ws_handler()
    if ws_handler_inst:
        ws_handler_inst.set_broadcast(broadcast_log_sync)

    # 绑定字幕推送回调（DualChannelTranslator → WS 客户端）
    def _subtitle_callback(
        type: str = "update",
        en: str = "",
        zh: str = "",
        is_final: bool = False,
    ):
        broadcast_subtitle_sync({
            "type": type,
            "en": en,
            "zh": zh,
            "is_final": is_final,
        })
    runtime_service.on_subtitle = _subtitle_callback

    # 绑定状态变更广播
    def _state_change(status: dict):
        if not control_clients or not _loop:
            return
        msg = json.dumps({"id": "", "ok": True, "data": {"event": "state_change", **status}}, ensure_ascii=False)
        for ws in list(control_clients):
            try:
                _loop.call_soon_threadsafe(asyncio.ensure_future, ws.send(msg))
            except Exception:
                pass
    runtime_service.on_state_change = _state_change

    server = await serve(ws_handler, host, port)

    # 获取实际绑定的端口
    actual_port = server.sockets[0].getsockname()[1]

    # 输出 ready 信号（Tauri 读这一行）
    ready_msg = json.dumps({"ready": True, "port": actual_port})
    print(ready_msg, flush=True)

    sys_log.info("WebSocket server 已启动: ws://%s:%d", host, actual_port)
    sys_log.info("端点: /ws/control, /ws/logs, /ws/subtitle")

    # 保持运行
    await asyncio.Future()  # 永不完成


def main():
    parser = argparse.ArgumentParser(description="实时同传桌面后端 sidecar")
    parser.add_argument("--dev", action="store_true", help="开发模式")
    parser.add_argument("--port", type=int, default=0, help="固定端口（默认自动分配）")
    parser.add_argument("--parent-pid", type=int, default=0, help="父进程 PID（用于心跳检测）")
    args = parser.parse_args()

    # 启动心跳监控
    if args.parent_pid > 0:
        start_watchdog(args.parent_pid)
    elif not args.dev:
        sys_log.warning("未指定 --parent-pid，跳过心跳监控（仅开发模式安全）")

    if args.dev:
        sys_log.info("开发模式启动")

    sys_log.info("配置文件路径: %s (已存在: %s)", config_service.config_path, config_service.exists())

    # 启动 server
    try:
        asyncio.run(start_server(port=args.port))
    except KeyboardInterrupt:
        sys_log.info("sidecar 已终止")


if __name__ == "__main__":
    main()
