"""
音频输出模块
将翻译后的音频输出到虚拟麦克风设备(VB-CABLE)
"""

import sounddevice as sd
import numpy as np
import logging
from typing import Optional
import queue
import threading

logger = logging.getLogger(__name__)


class AudioPlayer:
    """音频播放器"""

    def __init__(
        self,
        device_name: str,
        sample_rate: int = 24000,
        channels: int = 1
    ):
        """
        初始化音频播放器

        Args:
            device_name: 输出设备名称(如"CABLE Input")
            sample_rate: 采样率
            channels: 声道数
        """
        self.device_name = device_name
        self.sample_rate = sample_rate
        self.channels = channels

        self.device_index = None
        self.stream = None
        self.audio_queue = queue.Queue()
        self.is_running = False
        self.playback_thread = None

        # 查找设备
        self._find_device()

    def _find_device(self):
        """查找输出设备"""
        try:
            devices = sd.query_devices()

            for idx, device in enumerate(devices):
                # 匹配设备名称且支持输出
                if (self.device_name.lower() in device['name'].lower() and
                    device['max_output_channels'] > 0):
                    self.device_index = idx
                    logger.info(f"✅ 找到输出设备: [{idx}] {device['name']}")
                    return

            if self.device_index is None:
                logger.warning(f"⚠️  未找到设备 '{self.device_name}', 使用默认输出设备")
                self.device_index = sd.default.device[1]  # 默认输出设备

        except Exception as e:
            logger.error(f"❌ 查找输出设备失败: {e}")
            raise

    def start(self):
        """启动播放器"""
        if self.is_running:
            logger.warning("⚠️  播放器已在运行")
            return

        self.is_running = True
        self.playback_thread = threading.Thread(target=self._playback_loop, daemon=True)
        self.playback_thread.start()

        device_info = sd.query_devices(self.device_index)
        logger.info(f"✅ 音频播放器已启动: {device_info['name']}")

    def stop(self):
        """停止播放器"""
        if not self.is_running:
            return

        self.is_running = False

        if self.playback_thread:
            self.playback_thread.join(timeout=2.0)

        logger.info("⏹️  音频播放器已停止")

    def play(self, audio_data: bytes):
        """
        播放音频数据

        Args:
            audio_data: 音频字节流
        """
        if not self.is_running:
            logger.warning("⚠️  播放器未启动")
            return

        self.audio_queue.put(audio_data)

    def _playback_loop(self):
        """播放循环(在独立线程中运行)"""
        logger.debug("播放循环已启动")

        while self.is_running:
            try:
                # 从队列获取音频数据
                audio_data = self.audio_queue.get(timeout=0.5)

                if audio_data:
                    self._play_chunk(audio_data)

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"❌ 播放错误: {e}")

        logger.debug("播放循环已退出")

    def _play_chunk(self, audio_data: bytes):
        """播放单个音频块"""
        try:
            # 将字节流转换为numpy数组
            # 假设音频是16bit PCM格式
            audio_array = np.frombuffer(audio_data, dtype=np.int16)

            # 转换为float32格式(-1.0到1.0)
            audio_float = audio_array.astype(np.float32) / 32767.0

            # 重塑为正确的通道数 (n_samples, n_channels)
            if self.channels == 1:
                audio_float = audio_float.reshape(-1, 1)
            elif self.channels == 2:
                audio_float = audio_float.reshape(-1, 2)

            # 播放音频
            logger.info(f"🔊 播放PCM音频: {len(audio_float)} 样本 × {self.channels} 通道")
            sd.play(audio_float, samplerate=self.sample_rate, device=self.device_index)
            sd.wait()  # 等待播放完成

        except Exception as e:
            logger.error(f"❌ 播放音频块失败: {e}")

    def clear_queue(self):
        """清空播放队列"""
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break
        logger.debug("🗑️  播放队列已清空")


