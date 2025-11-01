"""
系统音频捕获模块
捕获系统播放的音频(立体声混音/CABLE Output)，用于听取对方的英文语音
"""

import sounddevice as sd
import numpy as np
import queue
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class SystemAudioCapturer:
    """
    系统音频捕获器
    捕获来自Zoom的对方英文语音

    支持两种音频源:
    1. 立体声混音 (Stereo Mix) - Windows默认混音设备
    2. CABLE Output - VB-CABLE输出端(降级选项)
    """

    def __init__(self,
                 device_name: str = "立体声混音",
                 fallback_device: str = "CABLE Output",
                 sample_rate: int = 16000,
                 channels: int = 1,
                 chunk_size: int = 1600):
        """
        初始化系统音频捕获器

        Args:
            device_name: 主音频设备名称
            fallback_device: 降级设备名称
            sample_rate: 采样率 (Hz)
            channels: 声道数
            chunk_size: 音频块大小 (样本数)
        """
        self.device_name = device_name
        self.fallback_device = fallback_device
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = chunk_size

        self.device_index = None
        self.stream = None
        self.audio_queue = queue.Queue()
        self.is_running = False

        logger.info(f"🎙️  系统音频捕获器初始化")
        logger.info(f"   主设备: {self.device_name}")
        logger.info(f"   降级设备: {self.fallback_device}")
        logger.info(f"   采样率: {self.sample_rate} Hz")
        logger.info(f"   声道: {self.channels}")
        logger.info(f"   块大小: {self.chunk_size} ({self.chunk_size / self.sample_rate * 1000:.0f}ms)")

    def _test_device(self, device_id: int) -> bool:
        """
        测试设备是否可用

        Args:
            device_id: 设备索引

        Returns:
            True if device is usable, False otherwise
        """
        try:
            # 创建测试流
            test_stream = sd.InputStream(
                device=device_id,
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=np.int16,
                blocksize=self.chunk_size
            )
            test_stream.close()
            return True
        except Exception as e:
            logger.debug(f"   设备 [{device_id}] 测试失败: {e}")
            return False

    def _find_device(self) -> int:
        """
        查找系统音频设备

        Returns:
            设备索引

        Raises:
            RuntimeError: 如果未找到任何可用设备
        """
        logger.info("🔍 正在查找系统音频设备...")

        devices = sd.query_devices()
        logger.debug(f"检测到 {len(devices)} 个音频设备")

        # 1. 尝试找到主设备并验证
        for i, device in enumerate(devices):
            device_name = device['name']
            max_input_channels = device['max_input_channels']

            logger.debug(f"[{i}] {device_name} (输入通道: {max_input_channels})")

            if self.device_name in device_name and max_input_channels > 0:
                logger.info(f"✅ 找到系统音频设备: [{i}] {device_name}")

                # 验证设备可用性
                if self._test_device(i):
                    logger.info(f"✅ 设备验证成功")
                    return i
                else:
                    logger.warning(f"⚠️  设备验证失败,尝试降级设备...")
                    break

        # 2. 尝试降级设备(排除VB-CABLE Output以避免回声)
        logger.warning(f"⚠️  主设备 '{self.device_name}' 不可用，尝试降级设备...")
        logger.warning(f"⚠️  警告: 使用CABLE Output会导致音频回路!")

        # 搜索所有可用的输入设备(排除CABLE Output)
        available_devices = []
        for i, device in enumerate(devices):
            device_name = device['name']
            max_input_channels = device['max_input_channels']

            # 排除VB-CABLE相关设备
            if max_input_channels > 0 and "CABLE" not in device_name.upper():
                if self._test_device(i):
                    available_devices.append((i, device_name))
                    logger.info(f"✅ 找到可用设备: [{i}] {device_name}")

        # 如果找到可用设备,使用第一个
        if available_devices:
            device_id, device_name = available_devices[0]
            logger.info(f"✅ 使用设备: [{device_id}] {device_name}")
            return device_id

        # 如果没有找到任何设备,最后才尝试CABLE Output(并警告)
        logger.error("❌ 未找到非VB-CABLE的音频设备!")
        logger.error("⚠️  将尝试使用CABLE Output,但这会导致音频回路!")

        for i, device in enumerate(devices):
            device_name = device['name']
            max_input_channels = device['max_input_channels']

            if self.fallback_device in device_name and max_input_channels > 0:
                logger.warning(f"🔄 测试降级设备: [{i}] {device_name}")

                if self._test_device(i):
                    logger.warning(f"⚠️  使用降级设备(有回声风险): [{i}] {device_name}")
                    return i

        # 3. 抛出异常
        logger.error("❌ 未找到任何可用的系统音频设备!")
        logger.error(f"   请确保已启用: '{self.device_name}' 或 '{self.fallback_device}'")
        logger.error("")
        logger.error("Windows 配置步骤:")
        logger.error("1. 右键任务栏音量图标 → '声音'")
        logger.error("2. 切换到 '录制' 标签页")
        logger.error("3. 右键空白处 → '显示已禁用的设备'")
        logger.error("4. 找到 '立体声混音' → 右键 → '启用'")
        logger.error("")
        logger.error("或者安装VB-CABLE: https://vb-audio.com/Cable/")

        raise RuntimeError(
            f"未找到系统音频设备!\n"
            f"请确保已启用: {self.device_name} 或 {self.fallback_device}\n"
            f"Windows: 右键音量图标 → 声音 → 录制 → 启用'立体声混音'\n"
            f"或安装VB-CABLE: https://vb-audio.com/Cable/"
        )

    def start(self):
        """启动音频捕获"""
        logger.info("🚀 启动系统音频捕获...")

        # 查找设备
        self.device_index = self._find_device()
        self.is_running = True

        # 音频回调函数
        def audio_callback(indata, frames, time_info, status):
            if status:
                logger.warning(f"⚠️  系统音频状态: {status}")

            # 转换为字节流并放入队列
            audio_bytes = indata.tobytes()
            self.audio_queue.put(audio_bytes)

        # 创建音频流
        try:
            self.stream = sd.InputStream(
                device=self.device_index,
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=np.int16,
                blocksize=self.chunk_size,
                callback=audio_callback
            )

            self.stream.start()
            logger.info("✅ 系统音频捕获已启动")

        except Exception as e:
            logger.error(f"❌ 启动系统音频捕获失败: {e}")
            raise

    def get_chunk(self, timeout: Optional[float] = None) -> Optional[bytes]:
        """
        获取音频块

        Args:
            timeout: 超时时间(秒)，None表示阻塞等待

        Returns:
            音频字节流，如果超时则返回None
        """
        try:
            return self.audio_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def stop(self):
        """停止音频捕获"""
        logger.info("🛑 正在停止系统音频捕获...")

        self.is_running = False

        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
            logger.info("✅ 系统音频捕获已停止")

    def get_stats(self) -> dict:
        """
        获取捕获器统计信息

        Returns:
            统计信息字典
        """
        return {
            'device_index': self.device_index,
            'device_name': self.device_name if self.device_index is not None
                          else sd.query_devices(self.device_index)['name'],
            'sample_rate': self.sample_rate,
            'channels': self.channels,
            'chunk_size': self.chunk_size,
            'queue_size': self.audio_queue.qsize(),
            'is_running': self.is_running
        }

    def __repr__(self):
        return (f"SystemAudioCapturer("
                f"device='{self.device_name}', "
                f"sample_rate={self.sample_rate}, "
                f"channels={self.channels}, "
                f"is_running={self.is_running})")
