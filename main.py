"""
实时同声传译器 v2.0 - 双向翻译主程序 (耳机模式)

Channel 1: 麦克风(中文) → 火山引擎(s2s) → VB-CABLE(英文) → Zoom → 对方听到英文
Channel 2: Zoom(英文) → 系统音频 → 火山引擎(s2t) → 字幕窗口(中文) → 你看到中文字幕

核心特性:
- 双通道独立并发执行
- 耳机物理隔离，无回声问题
- 简化架构，无需复杂冲突检测
- 线程安全的字幕更新
"""

import asyncio
import yaml
import logging
import time
import sys
import signal
import re
from pathlib import Path
from core.volcengine_client import VolcengineTranslator, VolcengineConfig
from core.logging_utils import setup_logging, ChannelLogger
# NOTE: gui.subtitle_window 依赖 tkinter, Embedded Python 不包含 tkinter
# 延迟到 CLI 模式实际需要时再导入（见 _init_components）

# 初始化日志系统
_logger = setup_logging(level=logging.INFO)
sys_log = ChannelLogger(_logger, "SYS")
ch1_log = ChannelLogger(_logger, "CH1")
ch2_log = ChannelLogger(_logger, "CH2")


CH2_SOURCE_SUBTITLE_START = 650
CH2_SOURCE_SUBTITLE_RESPONSE = 651
CH2_SOURCE_SUBTITLE_END = 652
CH2_TRANSLATION_SUBTITLE_START = 653
CH2_TRANSLATION_SUBTITLE_RESPONSE = 654
CH2_TRANSLATION_SUBTITLE_END = 655

CH2_SUBTITLE_EVENTS = {
    CH2_SOURCE_SUBTITLE_START,
    CH2_SOURCE_SUBTITLE_RESPONSE,
    CH2_SOURCE_SUBTITLE_END,
    CH2_TRANSLATION_SUBTITLE_START,
    CH2_TRANSLATION_SUBTITLE_RESPONSE,
    CH2_TRANSLATION_SUBTITLE_END,
}