class OggOpusPlayer(AudioPlayer):
    """
    Ogg Opus格式音频播放器
    火山引擎s2s模式返回的是ogg_opus格式
    支持双输出: 虚拟麦克风 + 本地监听
    """

    def __init__(self, device_name: str, sample_rate: int = 24000, use_ffmpeg: bool = False,
                 monitor_device: str = None, enable_monitor: bool = False):
        """
        初始化Opus播放器

        Args:
            device_name: 主输出设备名称 (通常是VB-CABLE Input)
            sample_rate: 采样率
            use_ffmpeg: 强制使用FFmpeg解码(默认False,会尝试opuslib)
            monitor_device: 监听输出设备名称 (通常是默认扬声器,用于调试)
            enable_monitor: 是否启用监听输出
        """
        # VB-CABLE通常需要立体声输入,即使源是单声道也需要转换
        super().__init__(device_name, sample_rate, channels=2)

        # 监听输出配置
        self.monitor_device = monitor_device
        self.enable_monitor = enable_monitor
        self.monitor_device_index = None
        self.monitor_stream = None  # 监听输出流

        if self.enable_monitor and self.monitor_device:
            # 查找监听设备
            devices = sd.query_devices()
            for i, device in enumerate(devices):
                if self.monitor_device in device['name'] and device['max_output_channels'] > 0:
                    self.monitor_device_index = i
                    logger.info(f"🔊 找到监听设备: [{i}] {device['name']}")
                    break

            if self.monitor_device_index is None:
                logger.warning(f"⚠️  未找到监听设备: {self.monitor_device}, 监听输出已禁用")
                self.enable_monitor = False

        # 初始化FFmpeg线程锁 (防止并发文件操作冲突)
        self._ffmpeg_lock = threading.Lock()
        logger.info("🔒 FFmpeg线程锁已初始化")

        # 持久FFmpeg进程 (用于流式解码)
        self._ffmpeg_process = None
        self._ffmpeg_reader_thread = None
        self._pcm_queue = queue.Queue()
        logger.info("🎬 FFmpeg流式解码器已初始化")

        # 检查是否安装了opus解码器
        self.has_opus = False

        if not use_ffmpeg:
            try:
                # 使用 importlib 延迟导入,避免初始化时的异常
                import importlib.util
                spec = importlib.util.find_spec("opuslib")

                if spec is not None:
                    import opuslib
                    # 尝试创建一个测试解码器,看是否真的可用
                    try:
                        test_decoder = opuslib.Decoder(48000, 1)
                        self.has_opus = True
                        logger.info("✅ Opus解码器(opuslib)可用")
                    except Exception as e:
                        logger.warning(f"⚠️  Opuslib已安装但无法使用: {e}")
                        logger.info("ℹ️  将使用FFmpeg解码")
                else:
                    logger.info("ℹ️  未安装opuslib,将使用FFmpeg解码")
            except Exception as e:
                logger.warning(f"⚠️  检查opuslib时出错: {e}")
                logger.info("ℹ️  将使用FFmpeg解码")
        else:
            logger.info("ℹ️  强制使用FFmpeg解码")

    def start(self):
        """启动播放器 (重写父类方法)"""
        if self.is_running:
            logger.warning("⚠️  播放器已在运行")
            return

        self.is_running = True

        # 如果使用FFmpeg,启动FFmpeg进程
        if not self.has_opus:
            self._start_ffmpeg_process()

        # 启动播放线程
        self.playback_thread = threading.Thread(target=self._playback_loop_ffmpeg, daemon=True)
        self.playback_thread.start()

        device_info = sd.query_devices(self.device_index)
        logger.info(f"✅ 音频播放器已启动: {device_info['name']}")

    def stop(self):
        """停止播放器 (重写父类方法)"""
        if not self.is_running:
            return

        self.is_running = False

        # 停止FFmpeg进程
        if self._ffmpeg_process:
            self._stop_ffmpeg_process()

        if self.playback_thread:
            self.playback_thread.join(timeout=2.0)

        logger.info("⏹️  音频播放器已停止")

    def _playback_loop_ffmpeg(self):
        """播放循环(使用OutputStream流式播放)"""
        logger.debug("FFmpeg播放循环已启动")

        output_rate = getattr(self, 'actual_output_rate', self.sample_rate)

        # 累积缓冲区 - 存储未播放的样本
        audio_buffer = np.array([], dtype=np.float32)
        buffer_lock = threading.Lock()  # 缓冲区锁,防止并发访问

        # 音频回调函数 - sounddevice会持续调用此函数填充音频缓冲区
        def audio_callback(outdata, frames, time_info, status):
            nonlocal audio_buffer

            if status:
                logger.warning(f"⚠️ 主输出状态: {status}")

            try:
                with buffer_lock:  # 获取锁
                    # 从队列获取所有可用的PCM数据
                    while True:
                        try:
                            pcm_data = self._pcm_queue.get_nowait()

                            # 转换为numpy数组
                            audio_array = np.frombuffer(pcm_data, dtype=np.int16)
                            audio_float = audio_array.astype(np.float32) / 32767.0

                            # 追加到缓冲区
                            audio_buffer = np.concatenate([audio_buffer, audio_float])

                        except queue.Empty:
                            break

                    # 计算需要的样本数 (frames × channels)
                    needed_samples = frames * self.channels

                    if len(audio_buffer) >= needed_samples:
                        # 有足够数据,取出需要的部分
                        output_samples = audio_buffer[:needed_samples]
                        audio_buffer = audio_buffer[needed_samples:]  # 剩余数据保留

                        # 重塑为 (frames, channels)
                        output_samples = output_samples.reshape(frames, self.channels)
                        outdata[:] = output_samples

                        logger.debug(f"🔊 主输出 {frames} 帧, 缓冲区剩余 {len(audio_buffer)} 样本")

                    elif len(audio_buffer) > 0:
                        # 数据不足,先播放已有的,其余填充静音
                        available_frames = len(audio_buffer) // self.channels
                        output_samples = audio_buffer[:available_frames * self.channels]
                        output_samples = output_samples.reshape(available_frames, self.channels)

                        outdata[:available_frames] = output_samples
                        outdata[available_frames:] = 0  # 静音
                        audio_buffer = np.array([], dtype=np.float32)  # 清空缓冲区

                        logger.debug(f"🔊 主输出 {available_frames}/{frames} 帧 (数据不足)")

                    else:
                        # 缓冲区为空,输出静音
                        outdata[:] = 0

            except Exception as e:
                logger.error(f"❌ 主输出回调错误: {e}")
                import traceback
                traceback.print_exc()
                outdata[:] = 0

        # 监听输出回调 - 复制数据而不消耗buffer
        def monitor_callback(outdata, frames, time_info, status):
            if status:
                logger.warning(f"⚠️ 监听输出状态: {status}")

            try:
                with buffer_lock:  # 获取锁
                    needed_samples = frames * self.channels

                    if len(audio_buffer) >= needed_samples:
                        # 复制数据(不消耗buffer)
                        output_samples = audio_buffer[:needed_samples].copy()
                        output_samples = output_samples.reshape(frames, self.channels)
                        outdata[:] = output_samples
                        logger.debug(f"🔊 监听输出 {frames} 帧")

                    elif len(audio_buffer) > 0:
                        # 部分数据
                        available_frames = len(audio_buffer) // self.channels
                        output_samples = audio_buffer[:available_frames * self.channels].copy()
                        output_samples = output_samples.reshape(available_frames, self.channels)
                        outdata[:available_frames] = output_samples
                        outdata[available_frames:] = 0
                        logger.debug(f"🔊 监听输出 {available_frames}/{frames} 帧")

                    else:
                        # 静音
                        outdata[:] = 0

            except Exception as e:
                logger.error(f"❌ 监听输出回调错误: {e}")
                outdata[:] = 0

        # 创建并启动主输出流 (VB-CABLE Input)
        try:
            main_stream = sd.OutputStream(
                device=self.device_index,
                channels=self.channels,
                samplerate=output_rate,
                callback=audio_callback,
                blocksize=2048
            )
            main_stream.start()
            logger.info(f"✅ 主输出流已启动: {self.channels}ch @ {output_rate}Hz → {sd.query_devices(self.device_index)['name']}")

            # 如果启用监听,创建监听输出流
            monitor_stream = None
            if self.enable_monitor and self.monitor_device_index is not None:
                try:
                    monitor_stream = sd.OutputStream(
                        device=self.monitor_device_index,
                        channels=self.channels,
                        samplerate=output_rate,
                        callback=monitor_callback,
                        blocksize=2048
                    )
                    monitor_stream.start()
                    logger.info(f"🔊 监听输出流已启动: {self.channels}ch @ {output_rate}Hz → {sd.query_devices(self.monitor_device_index)['name']}")
                except Exception as e:
                    logger.warning(f"⚠️  监听流启动失败: {e}")
                    monitor_stream = None

            # 保持流活跃直到停止
            while self.is_running:
                sd.sleep(100)

            logger.info("🔊 音频流正在关闭...")

            # 关闭流
            main_stream.stop()
            main_stream.close()
            if monitor_stream:
                monitor_stream.stop()
                monitor_stream.close()

        except Exception as e:
            logger.error(f"❌ 音频流错误: {e}")
            import traceback
            traceback.print_exc()

        logger.debug("FFmpeg播放循环已退出")

    def _start_ffmpeg_process(self):
        """启动持久的FFmpeg进程用于流式解码"""
        import subprocess

        try:
            logger.info("🎬 启动持久FFmpeg进程...")
            # VB-CABLE需要48kHz采样率,强制重采样
            output_sample_rate = 48000
            logger.info(f"📊 重采样: {self.sample_rate}Hz → {output_sample_rate}Hz")

            self._ffmpeg_process = subprocess.Popen(
                [
                    'ffmpeg',
                    '-loglevel', 'error',
                    '-f', 'ogg',              # 输入格式: Ogg容器
                    '-i', 'pipe:0',           # 从stdin读取流式数据
                    '-f', 's16le',            # 输出格式: PCM s16le
                    '-acodec', 'pcm_s16le',
                    '-ar', str(output_sample_rate),  # 强制48kHz输出
                    '-ac', str(self.channels),
                    'pipe:1'                  # 输出到stdout
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0  # 无缓冲,实时处理
            )

            # 更新实际播放采样率
            self.actual_output_rate = output_sample_rate

            # 启动读取PCM数据的线程
            self._ffmpeg_reader_thread = threading.Thread(
                target=self._read_pcm_output,
                daemon=True
            )
            self._ffmpeg_reader_thread.start()

            logger.info("✅ 持久FFmpeg进程已启动")

        except Exception as e:
            logger.error(f"❌ 启动FFmpeg进程失败: {e}")
            raise

    def _stop_ffmpeg_process(self):
        """停止FFmpeg进程"""
        if self._ffmpeg_process:
            try:
                self._ffmpeg_process.stdin.close()
                self._ffmpeg_process.terminate()
                self._ffmpeg_process.wait(timeout=2.0)
                logger.info("✅ FFmpeg进程已停止")
            except Exception as e:
                logger.error(f"⚠️  停止FFmpeg进程时出错: {e}")
                try:
                    self._ffmpeg_process.kill()
                except:
                    pass

    def _read_pcm_output(self):
        """读取FFmpeg输出的PCM数据(在独立线程中运行)"""
        logger.info("📖 PCM读取线程已启动")

        try:
            while self._ffmpeg_process and self._ffmpeg_process.poll() is None:
                # 读取固定大小的PCM数据块 (480样本 * 2通道 * 2字节/样本 = 1920字节)
                pcm_chunk = self._ffmpeg_process.stdout.read(1920)

                if pcm_chunk:
                    self._pcm_queue.put(pcm_chunk)
                    logger.debug(f"📦 读取PCM数据: {len(pcm_chunk)} bytes")
                else:
                    break

        except Exception as e:
            logger.error(f"❌ 读取PCM输出错误: {e}")
        finally:
            logger.info("📖 PCM读取线程已退出")

    def play(self, audio_data: bytes):
        """播放音频 (重写父类方法)"""
        if not self.is_running:
            logger.warning("⚠️  播放器未启动")
            return

        # 直接调用FFmpeg解码
        if self.has_opus:
            self._play_with_opus(audio_data)
        else:
            self._play_with_ffmpeg(audio_data)

    def _play_chunk(self, audio_data: bytes):
        """播放Ogg Opus音频块"""
        if self.has_opus:
            self._play_with_opus(audio_data)
        else:
            self._play_with_ffmpeg(audio_data)

    def _play_with_opus(self, audio_data: bytes):
        """使用opuslib解码播放"""
        try:
            import opuslib

            # 创建Opus解码器
            decoder = opuslib.Decoder(self.sample_rate, self.channels)

            # 解码音频
            pcm_data = decoder.decode(audio_data, frame_size=960)

            # 转换为numpy数组
            audio_array = np.frombuffer(pcm_data, dtype=np.int16)
            audio_float = audio_array.astype(np.float32) / 32767.0

            # 重塑为正确的通道数
            if self.channels == 1:
                audio_float = audio_float.reshape(-1, 1)
            elif self.channels == 2:
                audio_float = audio_float.reshape(-1, 2)

            # 播放
            logger.info(f"🔊 播放PCM音频: {len(audio_float)} 样本 × {self.channels} 通道")
            sd.play(audio_float, samplerate=self.sample_rate, device=self.device_index)
            sd.wait()

        except Exception as e:
            logger.error(f"❌ Opus解码失败: {e}")

    def _play_with_ffmpeg(self, audio_data: bytes):
        """使用持久FFmpeg进程解码播放"""
        import time

        # 检查音频数据是否为空
        if not audio_data or len(audio_data) == 0:
            logger.warning("⚠️  收到空音频数据,跳过播放")
            return

        # 确保FFmpeg进程已启动
        if not self._ffmpeg_process or self._ffmpeg_process.poll() is not None:
            logger.warning("⚠️  FFmpeg进程未运行,正在重启...")
            self._start_ffmpeg_process()

        try:
            # 将Ogg数据写入FFmpeg的stdin
            logger.info(f"📤 发送Ogg数据到FFmpeg: {len(audio_data)} bytes")
            self._ffmpeg_process.stdin.write(audio_data)
            self._ffmpeg_process.stdin.flush()

            # 等待PCM数据从队列中取出并播放
            time.sleep(0.01)  # 给FFmpeg一点时间处理

        except BrokenPipeError:
            logger.error("❌ FFmpeg进程管道断开,正在重启...")
            self._stop_ffmpeg_process()
            self._start_ffmpeg_process()
        except Exception as e:
            logger.error(f"❌ 发送数据到FFmpeg失败: {e}")


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.INFO)

    print("=" * 80)
    print("音频输出模块测试")
    print("=" * 80)

    # 列出所有输出设备
    devices = sd.query_devices()
    print("\n可用输出设备:")
    for idx, device in enumerate(devices):
        if device['max_output_channels'] > 0:
            print(f"[{idx}] {device['name']} - 声道数: {device['max_output_channels']}")

    # 测试虚拟麦克风播放
    try:
        player = AudioPlayer("CABLE Input", sample_rate=24000)
        player.start()

        print("\n✅ 播放器已启动(测试虚拟麦克风)")
        print("提示: 请在会议软件中选择'CABLE Output'作为麦克风")

        import time
        time.sleep(2)

        player.stop()
        print("✅ 测试完成")

    except Exception as e:
        print(f"❌ 测试失败: {e}")
