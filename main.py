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
import sounddevice as sd
import time
import sys
import signal
import re
from pathlib import Path
from core.audio_capture import AudioCapturer
from core.audio_output import OggOpusPlayer
from core.system_audio_capture import SystemAudioCapturer
from core.volcengine_client import VolcengineTranslator, VolcengineConfig
from gui.subtitle_window import SubtitleWindow, SubtitleWindowThread

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('realtime_translator_v2.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class DualChannelTranslator:
    """
    双通道实时翻译器 (耳机模式)

    Channel 1: 麦克风(中文) → VB-CABLE(英文) [s2s]
    Channel 2: 系统音频(英文) → 字幕窗口(中文) [s2t]
    """

    def __init__(self, config_path: str = "config.yaml"):
        """
        初始化双通道翻译器

        Args:
            config_path: 配置文件路径
        """

        logger.info("=" * 80)
        logger.info("🎙️  实时同声传译器 v2.0 (双向翻译 - 耳机模式)")
        logger.info("=" * 80)
        logger.info("📤 Channel 1: 你说中文 → 对方听英文")
        logger.info("📥 Channel 2: 对方说英文 → 你看中文字幕")
        logger.info("🎧 重要: 请使用耳机，避免音频回声!")
        logger.info("=" * 80)

        # 加载配置
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
            logger.info(f"✅ 配置文件加载成功: {config_path}")
        except FileNotFoundError:
            logger.error(f"❌ 配置文件未找到: {config_path}")
            logger.error("   请从 config.yaml 复制一份并重命名为 config_v2.yaml")
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

        # Channel 2 字幕聚合（避免逐词刷屏 + 中英分区显示）
        self.ch2_zh_buffer = ""
        self.ch2_en_buffer = ""
        self.ch2_last_update_time = 0.0

        # 初始化组件
        self._init_components()

    def _channel1_ready(self) -> bool:
        """Channel 1 运行前置条件是否满足"""
        return bool(
            self.channel1_enabled and
            self.mic_capturer and
            self.audio_player and
            self.translator_zh_to_en
        )

    def _channel2_ready(self) -> bool:
        """Channel 2 运行前置条件是否满足"""
        return bool(
            self.channel2_enabled and
            self.system_audio_capturer and
            self.translator_en_to_zh and
            self.subtitle_window_thread
        )

    async def _disable_channel1(self, reason: str):
        """关闭 Channel 1 并清理资源"""
        if not self.channel1_enabled and not self.mic_capturer and not self.audio_player and not self.translator_zh_to_en:
            return

        logger.warning(f"⚠️  Channel 1 已降级关闭: {reason}")
        self.channel1_enabled = False

        if self.mic_capturer:
            try:
                self.mic_capturer.stop()
            except Exception as e:
                logger.warning(f"⚠️  停止 Channel 1 麦克风失败: {e}")
            self.mic_capturer = None

        if self.audio_player:
            try:
                self.audio_player.stop()
            except Exception as e:
                logger.warning(f"⚠️  停止 Channel 1 音频播放器失败: {e}")
            self.audio_player = None

        if self.translator_zh_to_en:
            try:
                await self.translator_zh_to_en.close()
            except Exception as e:
                logger.warning(f"⚠️  关闭 Channel 1 翻译器失败: {e}")
            self.translator_zh_to_en = None

    async def _disable_channel2(self, reason: str):
        """关闭 Channel 2 并清理资源"""
        if not self.channel2_enabled and not self.system_audio_capturer and not self.translator_en_to_zh and not self.subtitle_window_thread:
            return

        logger.warning(f"⚠️  Channel 2 已降级关闭: {reason}")
        self.channel2_enabled = False

        if self.system_audio_capturer:
            try:
                self.system_audio_capturer.stop()
            except Exception as e:
                logger.warning(f"⚠️  停止 Channel 2 系统音频捕获失败: {e}")
            self.system_audio_capturer = None

        self.ch2_en_buffer = ""
        self.ch2_zh_buffer = ""
        self.ch2_last_update_time = 0.0

        if self.translator_en_to_zh:
            try:
                await self.translator_en_to_zh.close()
            except Exception as e:
                logger.warning(f"⚠️  关闭 Channel 2 翻译器失败: {e}")
            self.translator_en_to_zh = None

        if self.subtitle_window_thread:
            try:
                self.subtitle_window_thread.stop()
            except Exception as e:
                logger.warning(f"⚠️  停止字幕窗口失败: {e}")
            self.subtitle_window_thread = None
            self.subtitle_window = None

    def _is_mostly_english(self, text: str) -> bool:
        if not text:
            return False
        latin = sum(1 for c in text if c.isalpha() and ord(c) < 128)
        chinese = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        total = latin + chinese
        if total == 0:
            return False
        return (latin / total) > 0.55

    def _is_near_duplicate_en(self, old: str, frag: str) -> bool:
        """英文片段近重复检测（处理实时转写常见重复）"""
        if not old or not frag:
            return False

        o = old.strip().lower()
        f = frag.strip().lower()
        if not o or not f:
            return False

        # 完全相同/包含
        if o == f or f in o or o in f:
            return True

        # 词级别前后缀重叠（例如 "I think" + "I think we should"）
        o_words = o.split()
        f_words = f.split()
        if len(o_words) >= 3 and len(f_words) >= 3:
            suffix = " ".join(o_words[-4:])
            prefix = " ".join(f_words[:4])
            if suffix == prefix:
                return True

        # 高重叠短句也视为重复
        if len(f_words) <= 8:
            common = set(o_words) & set(f_words)
            if f_words and len(common) / max(1, len(set(f_words))) >= 0.8:
                return True

        return False

    def _append_dedup(self, old: str, frag: str) -> str:
        """将片段追加到缓冲区并做去重"""
        if not old:
            return frag

        is_en = self._is_mostly_english(old) or self._is_mostly_english(frag)

        # 英文更严格去重（防止重复句）
        if is_en and self._is_near_duplicate_en(old, frag):
            return old if len(old) >= len(frag) else frag

        # 通用包含关系去重
        if frag in old:
            return old
        if old in frag:
            return frag

        sep = " " if is_en else ""
        merged = (old + sep + frag).strip()

        # 合并后去掉连续重复词（英文）
        if is_en:
            words = merged.split()
            compact = []
            for w in words:
                if compact and compact[-1].lower() == w.lower():
                    continue
                compact.append(w)
            merged = " ".join(compact)

        return merged

    def _append_ch2_fragment(self, fragment: str):
        """聚合 Channel 2 文本片段，中文和英文严格分区展示"""
        if not fragment:
            return

        frag = re.sub(r"\s+", " ", fragment.strip())
        if not frag:
            return

        self.ch2_last_update_time = time.time()

        if self._is_mostly_english(frag):
            self.ch2_en_buffer = self._append_dedup(self.ch2_en_buffer, frag)
        else:
            self.ch2_zh_buffer = self._append_dedup(self.ch2_zh_buffer, frag)

        # 句子边界：优先中文句末标点；英文句末也触发
        if re.search(r"[。！？!?]$", frag):
            self._flush_ch2_buffer()

    def _flush_ch2_buffer(self, force: bool = False):
        """输出 Channel 2 聚合文本（EN/ZH 分区）"""
        if not self.subtitle_window_thread:
            return

        en = self.ch2_en_buffer.strip()
        zh = self.ch2_zh_buffer.strip()

        if not en and not zh:
            return

        # 非强制时，过短片段不输出，避免单词刷屏
        longest = max(len(en), len(zh))
        has_sentence_end = bool(re.search(r"[。！？!?]$", en) or re.search(r"[。！？!?]$", zh))
        if not force and longest < 12 and not has_sentence_end:
            return

        parts = []
        if en:
            parts.append(f"EN  {en}")
        if zh:
            parts.append(f"ZH  {zh}")

        self.subtitle_window_thread.update_subtitle("\n".join(parts))
        self.ch2_en_buffer = ""
        self.ch2_zh_buffer = ""
        self.ch2_last_update_time = 0.0

    def _init_components(self):
        """初始化所有组件"""

        logger.info("🚀 正在初始化组件...")

        # 1. 麦克风捕获 (Channel 1 输入)
        logger.info("\n📍 初始化 Channel 1 输入...")
        audio_config = self.config['audio']

        self.mic_capturer = None
        if self.channel1_enabled:
            self.mic_capturer = AudioCapturer(
                device_name=audio_config['microphone']['device'],
                sample_rate=16000,
                channels=1,
                chunk_size=1600  # 100ms @ 16kHz
            )
            logger.info("✅ 麦克风捕获器已初始化")
        else:
            logger.warning("⚠️  Channel 1 已禁用：跳过麦克风初始化")

        # 2. 系统音频捕获 (Channel 2 输入)
        logger.info("\n📍 初始化 Channel 2 输入...")
        system_audio_config = audio_config['system_audio']

        self.system_audio_capturer = None
        if self.channel2_enabled:
            self.system_audio_capturer = SystemAudioCapturer(
                device_name=system_audio_config['device'],
                fallback_device=system_audio_config['fallback_device'],
                sample_rate=16000,
                channels=1,
                chunk_size=1600
            )
            logger.info("✅ 系统音频捕获器已初始化")
        else:
            logger.warning("⚠️  Channel 2 已禁用：跳过系统音频初始化")

        # 3. 音频播放器 (Channel 1 输出 → VB-CABLE)
        logger.info("\n📍 初始化 Channel 1 输出...")
        self.audio_player = None

        if self.channel1_enabled:
            vbcable_config = audio_config['vbcable_output']

            # 查找 VB-CABLE Input 设备
            devices = sd.query_devices()
            cable_input_idx = None
            config_device_name = vbcable_config.get('device', 'CABLE Input')
            # 搜索关键词: 配置文件中的设备名 + 常见VB-CABLE变体
            cable_keywords = [config_device_name, 'CABLE Input', 'CABLE In']
            for keyword in cable_keywords:
                if cable_input_idx is not None:
                    break
                for i, device in enumerate(devices):
                    if keyword in device['name'] and device['max_output_channels'] > 0:
                        cable_input_idx = i
                        logger.info(f"✅ 找到 VB-CABLE Input: [{i}] {device['name']} (匹配关键词: '{keyword}')")
                        break

            if cable_input_idx is None:
                logger.warning("⚠️  未找到 VB-CABLE Input 设备!")
                logger.warning("   将使用默认扬声器作为输出(测试模式)")
                logger.warning("   如需 Zoom 集成，请安装 VB-CABLE: https://vb-audio.com/Cable/")
                logger.warning(f"   已搜索关键词: {cable_keywords}")
                cable_input_idx = sd.default.device[1]

            cable_input_device = devices[cable_input_idx]['name']
            logger.info(f"🔊 Channel 1 输出设备: {cable_input_device}")

            self.audio_player = OggOpusPlayer(
                device_name=cable_input_device,
                sample_rate=24000,
                use_ffmpeg=vbcable_config.get('use_ffmpeg', True),
                monitor_device=None,  # 耳机模式不需要监听
                enable_monitor=False
            )
            logger.info("✅ 音频播放器已初始化")
        else:
            logger.warning("⚠️  Channel 1 已禁用：跳过音频播放器初始化")

        # 4. 字幕窗口 (Channel 2 输出)
        logger.info("\n📍 初始化 Channel 2 输出...")
        subtitle_config = self.config.get('subtitle_window', {})

        self.subtitle_window = None
        self.subtitle_window_thread = None
        if self.channel2_enabled:
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
            logger.info("✅ 字幕窗口已初始化")
        else:
            logger.warning("⚠️  Channel 2 已禁用：跳过字幕窗口初始化")

        # 5. 火山引擎翻译客户端 (两个独立连接)
        logger.info("\n📍 初始化火山引擎翻译客户端...")

        volcengine_cfg = VolcengineConfig(
            ws_url=self.config['volcengine']['ws_url'],
            app_key=self.config['volcengine']['app_key'],
            access_key=self.config['volcengine']['access_key'],
            resource_id=self.config['volcengine'].get('resource_id', 'volc.service_type.10053')
        )

        # Channel 1: 中文 → 英文 (s2s)
        channels_config = self.config.get('channels', {})
        ch1_config = channels_config.get('zh_to_en', {})

        if self.channel1_enabled:
            self.translator_zh_to_en = VolcengineTranslator(
                config=volcengine_cfg,
                mode=ch1_config.get('mode', 's2s'),
                source_language=ch1_config.get('source_language', 'zh'),
                target_language=ch1_config.get('target_language', 'en')
            )
            logger.info("✅ Channel 1 翻译器: 中文 → 英文 (s2s)")
        else:
            self.translator_zh_to_en = None
            logger.warning("⚠️  Channel 1 已禁用")

        # Channel 2: 英文 → 中文 (s2t)
        ch2_config = channels_config.get('en_to_zh', {})

        if self.channel2_enabled:
            self.translator_en_to_zh = VolcengineTranslator(
                config=volcengine_cfg,
                mode=ch2_config.get('mode', 's2t'),  # speech to text!
                source_language=ch2_config.get('source_language', 'en'),
                target_language=ch2_config.get('target_language', 'zh')
            )
            logger.info("✅ Channel 2 翻译器: 英文 → 中文 (s2t)")
        else:
            self.translator_en_to_zh = None
            logger.warning("⚠️  Channel 2 已禁用")

        logger.info("\n✅ 所有组件初始化完成")

    async def start(self):
        """启动双通道翻译器"""

        self.is_running = True
        self.stats['start_time'] = time.time()

        # 1. 启动音频捕获
        logger.info("\n🚀 启动音频捕获...")
        if self.mic_capturer:
            try:
                self.mic_capturer.start()
            except Exception as e:
                await self._disable_channel1(f"麦克风启动失败: {e}")

        if self.system_audio_capturer:
            try:
                self.system_audio_capturer.start()
            except Exception as e:
                await self._disable_channel2(f"系统音频捕获启动失败: {e}")

        # 2. 启动音频播放器
        if self.audio_player:
            logger.info("🚀 启动音频播放器...")
            try:
                self.audio_player.start()
            except Exception as e:
                await self._disable_channel1(f"音频播放器启动失败: {e}")
        else:
            logger.info("🚀 Channel 1 音频输出已关闭（仅字幕模式）")

        # 3. 启动字幕窗口 (非阻塞)
        if self.subtitle_window_thread:
            logger.info("🚀 启动字幕窗口...")
            try:
                self.subtitle_window_thread.start()
            except Exception as e:
                await self._disable_channel2(f"字幕窗口启动失败: {e}")

        # 4. 连接火山引擎
        logger.info("🚀 连接火山引擎...")

        if self.translator_zh_to_en:
            try:
                await self.translator_zh_to_en.connect()
                await self.translator_zh_to_en.start_session()
                logger.info("✅ Channel 1 已连接")
            except Exception as e:
                await self._disable_channel1(f"火山引擎 Channel 1 连接失败: {e}")

        if self.translator_en_to_zh:
            try:
                await self.translator_en_to_zh.connect()
                await self.translator_en_to_zh.start_session()
                logger.info("✅ Channel 2 已连接")
            except Exception as e:
                await self._disable_channel2(f"火山引擎 Channel 2 连接失败: {e}")

        if not self._channel1_ready() and not self._channel2_ready():
            raise RuntimeError("所有通道均不可用，请检查音频设备、FFmpeg 和火山引擎配置")

        # 5. 打印启动信息
        logger.info("\n" + "=" * 80)
        logger.info("✅ 双向翻译器已启动")
        logger.info("=" * 80)
        if self._channel1_ready():
            logger.info("📤 Channel 1: 请开始说中文...")
            logger.info("   🔊 翻译后的英文将输出到 VB-CABLE Input")
            logger.info("   📱 请在 Zoom 中选择: CABLE Output (VB-Audio Virtual Cable)")
        else:
            logger.info("📤 Channel 1: 已关闭（仅字幕模式）")
        logger.info("")
        if self._channel2_ready():
            logger.info("📥 Channel 2: 对方的英文语音将翻译为中文字幕")
            logger.info("   📺 请查看屏幕右上角的字幕窗口")
            logger.info("   🎧 请务必使用耳机，避免音频回声!")
            logger.info("")
        else:
            logger.info("📥 Channel 2: 已关闭")
        logger.info("   ⌨️  按 Ctrl+C 停止并查看统计")
        logger.info("=" * 80 + "\n")

        # 6. 启动主循环
        await self._main_loop()

    async def _main_loop(self):
        """
        主循环 - 双通道并发执行

        关键: 两个通道完全独立，无需冲突检测!
        """

        async def channel1_loop():
            """Channel 1: 麦克风 → 英文语音"""
            logger.info("📤 Channel 1 已启动: 中文 → 英文")

            async def send_audio():
                """发送音频循环"""
                while self.is_running:
                    chunk = self.mic_capturer.get_chunk(timeout=0.1)

                    if chunk:
                        await self.translator_zh_to_en.send_audio(chunk)
                        self.stats['ch1_audio_chunks'] += 1

                    await asyncio.sleep(0.01)

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
                                logger.info(f"⏱️  Channel 1 首次音频延迟: {first_delay:.2f}秒")

                            # 处理文本
                            if result.text:
                                self.stats['ch1_text_segments'] += 1
                                # 详细日志改为DEBUG级别
                                logger.debug(f"📝 [CH1-{self.stats['ch1_text_segments']}] 英文: {result.text}")

                                # 每20条记录一次摘要
                                if self.stats['ch1_text_segments'] % 20 == 0:
                                    logger.info(f"📊 Channel 1 进度: 已接收 {self.stats['ch1_text_segments']} 条文本")

                            # 处理音频
                            if result.audio_data:
                                self.stats['ch1_audio_received'] += 1
                                self.stats['total_ch1_audio_bytes'] += len(result.audio_data)

                                # 详细日志改为DEBUG级别
                                logger.debug(
                                    f"🔊 [CH1] 音频块 [{self.stats['ch1_audio_received']}] "
                                    f"{len(result.audio_data)} bytes"
                                )

                                # 每50个音频块记录一次摘要
                                if self.stats['ch1_audio_received'] % 50 == 0:
                                    mb = self.stats['total_ch1_audio_bytes'] / 1024 / 1024
                                    logger.info(f"📊 Channel 1 音频: 已接收 {self.stats['ch1_audio_received']} 块, 共 {mb:.2f}MB")

                                # 播放音频到 VB-CABLE
                                self.audio_player.play(result.audio_data)

                    except asyncio.TimeoutError:
                        pass
                    except Exception as e:
                        logger.error(f"❌ Channel 1 接收错误: {e}")

            await asyncio.gather(send_audio(), receive_result())

        async def channel2_loop():
            """Channel 2: 系统音频 → 中文字幕"""
            logger.info("📥 Channel 2 已启动: 英文 → 中文")

            async def send_audio():
                """发送音频循环"""
                while self.is_running:
                    chunk = self.system_audio_capturer.get_chunk(timeout=0.1)

                    if chunk:
                        await self.translator_en_to_zh.send_audio(chunk)
                        self.stats['ch2_audio_chunks'] += 1

                    await asyncio.sleep(0.01)

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
                            if result.text and not self.stats['first_ch2_text_time']:
                                self.stats['first_ch2_text_time'] = time.time()
                                first_delay = self.stats['first_ch2_text_time'] - self.stats['start_time']
                                logger.info(f"⏱️  Channel 2 首次文本延迟: {first_delay:.2f}秒")

                            # 处理文本
                            if result.text:
                                self.stats['ch2_text_segments'] += 1
                                # 详细日志改为DEBUG级别
                                logger.debug(f"📝 [CH2-{self.stats['ch2_text_segments']}] 中文: {result.text}")

                                # 每20条记录一次摘要
                                if self.stats['ch2_text_segments'] % 20 == 0:
                                    logger.info(f"📊 Channel 2 进度: 已接收 {self.stats['ch2_text_segments']} 条字幕")

                                # 聚合后再展示（尽量按句子输出）
                                self._append_ch2_fragment(result.text)

                    except asyncio.TimeoutError:
                        # 片段静默超过阈值则强制输出，避免一直不显示
                        if (self.ch2_en_buffer or self.ch2_zh_buffer) and self.ch2_last_update_time:
                            if time.time() - self.ch2_last_update_time > 1.2:
                                self._flush_ch2_buffer(force=True)
                    except Exception as e:
                        logger.error(f"❌ Channel 2 接收错误: {e}")

            await asyncio.gather(send_audio(), receive_result())

        async def ui_event_loop():
            """UI 事件处理循环 (处理字幕窗口事件)"""
            while self.is_running:
                try:
                    if not self.subtitle_window_thread:
                        return
                    self.subtitle_window_thread.process_events()
                    await asyncio.sleep(0.05)  # 20fps 足够流畅
                except Exception as e:
                    logger.warning(f"⚠️  UI 事件处理错误: {e}")

        # 并发执行三个循环
        try:
            tasks = [ui_event_loop()]

            if self._channel1_ready():
                tasks.append(channel1_loop())

            if self._channel2_ready():
                tasks.append(channel2_loop())

            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("🛑 主循环被取消")

    async def stop(self):
        """停止双通道翻译器"""

        logger.info("\n🛑 正在停止翻译器...")

        self.is_running = False

        # 停止音频捕获
        if self.mic_capturer:
            self.mic_capturer.stop()
        if self.system_audio_capturer:
            self.system_audio_capturer.stop()

        # 停止前尽量输出剩余字幕片段
        self._flush_ch2_buffer(force=True)

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

        logger.info("✅ 翻译器已停止")

    def _print_stats(self):
        """打印统计信息"""

        total_time = time.time() - self.stats['start_time']

        logger.info("\n" + "=" * 80)
        logger.info("📊 会话统计")
        logger.info("=" * 80)
        logger.info(f"⏱️  总时长: {total_time:.2f}秒")
        logger.info("")
        logger.info("📤 Channel 1 (中文 → 英文):")
        logger.info(f"   📤 发送音频块: {self.stats['ch1_audio_chunks']}")
        logger.info(f"   📝 接收文本片段: {self.stats['ch1_text_segments']}")
        logger.info(f"   🔊 接收音频块: {self.stats['ch1_audio_received']}")
        logger.info(f"   📦 总音频量: {self.stats['total_ch1_audio_bytes'] / 1024:.2f} KB")

        if self.stats['first_ch1_audio_time']:
            first_delay = self.stats['first_ch1_audio_time'] - self.stats['start_time']
            logger.info(f"   ⏳ 首次响应: {first_delay:.2f}秒")

        logger.info("")
        logger.info("📥 Channel 2 (英文 → 中文):")
        logger.info(f"   📤 发送音频块: {self.stats['ch2_audio_chunks']}")
        logger.info(f"   📝 接收文本片段: {self.stats['ch2_text_segments']}")

        if self.stats['first_ch2_text_time']:
            first_delay = self.stats['first_ch2_text_time'] - self.stats['start_time']
            logger.info(f"   ⏳ 首次响应: {first_delay:.2f}秒")

        logger.info("=" * 80)


async def main():
    """主函数"""

    # 检查命令行参数
    config_file = "config.yaml"
    if len(sys.argv) > 1:
        config_file = sys.argv[1]
        logger.info(f"📝 使用配置文件: {config_file}")

    translator = DualChannelTranslator(config_path=config_file)

    # 信号处理器
    def signal_handler(signum, frame):
        """处理 SIGINT 信号 (Ctrl+C)"""
        logger.info("\n⌨️  接收到中断信号，正在停止...")
        translator.is_running = False

    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)

    try:
        await translator.start()
    except KeyboardInterrupt:
        logger.info("\n⌨️  捕获到 KeyboardInterrupt")
    except Exception as e:
        logger.error(f"\n❌ 错误: {e}", exc_info=True)
    finally:
        # 确保无论如何都会执行清理
        logger.info("🧹 执行清理...")
        await translator.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n⌨️  程序已终止")
    except Exception as e:
        logger.error(f"\n❌ 致命错误: {e}", exc_info=True)