class DualChannelTranslator:
    """
    双通道实时翻译器 (耳机模式)

    Channel 1: 麦克风(中文) → VB-CABLE(英文) [s2s]
    Channel 2: 系统音频(英文) → 字幕窗口(中文) [s2t]
    """

    def __init__(self, config_path: str = "config.yaml", subtitle_callback=None):
        """
        初始化双通道翻译器

        Args:
            config_path: 配置文件路径
            subtitle_callback: 字幕输出回调（桌面模式由 RuntimeService 传入，
                               传入后跳过 Tkinter 初始化）
        """

        sys_log.info("=" * 80)
        sys_log.info("实时同声传译器 v3.0 (双向翻译 - 耳机模式)")
        sys_log.info("=" * 80)
        sys_log.info("Channel 1: 你说中文 → 对方听英文")
        sys_log.info("Channel 2: 对方说英文 → 你看中文字幕")
        sys_log.info("重要: 请使用耳机，避免音频回声!")
        sys_log.info("=" * 80)

        # 加载配置
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
            sys_log.info("配置文件加载成功: %s", config_path)
        except FileNotFoundError:
            sys_log.error("配置文件未找到: %s", config_path)
            sys_log.error("   请从 config.yaml.example 复制一份为 config.yaml")
            raise

        self.is_running = False

        channels_cfg = self.config.get('channels', {})
        self.channel1_enabled = channels_cfg.get('zh_to_en', {}).get('enabled', True)
        self.channel2_enabled = channels_cfg.get('en_to_zh', {}).get('enabled', True)

        # 统计信息
        self.stats = {
            'ch1_audio_chunks': 0,      # Channel 1 发送的音频块数
            'ch1_text_segments': 0,     # Channel 1 接收的文本片段数
            'ch1_audio_received': 0,    # Channel 1 接收的音频块数
            'ch2_audio_chunks': 0,      # Channel 2 发送的音频块数
            'ch2_text_segments': 0,     # Channel 2 接收的文本片段数
            'start_time': None,
            'first_ch1_audio_time': None,
            'first_ch2_text_time': None,
            'total_ch1_audio_bytes': 0,
            'total_ch2_audio_bytes': 0
        }

        # Channel 2 当前句状态（利用 API 的 Start/Response/End 生命周期直推前端）
        self.ch2_zh_buffer = ""
        self.ch2_en_buffer = ""
        self.ch2_last_update_time = 0.0
        self.ch2_sentence_active = False
        self.ch2_source_completed = False
        self.ch2_translation_completed = False

        # 字幕输出回调（桌面模式下由 RuntimeService 通过构造参数传入）
        self.subtitle_callback = subtitle_callback

        # 初始化组件
        self._init_components()

    def _is_mostly_english(self, text: str) -> bool:
        if not text:
            return False
        latin = sum(1 for c in text if c.isalpha() and ord(c) < 128)
        chinese = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        total = latin + chinese
        if total == 0:
            return False
        return (latin / total) > 0.55

    def _reset_ch2_sentence_state(self):
        """重置 Channel 2 当前句状态。"""
        self.ch2_en_buffer = ""
        self.ch2_zh_buffer = ""
        self.ch2_last_update_time = 0.0
        self.ch2_sentence_active = False
        self.ch2_source_completed = False
        self.ch2_translation_completed = False

    def _emit_ch2_subtitle(self, message_type: str, is_final: bool = False):
        """按统一消息格式输出字幕，桌面模式和 CLI 模式共用一套状态。"""
        en = self.ch2_en_buffer.strip()
        zh = self.ch2_zh_buffer.strip()

        if self.subtitle_callback:
            self.subtitle_callback(
                type=message_type,
                en=en,
                zh=zh,
                is_final=is_final,
            )
        elif self.subtitle_window_thread:
            if message_type == "start":
                self.subtitle_window_thread.update_subtitle("")
                return

            parts = []
            if en:
                parts.append(f"EN  {en}")
            if zh:
                parts.append(f"ZH  {zh}")
            self.subtitle_window_thread.update_subtitle("\n".join(parts))

        ch2_log.debug(
            "字幕事件: type=%s en=%dc zh=%dc final=%s",
            message_type,
            len(en),
            len(zh),
            is_final,
        )

    def _start_ch2_sentence(self):
        """开启新句；若上一句意外未结束，先补发结束事件。"""
        has_content = bool(self.ch2_en_buffer.strip() or self.ch2_zh_buffer.strip())
        if self.ch2_sentence_active and not has_content:
            self.ch2_last_update_time = time.time()
            return

        if self.ch2_sentence_active and has_content:
            self._finish_ch2_sentence()

        self._reset_ch2_sentence_state()
        self.ch2_sentence_active = True
        self.ch2_last_update_time = time.time()
        self._emit_ch2_subtitle("start", is_final=False)

    def _update_ch2_buffer(self, event: int, text: str):
        """根据事件类型更新 EN/ZH 当前句内容。"""
        clean_text = re.sub(r"\s+", " ", text.strip())
        if not clean_text:
            return

        is_english = self._is_mostly_english(clean_text)
        if event in (CH2_SOURCE_SUBTITLE_RESPONSE, CH2_SOURCE_SUBTITLE_END):
            if is_english or not self.ch2_zh_buffer:
                self.ch2_en_buffer = clean_text
            else:
                self.ch2_zh_buffer = clean_text
        else:
            if is_english and not self.ch2_zh_buffer:
                self.ch2_en_buffer = clean_text
            else:
                self.ch2_zh_buffer = clean_text

        self.ch2_last_update_time = time.time()

    def _finish_ch2_sentence(self) -> bool:
        """结束当前句并推送最终字幕。"""
        has_content = bool(self.ch2_en_buffer.strip() or self.ch2_zh_buffer.strip())
        if not self.ch2_sentence_active and not has_content:
            return False

        if has_content:
            self._emit_ch2_subtitle("end", is_final=True)

        self._reset_ch2_sentence_state()
        return has_content

    def _flush_stale_ch2_sentence(self, timeout_seconds: float = 3.0) -> bool:
        """在 End 丢失时，通过超时补发结束事件。"""
        if not self.ch2_sentence_active or not self.ch2_last_update_time:
            return False

        if time.time() - self.ch2_last_update_time < timeout_seconds:
            return False

        ch2_log.warning("字幕结束事件超时缺失，已按 %.1f 秒兜底补发结束", timeout_seconds)
        return self._finish_ch2_sentence()

    def _handle_ch2_subtitle_result(self, result):
        """处理 Channel 2 字幕事件，直接向前端推送 start/streaming/end。"""
        if result.event not in CH2_SUBTITLE_EVENTS:
            return

        if result.event in (CH2_SOURCE_SUBTITLE_START, CH2_TRANSLATION_SUBTITLE_START):
            self._start_ch2_sentence()
            return

        if result.text and not self.ch2_sentence_active:
            self._start_ch2_sentence()

        if result.text:
            self._update_ch2_buffer(result.event, result.text)

        if result.event in (CH2_SOURCE_SUBTITLE_RESPONSE, CH2_TRANSLATION_SUBTITLE_RESPONSE):
            self._emit_ch2_subtitle("streaming", is_final=False)
            return

        if result.event == CH2_SOURCE_SUBTITLE_END:
            self.ch2_source_completed = True
            self._emit_ch2_subtitle("streaming", is_final=False)
            if self.ch2_translation_completed:
                self._finish_ch2_sentence()
            return

        if result.event == CH2_TRANSLATION_SUBTITLE_END:
            self.ch2_translation_completed = True
            self._finish_ch2_sentence()

    def _init_components(self):
        """初始化所有组件"""
        import sounddevice as sd  # 延迟导入: 避免顶层加载 C 扩展
        from core.audio_capture import AudioCapturer
        from core.audio_output import OggOpusPlayer, PcmStreamPlayer
        from core.system_audio_capture import SystemAudioCapturer

        sys_log.info("正在初始化组件...")

        # 1. 麦克风捕获 (Channel 1 输入)
        ch1_log.info("初始化输入设备...")
        audio_config = self.config['audio']

        self.mic_capturer = None
        if self.channel1_enabled:
            self.mic_capturer = AudioCapturer(
                device_name=audio_config['microphone']['device'],
                sample_rate=16000,
                channels=1,
                chunk_size=1600  # 100ms @ 16kHz
            )
            ch1_log.info("麦克风捕获器已初始化")
        else:
            ch1_log.warning("Channel 1 已禁用：跳过麦克风初始化")

        # 2. 系统音频捕获 (Channel 2 输入)
        ch2_log.info("初始化输入设备...")
        system_audio_config = audio_config['system_audio']

        self.system_audio_capturer = SystemAudioCapturer(
            device_name=system_audio_config['device'],
            fallback_device=system_audio_config['fallback_device'],
            sample_rate=16000,
            channels=1,
            chunk_size=1600
        )
        ch2_log.info("系统音频捕获器已初始化")

        # 3. 音频播放器 (Channel 1 输出 → VB-CABLE)
        ch1_log.info("初始化输出设备...")
        self.audio_player = None

        if self.channel1_enabled:
            vbcable_config = audio_config['vbcable_output']
            target_format = vbcable_config.get('target_format', 'ogg_opus')
            output_sample_rate = vbcable_config.get(
                'sample_rate',
                48000 if target_format == 'pcm' else 24000
            )

            # 查找 VB-CABLE Input 设备
            devices = sd.query_devices()
            cable_input_idx = None
            config_device_name = vbcable_config.get('device', 'CABLE Input')
            cable_keywords = [config_device_name, 'CABLE Input', 'CABLE In']
            for keyword in cable_keywords:
                if cable_input_idx is not None:
                    break
                for i, device in enumerate(devices):
                    if keyword in device['name'] and device['max_output_channels'] > 0:
                        cable_input_idx = i
                        ch1_log.info("找到 VB-CABLE Input: [%d] %s (关键词: '%s')", i, device['name'], keyword)
                        break

            if cable_input_idx is None:
                ch1_log.warning("未找到 VB-CABLE Input 设备! 将使用默认扬声器(测试模式)")
                ch1_log.warning("已搜索关键词: %s", cable_keywords)
                cable_input_idx = sd.default.device[1]

            cable_input_device = devices[cable_input_idx]['name']
            ch1_log.info("输出设备: %s", cable_input_device)
            ch1_log.info(
                "输出设备能力: 输出通道=%s 默认采样率=%sHz 目标格式=%s 目标采样率=%sHz",
                devices[cable_input_idx]['max_output_channels'],
                devices[cable_input_idx]['default_samplerate'],
                target_format,
                output_sample_rate,
            )

            if target_format == 'pcm':
                self.audio_player = PcmStreamPlayer(
                    device_name=cable_input_device,
                    output_rate=output_sample_rate,
                    channels=2,
                    api_channels=1,
                )
            else:
                self.audio_player = OggOpusPlayer(
                    device_name=cable_input_device,
                    sample_rate=24000,
                    use_ffmpeg=vbcable_config.get('use_ffmpeg', True),
                    monitor_device=None,
                    enable_monitor=False
                )
            ch1_log.info("音频播放器已初始化")
        else:
            ch1_log.warning("Channel 1 已禁用：跳过音频播放器初始化")

        # 4. 字幕窗口 (Channel 2 输出 - 仅 CLI 模式)
        # 桌面模式下 subtitle_callback 会由 RuntimeService 注入，跳过 Tkinter
        self.subtitle_window = None
        self.subtitle_window_thread = None

        if not self.subtitle_callback:
            ch2_log.info("初始化字幕窗口 (CLI 模式)...")
            # 延迟导入: tkinter 在 Embedded Python 中不可用
            from gui.subtitle_window import SubtitleWindow, SubtitleWindowThread
            subtitle_config = self.config.get('subtitle_window', {})

            self.subtitle_window = SubtitleWindow(
                width=subtitle_config.get('width', 400),
                height=subtitle_config.get('height', 800),
                font_size=subtitle_config.get('font_size', 20),
                bg_color=subtitle_config.get('bg_color', '#000000'),
                text_color=subtitle_config.get('text_color', '#FFFFFF'),
                opacity=subtitle_config.get('opacity', 0.85),
                position=subtitle_config.get('position', 'top_right'),
                max_history=subtitle_config.get('max_history', 1000),
                show_timestamp=subtitle_config.get('show_timestamp', False)
            )

            # 使用线程包装器
            self.subtitle_window_thread = SubtitleWindowThread(self.subtitle_window)
            ch2_log.info("字幕窗口已初始化")
        else:
            ch2_log.info("桌面模式：跳过 Tkinter 字幕窗口初始化")

        # 5. 火山引擎翻译客户端 (两个独立连接)
        sys_log.info("初始化火山引擎翻译客户端...")

        volcengine_cfg = VolcengineConfig(
            ws_url=self.config['volcengine']['ws_url'],
            app_key=self.config['volcengine']['app_key'],
            access_key=self.config['volcengine']['access_key'],
            resource_id=self.config['volcengine'].get('resource_id', 'volc.service_type.10053')
        )

        # Channel 1: 中文 → 英文 (s2s)
        channels_config = self.config.get('channels', {})
        ch1_config = channels_config.get('zh_to_en', {})
        ch1_target_format = audio_config.get('vbcable_output', {}).get('target_format', 'ogg_opus')
        ch1_target_rate = audio_config.get('vbcable_output', {}).get(
            'sample_rate',
            48000 if ch1_target_format == 'pcm' else 24000
        )

        if self.channel1_enabled:
            self.translator_zh_to_en = VolcengineTranslator(
                config=volcengine_cfg,
                mode=ch1_config.get('mode', 's2s'),
                source_language=ch1_config.get('source_language', 'zh'),
                target_language=ch1_config.get('target_language', 'en'),
                target_audio_format=ch1_target_format,
                target_audio_rate=ch1_target_rate,
            )
            ch1_log.info("翻译器已初始化: 中文 → 英文 (s2s)")
        else:
            self.translator_zh_to_en = None
            ch1_log.warning("Channel 1 已禁用")

        # Channel 2: 英文 → 中文 (s2t)
        ch2_config = channels_config.get('en_to_zh', {})

        if self.channel2_enabled:
            self.translator_en_to_zh = VolcengineTranslator(
                config=volcengine_cfg,
                mode=ch2_config.get('mode', 's2t'),  # speech to text!
                source_language=ch2_config.get('source_language', 'en'),
                target_language=ch2_config.get('target_language', 'zh')
            )
            ch2_log.info("翻译器已初始化: 英文 → 中文 (s2t)")
        else:
            self.translator_en_to_zh = None
            ch2_log.warning("Channel 2 已禁用")

        sys_log.info("所有组件初始化完成")

    async def start(self):
        """启动双通道翻译器"""

        self.is_running = True
        self.stats['start_time'] = time.time()

        # 1. 启动音频捕获
        sys_log.info("启动音频捕获...")
        if self.mic_capturer:
            self.mic_capturer.start()
        self.system_audio_capturer.start()

        # 2. 启动音频播放器
        if self.audio_player:
            ch1_log.info("启动音频播放器...")
            self.audio_player.start()
        else:
            ch1_log.info("音频输出已关闭（仅字幕模式）")

        # 3. 启动字幕窗口 (非阻塞, 仅 CLI 模式)
        if self.subtitle_window_thread:
            ch2_log.info("启动字幕窗口...")
            self.subtitle_window_thread.start()

        # 4. 连接火山引擎
        sys_log.info("连接火山引擎...")

        if self.translator_zh_to_en:
            await self.translator_zh_to_en.connect()
            await self.translator_zh_to_en.start_session()
            ch1_log.info("火山引擎已连接")

        if self.translator_en_to_zh:
            await self.translator_en_to_zh.connect()
            await self.translator_en_to_zh.start_session()
            ch2_log.info("火山引擎已连接")

        # 5. 打印启动信息
        sys_log.info("=" * 60)
        sys_log.info("双向翻译器已启动")
        sys_log.info("=" * 60)
        if self.translator_zh_to_en:
            ch1_log.info("请开始说中文... 翻译后英文输出到 VB-CABLE")
        else:
            ch1_log.info("已关闭（仅字幕模式）")
        if self.translator_en_to_zh:
            ch2_log.info("对方英文语音将翻译为中文字幕")
        sys_log.info("按 Ctrl+C 停止并查看统计")

        # 6. 启动主循环
        await self._main_loop()

    async def _main_loop(self):
        """
        主循环 - 双通道并发执行

        关键: 两个通道完全独立，无需冲突检测!
        """

        async def channel1_loop():
            """Channel 1: 麦克风 → 英文语音"""
            ch1_log.info("通道已启动: 中文 → 英文")

            async def send_audio():
                """发送音频循环"""
                loop = asyncio.get_running_loop()
                while self.is_running:
                    chunk = await loop.run_in_executor(None, self.mic_capturer.get_chunk, 0.1)

                    if chunk:
                        await self.translator_zh_to_en.send_audio(chunk)
                        self.stats['ch1_audio_chunks'] += 1

            async def receive_result():
                """接收结果循环"""
                while self.is_running:
                    try:
                        result = await asyncio.wait_for(
                            self.translator_zh_to_en.receive_result(),
                            timeout=1.0
                        )

                        if result:
                            # 记录首次音频时间
                            if result.audio_data and not self.stats['first_ch1_audio_time']:
                                self.stats['first_ch1_audio_time'] = time.time()
                                first_delay = self.stats['first_ch1_audio_time'] - self.stats['start_time']
                                ch1_log.info("首次音频延迟: %.2f秒", first_delay)

                            # 处理文本
                            if result.text:
                                self.stats['ch1_text_segments'] += 1
                                ch1_log.debug("← text #%d %r", self.stats['ch1_text_segments'], result.text)

                                if self.stats['ch1_text_segments'] % 20 == 0:
                                    ch1_log.info("进度: 已接收 %d 条文本", self.stats['ch1_text_segments'])

                            # 处理音频
                            if result.audio_data:
                                self.stats['ch1_audio_received'] += 1
                                self.stats['total_ch1_audio_bytes'] += len(result.audio_data)

                                ch1_log.debug("← audio #%d %dB", self.stats['ch1_audio_received'], len(result.audio_data))

                                if self.stats['ch1_audio_received'] % 50 == 0:
                                    mb = self.stats['total_ch1_audio_bytes'] / 1024 / 1024
                                    ch1_log.info("音频进度: %d 块, %.2fMB", self.stats['ch1_audio_received'], mb)

                                # 播放音频到 VB-CABLE
                                self.audio_player.play(result.audio_data)

                    except asyncio.TimeoutError:
                        pass
                    except Exception as e:
                        ch1_log.error("接收错误: %s", e)

            await asyncio.gather(send_audio(), receive_result())

        async def channel1_diagnostics_loop():
            """定期输出 CH1 诊断快照，辅助判断是上游稀疏还是输出侧断流。"""
            while self.is_running:
                try:
                    await asyncio.sleep(5.0)

                    if not self.translator_zh_to_en or not self.audio_player:
                        continue

                    translator_snapshot = None
                    if hasattr(self.translator_zh_to_en, "get_debug_snapshot"):
                        translator_snapshot = self.translator_zh_to_en.get_debug_snapshot()

                    player_snapshot = None
                    if hasattr(self.audio_player, "get_debug_snapshot"):
                        player_snapshot = self.audio_player.get_debug_snapshot()

                    if translator_snapshot:
                        ch1_log.info(
                            "CH1上游诊断: 音频包=%s 累计=%sB 估算音频=%.2fs 最近包=%sB seq=%s 间隔=%sms",
                            translator_snapshot["audio_packet_count"],
                            translator_snapshot["audio_bytes_total"],
                            translator_snapshot["estimated_audio_seconds"],
                            translator_snapshot["last_audio_size"],
                            translator_snapshot["last_audio_sequence"],
                            translator_snapshot["last_audio_delta_ms"],
                        )

                    if player_snapshot:
                        ch1_log.info(
                            "CH1播放诊断: state=%s 缓冲=%.1fms 样本=%s 输入包=%s 输入=%sB 已写=%.2fs 已播=%.2fs underflow=%s rebuffer=%s dropped=%s 静音回调=%s",
                            player_snapshot["state"],
                            player_snapshot["buffered_ms"],
                            player_snapshot["buffered_samples"],
                            player_snapshot["packet_count"],
                            player_snapshot["input_bytes_total"],
                            player_snapshot["written_seconds"],
                            player_snapshot["played_seconds"],
                            player_snapshot["underflow_total"],
                            player_snapshot["rebuffer_count"],
                            player_snapshot["dropped_samples"],
                            player_snapshot["silence_callback_count"],
                        )
                except Exception as e:
                    ch1_log.warning("CH1诊断循环错误: %s", e)

        async def channel2_loop():
            """Channel 2: 系统音频 → 中文字幕"""
            ch2_log.info("通道已启动: 英文 → 中文")

            async def send_audio():
                """发送音频循环"""
                loop = asyncio.get_running_loop()
                while self.is_running:
                    chunk = await loop.run_in_executor(None, self.system_audio_capturer.get_chunk, 0.1)

                    if chunk:
                        await self.translator_en_to_zh.send_audio(chunk)
                        self.stats['ch2_audio_chunks'] += 1

            async def receive_result():
                """接收结果循环"""
                while self.is_running:
                    try:
                        result = await asyncio.wait_for(
                            self.translator_en_to_zh.receive_result(),
                            timeout=1.0
                        )

                        if result:
                            # 记录首次文本时间
                            if (
                                result.text
                                and result.event in CH2_SUBTITLE_EVENTS
                                and not self.stats['first_ch2_text_time']
                            ):
                                self.stats['first_ch2_text_time'] = time.time()
                                first_delay = self.stats['first_ch2_text_time'] - self.stats['start_time']
                                ch2_log.info("首次文本延迟: %.2f秒", first_delay)

                            # 仅处理字幕生命周期事件，避免把其他文本事件误当成 CH2 字幕
                            if result.event in CH2_SUBTITLE_EVENTS:
                                self.stats['ch2_text_segments'] += 1
                                ch2_log.debug(
                                    "← 字幕事件 #%d event=%s text=%r",
                                    self.stats['ch2_text_segments'],
                                    result.event,
                                    result.text,
                                )

                                if self.stats['ch2_text_segments'] % 20 == 0:
                                    ch2_log.info("进度: 已接收 %d 条字幕", self.stats['ch2_text_segments'])

                                self._handle_ch2_subtitle_result(result)

                    except asyncio.TimeoutError:
                        self._flush_stale_ch2_sentence(timeout_seconds=3.0)
                    except Exception as e:
                        ch2_log.error("接收错误: %s", e)

            await asyncio.gather(send_audio(), receive_result())

        async def ui_event_loop():
            """UI 事件处理循环 (处理字幕窗口事件)"""
            while self.is_running:
                try:
                    self.subtitle_window_thread.process_events()
                    await asyncio.sleep(0.05)  # 20fps 足够流畅
                except Exception as e:
                    sys_log.warning("UI 事件处理错误: %s", e)

        # 并发执行
        try:
            tasks = []

            # UI 事件循环仅在 CLI 模式（有 Tkinter 字幕窗口）时启动
            if self.subtitle_window_thread:
                tasks.append(ui_event_loop())

            if self.translator_zh_to_en:
                tasks.append(channel1_loop())
                tasks.append(channel1_diagnostics_loop())

            if self.translator_en_to_zh:
                tasks.append(channel2_loop())

            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            sys_log.info("主循环被取消")

    async def stop(self):
        """停止双通道翻译器"""

        sys_log.info("正在停止翻译器...")

        self.is_running = False

        # 停止音频捕获
        if self.mic_capturer:
            self.mic_capturer.stop()
        self.system_audio_capturer.stop()

        # 停止前尽量补发剩余字幕，避免最后一句丢失
        self._finish_ch2_sentence()

        # 关闭翻译客户端
        if self.translator_zh_to_en:
            await self.translator_zh_to_en.close()

        if self.translator_en_to_zh:
            await self.translator_en_to_zh.close()

        # 停止音频播放器
        if self.audio_player:
            self.audio_player.stop()

        # 关闭字幕窗口
        if self.subtitle_window_thread:
            self.subtitle_window_thread.stop()

        # 打印统计
        self._print_stats()

        sys_log.info("翻译器已停止")

    def _print_stats(self):
        """打印统计信息"""

        total_time = time.time() - self.stats['start_time']

        sys_log.info("=" * 60)
        sys_log.info("会话统计 | 总时长: %.2f秒", total_time)
        ch1_log.info("发送: %d 块 | 文本: %d 段 | 音频: %d 块 %.2fKB",
                     self.stats['ch1_audio_chunks'],
                     self.stats['ch1_text_segments'],
                     self.stats['ch1_audio_received'],
                     self.stats['total_ch1_audio_bytes'] / 1024)

        if self.stats['first_ch1_audio_time']:
            first_delay = self.stats['first_ch1_audio_time'] - self.stats['start_time']
            ch1_log.info("首次响应: %.2f秒", first_delay)

        ch2_log.info("发送: %d 块 | 字幕: %d 段",
                     self.stats['ch2_audio_chunks'],
                     self.stats['ch2_text_segments'])

        if self.stats['first_ch2_text_time']:
            first_delay = self.stats['first_ch2_text_time'] - self.stats['start_time']
            ch2_log.info("首次响应: %.2f秒", first_delay)

        sys_log.info("=" * 60)


async def main():
    """主函数"""

    # 检查命令行参数
    config_file = "config.yaml"
    if len(sys.argv) > 1:
        config_file = sys.argv[1]
        sys_log.info("使用配置文件: %s", config_file)

    translator = DualChannelTranslator(config_path=config_file)

    # 信号处理器
    def signal_handler(signum, frame):
        """处理 SIGINT 信号 (Ctrl+C)"""
        sys_log.info("接收到中断信号，正在停止...")
        translator.is_running = False

    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)

    try:
        await translator.start()
    except KeyboardInterrupt:
        sys_log.info("捕获到 KeyboardInterrupt")
    except Exception as e:
        sys_log.error("错误: %s", e, exc_info=True)
    finally:
        sys_log.info("执行清理...")
        await translator.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys_log.info("程序已终止")
    except Exception as e:
        sys_log.error("致命错误: %s", e, exc_info=True)
