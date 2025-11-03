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

    def __init__(self, config_path: str = "config_v2.yaml"):
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

        # 初始化组件
        self._init_components()

    def _init_components(self):
        """初始化所有组件"""

        logger.info("🚀 正在初始化组件...")

        # 1. 麦克风捕获 (Channel 1 输入)
        logger.info("\n📍 初始化 Channel 1 输入...")
        audio_config = self.config['audio']

        self.mic_capturer = AudioCapturer(
            device_name=audio_config['microphone']['device'],
            sample_rate=16000,
            channels=1,
            chunk_size=1600  # 100ms @ 16kHz
        )
        logger.info("✅ 麦克风捕获器已初始化")

        # 2. 系统音频捕获 (Channel 2 输入)
        logger.info("\n📍 初始化 Channel 2 输入...")
        system_audio_config = audio_config['system_audio']

        self.system_audio_capturer = SystemAudioCapturer(
            device_name=system_audio_config['device'],
            fallback_device=system_audio_config['fallback_device'],
            sample_rate=16000,
            channels=1,
            chunk_size=1600
        )
        logger.info("✅ 系统音频捕获器已初始化")

        # 3. 音频播放器 (Channel 1 输出 → VB-CABLE)
        logger.info("\n📍 初始化 Channel 1 输出...")

        # 查找 VB-CABLE Input 设备
        devices = sd.query_devices()
        cable_input_idx = None
        for i, device in enumerate(devices):
            if 'CABLE Input' in device['name'] and device['max_output_channels'] > 0:
                cable_input_idx = i
                logger.info(f"✅ 找到 VB-CABLE Input: [{i}] {device['name']}")
                break

        if cable_input_idx is None:
            logger.warning("⚠️  未找到 VB-CABLE Input 设备!")
            logger.warning("   将使用默认扬声器作为输出(测试模式)")
            logger.warning("   如需 Zoom 集成，请安装 VB-CABLE: https://vb-audio.com/Cable/")
            cable_input_idx = sd.default.device[1]

        cable_input_device = devices[cable_input_idx]['name']
        logger.info(f"🔊 Channel 1 输出设备: {cable_input_device}")

        vbcable_config = audio_config['vbcable_output']
        self.audio_player = OggOpusPlayer(
            device_name=cable_input_device,
            sample_rate=24000,
            use_ffmpeg=vbcable_config.get('use_ffmpeg', True),
            monitor_device=None,  # 耳机模式不需要监听
            enable_monitor=False
        )
        logger.info("✅ 音频播放器已初始化")

        # 4. 字幕窗口 (Channel 2 输出)
        logger.info("\n📍 初始化 Channel 2 输出...")
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
        logger.info("✅ 字幕窗口已初始化")

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

        if ch1_config.get('enabled', True):
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

        if ch2_config.get('enabled', True):
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
        self.mic_capturer.start()
        self.system_audio_capturer.start()

        # 2. 启动音频播放器
        logger.info("🚀 启动音频播放器...")
        self.audio_player.start()

        # 3. 启动字幕窗口 (非阻塞)
        logger.info("🚀 启动字幕窗口...")
        self.subtitle_window_thread.start()

        # 4. 连接火山引擎
        logger.info("🚀 连接火山引擎...")

        if self.translator_zh_to_en:
            await self.translator_zh_to_en.connect()
            await self.translator_zh_to_en.start_session()
            logger.info("✅ Channel 1 已连接")

        if self.translator_en_to_zh:
            await self.translator_en_to_zh.connect()
            await self.translator_en_to_zh.start_session()
            logger.info("✅ Channel 2 已连接")

        # 5. 打印启动信息
        logger.info("\n" + "=" * 80)
        logger.info("✅ 双向翻译器已启动")
        logger.info("=" * 80)
        logger.info("📤 Channel 1: 请开始说中文...")
        logger.info("   🔊 翻译后的英文将输出到 VB-CABLE Input")
        logger.info("   📱 请在 Zoom 中选择: CABLE Output (VB-Audio Virtual Cable)")
        logger.info("")
        logger.info("📥 Channel 2: 对方的英文语音将翻译为中文字幕")
        logger.info("   📺 请查看屏幕右上角的字幕窗口")
        logger.info("   🎧 请务必使用耳机，避免音频回声!")
        logger.info("")
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

                                # 更新字幕窗口
                                self.subtitle_window_thread.update_subtitle(result.text)

                    except asyncio.TimeoutError:
                        pass
                    except Exception as e:
                        logger.error(f"❌ Channel 2 接收错误: {e}")

            await asyncio.gather(send_audio(), receive_result())

        async def ui_event_loop():
            """UI 事件处理循环 (处理字幕窗口事件)"""
            while self.is_running:
                try:
                    self.subtitle_window_thread.process_events()
                    await asyncio.sleep(0.05)  # 20fps 足够流畅
                except Exception as e:
                    logger.warning(f"⚠️  UI 事件处理错误: {e}")

        # 并发执行三个循环
        try:
            tasks = [ui_event_loop()]

            if self.translator_zh_to_en:
                tasks.append(channel1_loop())

            if self.translator_en_to_zh:
                tasks.append(channel2_loop())

            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("🛑 主循环被取消")

    async def stop(self):
        """停止双通道翻译器"""

        logger.info("\n🛑 正在停止翻译器...")

        self.is_running = False

        # 停止音频捕获
        self.mic_capturer.stop()
        self.system_audio_capturer.stop()

        # 关闭翻译客户端
        if self.translator_zh_to_en:
            await self.translator_zh_to_en.close()

        if self.translator_en_to_zh:
            await self.translator_en_to_zh.close()

        # 停止音频播放器
        self.audio_player.stop()

        # 关闭字幕窗口
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
    config_file = "config_v2.yaml"
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
