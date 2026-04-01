"""
日志工具模块 - 带通道标识的结构化日志系统

提供 ChannelLogger 适配器，为每条日志自动注入通道标识（SYS/CH1/CH2），
统一日志格式，支持 WS 实时推送。

用法:
    from core.logging_utils import setup_logging, ChannelLogger

    logger = setup_logging()
    sys_log = ChannelLogger(logger, "SYS")
    ch1_log = ChannelLogger(logger, "CH1")
    ch2_log = ChannelLogger(logger, "CH2")

    sys_log.info("翻译器已启动")
    ch1_log.debug("音频块 #%d size=%dB", chunk_id, len(data))
"""

import logging
import time
from collections import deque
from typing import Callable, Optional


# 日志格式常量
LOG_FORMAT = '%(asctime)s.%(msecs)03d [%(levelname)-5s] [%(channel)-3s] [%(module)-8s] %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
def _default_log_path() -> str:
    """根据运行环境决定日志文件路径（生产环境写入 AppData，开发环境写入 CWD）"""
    import os as _os
    import sys as _sys

    # 优先使用 Tauri 注入的 RT_APP_DATA
    app_data = _os.environ.get("RT_APP_DATA")
    if app_data:
        log_dir = _os.path.join(app_data, "logs")
        _os.makedirs(log_dir, exist_ok=True)
        return _os.path.join(log_dir, "realtime_translator.log")

    # 检测生产模式（从 rt-engine.exe 启动）
    exe_name = _os.path.basename(_sys.executable).lower()
    if exe_name.startswith("rt-engine"):
        appdata = _os.environ.get("APPDATA")
        if appdata:
            log_dir = _os.path.join(appdata, "RealtimeTranslator", "logs")
            _os.makedirs(log_dir, exist_ok=True)
            return _os.path.join(log_dir, "realtime_translator.log")

    # 开发模式：CWD
    return "realtime_translator.log"


LOG_FILE = _default_log_path()


class ChannelFormatter(logging.Formatter):
    """自定义 Formatter，注入 channel 字段（缺省为 SYS）"""

    def format(self, record):
        if not hasattr(record, 'channel'):
            record.channel = 'SYS'
        return super().format(record)


class WSLogHandler(logging.Handler):
    """
    日志 Handler：通过回调推送日志到 WebSocket 客户端。

    同时维护一个环形缓冲区（最近 max_buffer 条），
    新 WS 客户端连接时可一次性拉取历史日志。
    """

    def __init__(self, broadcast_fn: Optional[Callable] = None, max_buffer: int = 500):
        super().__init__()
        self.broadcast_fn = broadcast_fn
        self.buffer = deque(maxlen=max_buffer)

    def set_broadcast(self, fn: Callable):
        """设置广播回调（延迟绑定，sidecar 启动后再设置）"""
        self.broadcast_fn = fn

    def emit(self, record):
        try:
            entry = self._format_entry(record)
            self.buffer.append(entry)
            if self.broadcast_fn:
                self.broadcast_fn(entry)
        except Exception:
            self.handleError(record)

    def get_history(self) -> list:
        """获取缓冲区中的历史日志"""
        return list(self.buffer)

    def _format_entry(self, record) -> dict:
        """将 LogRecord 转为可 JSON 序列化的 dict"""
        return {
            "ts": time.strftime('%H:%M:%S', time.localtime(record.created))
                  + f'.{int(record.msecs):03d}',
            "level": record.levelname,
            "channel": getattr(record, 'channel', 'SYS'),
            "module": (record.module or 'unknown')[:8],
            "msg": record.getMessage(),
        }


class ChannelLogger:
    """
    带通道标识的日志适配器。

    将 channel 字段（SYS/CH1/CH2）自动注入每条日志的 extra 中，
    上层代码无需手动传递。
    """

    def __init__(self, logger: logging.Logger, channel: str):
        self.logger = logger
        self.channel = channel

    def debug(self, msg, *args, **kwargs):
        kwargs.setdefault('extra', {})['channel'] = self.channel
        kwargs.setdefault('stacklevel', 2)
        self.logger.debug(msg, *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        kwargs.setdefault('extra', {})['channel'] = self.channel
        kwargs.setdefault('stacklevel', 2)
        self.logger.info(msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        kwargs.setdefault('extra', {})['channel'] = self.channel
        kwargs.setdefault('stacklevel', 2)
        self.logger.warning(msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        kwargs.setdefault('extra', {})['channel'] = self.channel
        kwargs.setdefault('stacklevel', 2)
        self.logger.error(msg, *args, **kwargs)

    def exception(self, msg, *args, **kwargs):
        kwargs.setdefault('extra', {})['channel'] = self.channel
        kwargs.setdefault('stacklevel', 2)
        self.logger.exception(msg, *args, **kwargs)


# 全局 WS handler 实例（延迟绑定广播函数）
_ws_handler: Optional[WSLogHandler] = None


def get_ws_handler() -> Optional[WSLogHandler]:
    """获取全局 WS log handler（供 sidecar 绑定广播回调）"""
    return _ws_handler


def setup_logging(
    level: int = logging.INFO,
    log_file: str = LOG_FILE,
    enable_ws_handler: bool = False,
) -> logging.Logger:
    """
    初始化日志系统。

    Args:
        level: 日志级别
        log_file: 日志文件路径
        enable_ws_handler: 是否启用 WS 推送 handler（桌面模式开启）

    Returns:
        配置好的 root logger
    """
    global _ws_handler

    logger = logging.getLogger('realtime_translator')
    logger.setLevel(level)

    # 避免重复添加 handler
    if logger.handlers:
        return logger

    formatter = ChannelFormatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    # 文件 handler
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)
    logger.addHandler(file_handler)

    # 控制台 handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)
    logger.addHandler(console_handler)

    # WS 推送 handler（桌面模式）
    if enable_ws_handler:
        _ws_handler = WSLogHandler()
        _ws_handler.setFormatter(formatter)
        _ws_handler.setLevel(level)
        logger.addHandler(_ws_handler)

    return logger
