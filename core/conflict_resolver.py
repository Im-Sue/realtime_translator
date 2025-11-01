"""
冲突解决器 - 对方优先模式
当检测到对方说话时,自动暂停自己的音频传输
"""

import time
import logging
from collections import deque
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ConflictStatistics:
    """冲突统计信息"""
    interruption_count: int = 0      # 被打断次数
    total_pause_time: float = 0.0    # 总暂停时长(秒)
    last_interruption_time: Optional[float] = None
    currently_paused: bool = False


class OpponentPriorityResolver:
    """对方优先的冲突解决器"""

    def __init__(self, pause_threshold: float = 0.5, history_size: int = 10):
        """
        初始化冲突解决器

        Args:
            pause_threshold: 对方停止说话后多久恢复自己的传输(秒)
            history_size: 历史记录大小(用于平滑检测)
        """
        self.pause_threshold = pause_threshold
        self.history_size = history_size

        # 状态追踪
        self.opponent_speaking = False        # 对方是否在说话
        self.last_opponent_activity = 0.0     # 对方最后活动时间戳
        self.pause_start_time = 0.0          # 暂停开始时间

        # 历史记录(用于平滑检测)
        self.recent_opponent_activity = deque(maxlen=history_size)

        # 统计信息
        self.stats = ConflictStatistics()

        logger.info(f"✅ 冲突解决器已初始化 (对方优先模式, 阈值:{pause_threshold}s)")

    def update_opponent_activity(self, is_speaking: bool, timestamp: Optional[float] = None):
        """
        更新对方的语音活动状态

        Args:
            is_speaking: 对方是否正在说话
            timestamp: 时间戳(如果不提供则使用当前时间)
        """
        if timestamp is None:
            timestamp = time.time()

        # 更新历史记录
        self.recent_opponent_activity.append(is_speaking)

        if is_speaking:
            # 对方正在说话
            self.last_opponent_activity = timestamp

            if not self.opponent_speaking:
                # 对方刚开始说话
                self._on_opponent_start_speaking(timestamp)
        else:
            # 对方没说话,检查是否应该恢复
            if self.opponent_speaking:
                time_since_last = timestamp - self.last_opponent_activity

                if time_since_last >= self.pause_threshold:
                    # 超过阈值,恢复传输
                    self._on_opponent_stop_speaking(timestamp)

    def _on_opponent_start_speaking(self, timestamp: float):
        """对方开始说话的处理"""
        self.opponent_speaking = True
        self.pause_start_time = timestamp

        # 更新统计
        self.stats.interruption_count += 1
        self.stats.last_interruption_time = timestamp
        self.stats.currently_paused = True

        logger.info(f"🔴 对方开始说话,暂停自己的传输 (第{self.stats.interruption_count}次)")

    def _on_opponent_stop_speaking(self, timestamp: float):
        """对方停止说话的处理"""
        self.opponent_speaking = False

        # 更新统计
        pause_duration = timestamp - self.pause_start_time
        self.stats.total_pause_time += pause_duration
        self.stats.currently_paused = False

        logger.info(f"🟢 对方停止说话,恢复自己的传输 (暂停了{pause_duration:.2f}秒)")

    def should_transmit_own_audio(self) -> bool:
        """
        判断当前是否应该传输自己的音频

        Returns:
            True: 可以传输
            False: 应该暂停(对方正在说话)
        """
        return not self.opponent_speaking

    def get_status_message(self) -> str:
        """
        获取当前状态的提示信息

        Returns:
            状态消息字符串
        """
        if self.opponent_speaking:
            return "🔴 对方正在说话..."
        else:
            return "🟢 可以说话"

    def get_status_color(self) -> str:
        """
        获取当前状态的颜色

        Returns:
            颜色字符串("red"或"green")
        """
        return "red" if self.opponent_speaking else "green"

    def get_statistics(self) -> ConflictStatistics:
        """
        获取统计信息

        Returns:
            统计信息对象
        """
        return self.stats

    def get_statistics_dict(self) -> dict:
        """
        获取统计信息字典

        Returns:
            包含统计信息的字典
        """
        return {
            "interruption_count": self.stats.interruption_count,
            "total_pause_time": round(self.stats.total_pause_time, 2),
            "average_pause_time": (
                round(self.stats.total_pause_time / self.stats.interruption_count, 2)
                if self.stats.interruption_count > 0 else 0
            ),
            "currently_paused": self.stats.currently_paused,
            "last_interruption": (
                time.strftime("%H:%M:%S", time.localtime(self.stats.last_interruption_time))
                if self.stats.last_interruption_time else "无"
            )
        }

    def reset_statistics(self):
        """重置统计信息"""
        self.stats = ConflictStatistics()
        logger.info("📊 统计信息已重置")

    def is_opponent_likely_speaking(self) -> bool:
        """
        基于历史记录判断对方是否可能在说话(平滑检测)

        Returns:
            True: 对方可能在说话
            False: 对方可能没说话
        """
        if len(self.recent_opponent_activity) == 0:
            return False

        # 如果最近70%的检测都是说话,则认为对方在说话
        speaking_ratio = sum(self.recent_opponent_activity) / len(self.recent_opponent_activity)
        return speaking_ratio >= 0.7

    def print_statistics(self):
        """打印统计信息到日志"""
        stats_dict = self.get_statistics_dict()

        logger.info("=" * 60)
        logger.info("冲突解决统计信息")
        logger.info("-" * 60)
        logger.info(f"  被打断次数: {stats_dict['interruption_count']}")
        logger.info(f"  总暂停时长: {stats_dict['total_pause_time']}秒")
        logger.info(f"  平均暂停时长: {stats_dict['average_pause_time']}秒")
        logger.info(f"  当前状态: {'暂停中' if stats_dict['currently_paused'] else '正常'}")
        logger.info(f"  最后打断时间: {stats_dict['last_interruption']}")
        logger.info("=" * 60)


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.INFO)

    print("=" * 80)
    print("冲突解决器测试")
    print("=" * 80)

    resolver = OpponentPriorityResolver(pause_threshold=0.5)

    # 模拟场景
    print("\n场景1: 对方开始说话")
    resolver.update_opponent_activity(is_speaking=True)
    print(f"状态: {resolver.get_status_message()}")
    print(f"可以传输: {resolver.should_transmit_own_audio()}")

    print("\n场景2: 等待0.3秒(未达到阈值)")
    time.sleep(0.3)
    resolver.update_opponent_activity(is_speaking=False)
    print(f"状态: {resolver.get_status_message()}")
    print(f"可以传输: {resolver.should_transmit_own_audio()}")

    print("\n场景3: 再等待0.3秒(达到阈值)")
    time.sleep(0.3)
    resolver.update_opponent_activity(is_speaking=False)
    print(f"状态: {resolver.get_status_message()}")
    print(f"可以传输: {resolver.should_transmit_own_audio()}")

    print("\n场景4: 对方再次说话")
    resolver.update_opponent_activity(is_speaking=True)
    time.sleep(0.6)
    resolver.update_opponent_activity(is_speaking=False)

    print("\n统计信息:")
    resolver.print_statistics()

    print("\n✅ 测试完成")
