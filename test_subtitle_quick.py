"""
字幕窗口快速测试
独立测试字幕窗口的显示和交互功能
"""

import time
import logging
from gui.subtitle_window import SubtitleWindow, SubtitleWindowThread

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    logger.info("🚀 字幕窗口快速测试")
    logger.info("=" * 60)
    logger.info("测试操作:")
    logger.info("  - 左键拖动: 移动窗口")
    logger.info("  - 双击: 切换字体大小")
    logger.info("  - ESC: 隐藏/显示窗口")
    logger.info("=" * 60)

    # 创建字幕窗口
    subtitle_window = SubtitleWindow(
        width=400,
        height=800,
        font_size=20,
        bg_color="#000000",
        text_color="#FFFFFF",
        opacity=0.85,
        position="top_right",
        max_history=10,
        show_timestamp=True
    )

    # 使用线程包装器
    window_thread = SubtitleWindowThread(subtitle_window)

    try:
        # 启动窗口
        window_thread.start()

        # 模拟字幕流
        test_subtitles = [
            "欢迎使用实时同声传译器 v2.0",
            "这是一条测试字幕",
            "Phase 2 双向翻译系统",
            "Channel 1: 中文 → 英文",
            "Channel 2: 英文 → 中文",
            "字幕窗口支持历史记录",
            "可以显示最近10条翻译",
            "支持拖动和字体切换",
            "双击可以放大字体",
            "按ESC可以隐藏窗口"
        ]

        logger.info("\n📺 开始显示测试字幕...")

        for i, subtitle in enumerate(test_subtitles, 1):
            logger.info(f"📝 [{i}/{len(test_subtitles)}] {subtitle}")
            window_thread.update_subtitle(subtitle)

            # 处理UI事件并等待
            for _ in range(20):  # 2秒
                window_thread.process_events()
                time.sleep(0.1)

        # 保持窗口显示
        logger.info("\n⏳ 字幕窗口将保持显示，按 Ctrl+C 退出...")

        while True:
            window_thread.process_events()
            time.sleep(0.1)

    except KeyboardInterrupt:
        logger.info("\n⌨️  接收到中断信号")
    finally:
        logger.info("🛑 关闭字幕窗口...")
        window_thread.stop()
        logger.info("✅ 测试完成")


if __name__ == "__main__":
    main()
