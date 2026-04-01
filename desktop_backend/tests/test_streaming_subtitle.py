import importlib
import logging
import sys
import time
import types
from pathlib import Path
from types import SimpleNamespace


def _install_main_stubs():
    """为导入 main.py 安装最小依赖桩，避免测试依赖真实音频环境。"""
    stub_modules = {}

    events_mod = types.ModuleType("pb2.common.events_pb2")

    class Type:
        SourceSubtitleStart = 650
        SourceSubtitleResponse = 651
        SourceSubtitleEnd = 652
        TranslationSubtitleStart = 653
        TranslationSubtitleResponse = 654
        TranslationSubtitleEnd = 655

    events_mod.Type = Type
    stub_modules["pb2"] = types.ModuleType("pb2")
    stub_modules["pb2.common"] = types.ModuleType("pb2.common")
    stub_modules["pb2.common.events_pb2"] = events_mod

    # 同时注册包路径和源码路径两种导入方式。
    root_package = types.ModuleType("realtime_translator")
    root_package.__path__ = [str(Path(__file__).resolve().parents[2])]
    pb2_package = types.ModuleType("realtime_translator.pb2")
    pb2_package.__path__ = []
    common_package = types.ModuleType("realtime_translator.pb2.common")
    common_package.__path__ = []
    stub_modules["realtime_translator"] = root_package
    stub_modules["realtime_translator.pb2"] = pb2_package
    stub_modules["realtime_translator.pb2.common"] = common_package
    stub_modules["realtime_translator.pb2.common.events_pb2"] = events_mod

    audio_capture_mod = types.ModuleType("core.audio_capture")
    audio_capture_mod.AudioCapturer = type("AudioCapturer", (), {})
    stub_modules["core.audio_capture"] = audio_capture_mod

    audio_output_mod = types.ModuleType("core.audio_output")
    audio_output_mod.OggOpusPlayer = type("OggOpusPlayer", (), {})
    stub_modules["core.audio_output"] = audio_output_mod

    system_audio_mod = types.ModuleType("core.system_audio_capture")
    system_audio_mod.SystemAudioCapturer = type("SystemAudioCapturer", (), {})
    stub_modules["core.system_audio_capture"] = system_audio_mod

    volcengine_mod = types.ModuleType("core.volcengine_client")
    volcengine_mod.VolcengineTranslator = type("VolcengineTranslator", (), {})
    volcengine_mod.VolcengineConfig = type("VolcengineConfig", (), {})
    stub_modules["core.volcengine_client"] = volcengine_mod

    logging_utils_mod = types.ModuleType("core.logging_utils")

    def setup_logging(level=logging.INFO, enable_ws_handler=False):
        return logging.getLogger("test-main")

    class ChannelLogger:
        def __init__(self, logger, channel):
            self.logger = logger
            self.channel = channel

        def info(self, *args, **kwargs):
            return None

        def warning(self, *args, **kwargs):
            return None

        def error(self, *args, **kwargs):
            return None

        def debug(self, *args, **kwargs):
            return None

    logging_utils_mod.setup_logging = setup_logging
    logging_utils_mod.ChannelLogger = ChannelLogger
    stub_modules["core.logging_utils"] = logging_utils_mod

    for name, module in stub_modules.items():
        sys.modules[name] = module


_install_main_stubs()
main = importlib.import_module("main")


def _make_translator():
    """构造一个跳过 __init__ 的测试实例，只保留 CH2 逻辑所需状态。"""
    translator = main.DualChannelTranslator.__new__(main.DualChannelTranslator)
    translator.ch2_zh_buffer = ""
    translator.ch2_en_buffer = ""
    translator.ch2_last_update_time = 0.0
    translator.ch2_sentence_active = False
    translator.ch2_source_completed = False
    translator.ch2_translation_completed = False
    translator.subtitle_window_thread = None
    captured = []
    translator.subtitle_callback = lambda **payload: captured.append(payload)
    return translator, captured


def test_ch2_streaming_lifecycle_emits_start_streaming_and_end():
    translator, captured = _make_translator()

    translator._handle_ch2_subtitle_result(SimpleNamespace(event=main.CH2_SOURCE_SUBTITLE_START, text=""))
    translator._handle_ch2_subtitle_result(SimpleNamespace(event=main.CH2_SOURCE_SUBTITLE_RESPONSE, text="How are you"))
    translator._handle_ch2_subtitle_result(SimpleNamespace(event=main.CH2_TRANSLATION_SUBTITLE_RESPONSE, text="你好吗"))
    translator._handle_ch2_subtitle_result(SimpleNamespace(event=main.CH2_TRANSLATION_SUBTITLE_END, text="你好吗？"))

    assert captured == [
        {"type": "start", "en": "", "zh": "", "is_final": False},
        {"type": "streaming", "en": "How are you", "zh": "", "is_final": False},
        {"type": "streaming", "en": "How are you", "zh": "你好吗", "is_final": False},
        {"type": "end", "en": "How are you", "zh": "你好吗？", "is_final": True},
    ]
    assert translator.ch2_sentence_active is False


def test_ch2_timeout_fallback_flushes_open_sentence():
    translator, captured = _make_translator()

    translator._handle_ch2_subtitle_result(SimpleNamespace(event=main.CH2_SOURCE_SUBTITLE_START, text=""))
    translator._handle_ch2_subtitle_result(SimpleNamespace(event=main.CH2_SOURCE_SUBTITLE_RESPONSE, text="Good morning"))
    translator.ch2_last_update_time = time.time() - 3.2

    flushed = translator._flush_stale_ch2_sentence(timeout_seconds=3.0)

    assert flushed is True
    assert captured[-1] == {
        "type": "end",
        "en": "Good morning",
        "zh": "",
        "is_final": True,
    }
    assert translator.ch2_sentence_active is False
