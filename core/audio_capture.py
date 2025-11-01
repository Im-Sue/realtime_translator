"""
音频捕获模块
支持从系统音频(立体声混音)和麦克风捕获音频流
"""

import sounddevice as sd
import numpy as np
import queue
import logging
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class AudioCapturer:
    """音频捕获器"""

    def __init__(
        self,
        device_name: str,
        sample_rate: int = 16000,
        channels: int = 1,
        chunk_size: int = 1600,
        callback: Optional[Callable] = None
    ):
        """
        初始化音频捕获器

        Args:
            device_name: 音频设备名称
            sample_rate: 采样率(Hz)
            channels: 声道数
            chunk_size: 每次读取的音频帧数
            callback: 音频数据回调函数
        """
        self.device_name = device_name
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = chunk_size
        self.callback = callback

        self.device_index = None
        self.stream = None
        self.audio_queue = queue.Queue()
        self.is_running = False

        # 查找音频设备
        self._find_device()

    def _find_device(self):
        """查找指定名称的音频设备"""
        try:
            devices = sd.query_devices()
            logger.info(f"可用音频设备列表:")

            for idx, device in enumerate(devices):
                logger.info(f"  [{idx}] {device['name']} - "
                          f"输入:{device['max_input_channels']} "
                          f"输出:{device['max_output_channels']}")

                # 模糊匹配设备名称
                if self.device_name.lower() in device['name'].lower():
                    # 检查是否支持输入
                    if device['max_input_channels'] > 0:
                        self.device_index = idx
                        logger.info(f"✅ 找到音频设备: [{idx}] {device['name']}")
                        return

            if self.device_index is None:
                logger.warning(f"⚠️  未找到设备 '{self.device_name}', 使用默认输入设备")
                self.device_index = sd.default.device[0]  # 默认输入设备

        except Exception as e:
            logger.error(f"❌ 查找音频设备失败: {e}")
            raise

    def _audio_callback(self, indata, frames, time, status):
        """音频流回调函数"""
        if status:
            logger.warning(f"⚠️  音频状态: {status}")

        try:
            # 转换为int16格式的字节流
            audio_data = (indata * 32767).astype(np.int16)
            audio_bytes = audio_data.tobytes()

            # 放入队列
            self.audio_queue.put(audio_bytes)

            # 调用外部回调
            if self.callback:
                self.callback(audio_bytes)

        except Exception as e:
            logger.error(f"❌ 音频回调错误: {e}")

    def start(self):
        """开始捕获音频"""
        if self.is_running:
            logger.warning("⚠️  音频捕获已在运行")
            return

        try:
            self.stream = sd.InputStream(
                device=self.device_index,
                channels=self.channels,
                samplerate=self.sample_rate,
                blocksize=self.chunk_size,
                callback=self._audio_callback
            )

            self.stream.start()
            self.is_running = True

            device_info = sd.query_devices(self.device_index)
            logger.info(f"✅ 音频捕获已启动: {device_info['name']}")
            logger.info(f"   采样率:{self.sample_rate}Hz, 声道:{self.channels}, "
                       f"块大小:{self.chunk_size}")

        except Exception as e:
            logger.error(f"❌ 启动音频捕获失败: {e}")
            raise

    def stop(self):
        """停止捕获音频"""
        if not self.is_running:
            return

        try:
            if self.stream:
                self.stream.stop()
                self.stream.close()
                self.stream = None

            self.is_running = False
            logger.info("⏹️  音频捕获已停止")

        except Exception as e:
            logger.error(f"❌ 停止音频捕获失败: {e}")

    def get_chunk(self, timeout: float = 1.0) -> Optional[bytes]:
        """
        从队列获取一个音频块

        Args:
            timeout: 超时时间(秒)

        Returns:
            音频数据字节流,如果超时返回None
        """
        try:
            return self.audio_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def clear_queue(self):
        """清空音频队列"""
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break
        logger.debug("🗑️  音频队列已清空")

    @staticmethod
    def list_devices():
        """列出所有可用的音频设备"""
        devices = sd.query_devices()
        print("\n可用音频设备:")
        print("-" * 80)

        for idx, device in enumerate(devices):
            device_type = []
            if device['max_input_channels'] > 0:
                device_type.append("输入")
            if device['max_output_channels'] > 0:
                device_type.append("输出")

            print(f"[{idx:2d}] {device['name']}")
            print(f"     类型: {'/'.join(device_type)}")
            print(f"     输入声道: {device['max_input_channels']}, "
                  f"输出声道: {device['max_output_channels']}")
            print(f"     默认采样率: {device['default_samplerate']}Hz")
            print()


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.INFO)

    print("=" * 80)
    print("音频捕获模块测试")
    print("=" * 80)

    # 列出所有设备
    AudioCapturer.list_devices()

    # 测试麦克风捕获
    print("\n测试麦克风捕获(5秒)...")
    try:
        mic = AudioCapturer("麦克风", sample_rate=16000)
        mic.start()

        import time
        time.sleep(5)

        mic.stop()
        print("✅ 麦克风测试完成")

    except Exception as e:
        print(f"❌ 测试失败: {e}")
