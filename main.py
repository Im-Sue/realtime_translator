"""
实时同声传译器 - 主程序
麦克风(中文) → 火山引擎 → VB-CABLE Input(给Zoom) + 扬声器监听(可选)

功能:
- 中文语音实时翻译为英文语音
- 支持VB-CABLE虚拟麦克风输出(Zoom集成)
- 可选本地监听输出(调试模式)
- 优雅的资源管理和错误处理
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
from core.volcengine_client import VolcengineTranslator, VolcengineConfig

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('realtime_translator.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class RealtimeTranslator:
    """实时同声传译器"""

    def __init__(self, config_path: str = "config.yaml", enable_monitor: bool = True):
        """
        初始化翻译器

        Args:
            config_path: 配置文件路径
            enable_monitor: 是否启用本地监听输出(调试用)
        """

        logger.info("=" * 80)
        logger.info("🎙️  实时同声传译器")
        logger.info("   中文(麦克风) → 英文(VB-CABLE Input → Zoom)")
        if enable_monitor:
            logger.info("   调试模式: 同时本地监听输出")
        logger.info("=" * 80)

        # 加载配置
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)

        self.enable_monitor = enable_monitor
        self.is_running = False
        self.stats = {
            'audio_chunks_received': 0,
            'text_segments_received': 0,
            'start_time': None,
            'first_audio_time': None,
            'total_audio_bytes': 0
        }

        # 初始化组件
        self._init_components()

    def _init_components(self):
        """初始化音频和翻译组件"""

        logger.info("🚀 正在初始化组件...")

        # 1. 麦克风捕获
        audio_config = self.config['audio']
        self.mic_capturer = AudioCapturer(
            device_name=audio_config['microphone_device'],
            sample_rate=16000,
            channels=1,
            chunk_size=1600  # 100ms @ 16kHz
        )

        # 2. 查找VB-CABLE Input设备(如果已安装)
        devices = sd.query_devices()
        cable_input_idx = None
        for i, device in enumerate(devices):
            if 'CABLE Input' in device['name'] and device['max_output_channels'] > 0:
                cable_input_idx = i
                logger.info(f"✅ 找到VB-CABLE Input: [{i}] {device['name']}")
                break

        if cable_input_idx is None:
            logger.warning("⚠️  未找到VB-CABLE Input设备!")
            logger.warning("   将使用默认扬声器作为主输出(测试模式)")
            logger.warning("   如需Zoom集成,请安装VB-CABLE: https://vb-audio.com/Cable/")
            # 使用默认扬声器
            cable_input_idx = sd.default.device[1]

        cable_input_device = devices[cable_input_idx]['name']
        logger.info(f"🔊 主输出设备: {cable_input_device}")

        # 3. 创建音频播放器
        # 如果主输出是VB-CABLE,监听输出到扬声器
        # 如果主输出是扬声器(测试模式),禁用监听
        has_vbcable = ('CABLE' in cable_input_device)

        if has_vbcable and self.enable_monitor:
            # VB-CABLE模式 + 监听
            default_output_idx = sd.default.device[1]
            default_output_device = sd.query_devices(default_output_idx)['name']
            logger.info(f"🔊 监听设备: {default_output_device}")

            self.audio_player = OggOpusPlayer(
                device_name=cable_input_device,
                sample_rate=24000,
                use_ffmpeg=True,
                monitor_device=default_output_device,
                enable_monitor=True
            )
        else:
            # 单输出模式 (测试模式或禁用监听)
            logger.info(f"📢 单输出模式")
            self.audio_player = OggOpusPlayer(
                device_name=cable_input_device,
                sample_rate=24000,
                use_ffmpeg=True,
                monitor_device=None,
                enable_monitor=False
            )

        # 4. 火山引擎翻译客户端
        volcengine_cfg = VolcengineConfig(
            ws_url=self.config['volcengine']['ws_url'],
            app_key=self.config['volcengine']['app_key'],
            access_key=self.config['volcengine']['access_key'],
            resource_id=self.config['volcengine'].get('resource_id', 'volc.service_type.10053')
        )

        self.translator = VolcengineTranslator(
            config=volcengine_cfg,
            mode='s2s',
            source_language='zh',
            target_language='en'
        )

        logger.info("✅ 组件初始化完成")

    async def start(self):
        """启动翻译器"""

        self.is_running = True
        self.stats['start_time'] = time.time()

        # 1. 启动音频播放器
        self.audio_player.start()

        # 2. 连接火山引擎并启动会话
        await self.translator.connect()
        await self.translator.start_session()

        # 3. 启动麦克风捕获
        self.mic_capturer.start()

        logger.info("=" * 80)
        logger.info("✅ 翻译器已启动")
        logger.info("   🎤 请开始说中文...")
        logger.info("   🔊 翻译后的英文将输出到 VB-CABLE Input")
        logger.info("   📱 请在Zoom中选择: CABLE Output (VB-Audio Virtual Cable)")
        if self.enable_monitor:
            logger.info("   🔊 本地监听: 同时从扬声器播放")
        logger.info("   ⌨️  按 Ctrl+C 停止并查看统计")
        logger.info("=" * 80)

        # 主循环
        await self._main_loop()

    async def _main_loop(self):
        """主循环"""

        async def send_audio_loop():
            """发送音频循环"""
            logger.info("📤 音频发送线程已启动")

            try:
                while self.is_running:
                    audio_chunk = self.mic_capturer.get_chunk(timeout=0.1)

                    if audio_chunk:
                        await self.translator.send_audio(audio_chunk)

                    await asyncio.sleep(0.01)
            except asyncio.CancelledError:
                logger.info("📤 音频发送循环被取消")
                raise

        async def receive_result_loop():
            """接收结果循环"""
            logger.info("📥 结果接收线程已启动")

            try:
                while self.is_running:
                    try:
                        result = await asyncio.wait_for(
                            self.translator.receive_result(),
                            timeout=1.0
                        )

                        if result:
                            # 记录第一次收到音频的时间
                            if result.audio_data and not self.stats['first_audio_time']:
                                self.stats['first_audio_time'] = time.time()
                                first_delay = self.stats['first_audio_time'] - self.stats['start_time']
                                logger.info(f"⏱️  首次音频延迟: {first_delay:.2f}秒")

                            # 处理文本
                            if result.text:
                                self.stats['text_segments_received'] += 1
                                logger.info(f"📝 [{self.stats['text_segments_received']}] {result.text}")

                            # 处理音频
                            if result.audio_data:
                                self.stats['audio_chunks_received'] += 1
                                self.stats['total_audio_bytes'] += len(result.audio_data)

                                current_time = time.time()
                                current_delay = current_time - self.stats['start_time']

                                logger.info(
                                    f"🔊 音频块 [{self.stats['audio_chunks_received']}] "
                                    f"{len(result.audio_data)} bytes | "
                                    f"延迟: {current_delay:.2f}s"
                                )

                                # 播放音频(会同时输出到VB-CABLE和扬声器)
                                self.audio_player.play(result.audio_data)

                    except asyncio.TimeoutError:
                        pass
                    except Exception as e:
                        logger.error(f"❌ 接收错误: {e}")

            except asyncio.CancelledError:
                logger.info("📥 结果接收循环被取消")
                raise

        # 并发执行,捕获取消异常
        try:
            await asyncio.gather(
                send_audio_loop(),
                receive_result_loop()
            )
        except asyncio.CancelledError:
            logger.info("🛑 主循环被取消")
            # 不重新抛出,正常退出

    async def stop(self):
        """停止翻译器"""

        logger.info("\n🛑 正在停止翻译器...")

        self.is_running = False

        # 停止麦克风
        self.mic_capturer.stop()

        # 关闭翻译会话
        await self.translator.close()

        # 停止音频播放器
        self.audio_player.stop()

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
        logger.info(f"📝 文本片段: {self.stats['text_segments_received']}")
        logger.info(f"🔊 音频块数: {self.stats['audio_chunks_received']}")
        logger.info(f"📦 总音频量: {self.stats['total_audio_bytes'] / 1024:.2f} KB")

        if self.stats['first_audio_time']:
            first_delay = self.stats['first_audio_time'] - self.stats['start_time']
            logger.info(f"⏳ 首次响应: {first_delay:.2f}秒")

        if self.stats['audio_chunks_received'] > 0:
            avg_chunk_size = self.stats['total_audio_bytes'] / self.stats['audio_chunks_received']
            logger.info(f"📊 平均音频块: {avg_chunk_size:.0f} bytes")

        logger.info("=" * 80)


async def main():
    """主函数"""

    # 检查命令行参数
    enable_monitor = True
    if len(sys.argv) > 1 and sys.argv[1] == '--no-monitor':
        enable_monitor = False
        logger.info("📢 监听输出已禁用")

    translator = RealtimeTranslator(enable_monitor=enable_monitor)

    # 信号处理器
    def signal_handler(signum, frame):
        """处理SIGINT信号(Ctrl+C)"""
        logger.info("\n⌨️  接收到中断信号,正在停止...")
        translator.is_running = False  # 先设置标志位

    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)

    try:
        await translator.start()
    except KeyboardInterrupt:
        logger.info("\n⌨️  捕获到KeyboardInterrupt")
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
        # asyncio.run可能会在这里捕获异常
        logger.info("\n⌨️  程序已终止")
    except Exception as e:
        logger.error(f"\n❌ 致命错误: {e}", exc_info=True)
