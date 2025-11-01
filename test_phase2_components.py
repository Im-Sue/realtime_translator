"""
Phase 2 组件测试脚本
测试系统音频捕获、字幕窗口和双通道翻译器的基本功能
"""

import sys
import time
import logging
from core.system_audio_capture import SystemAudioCapturer
from gui.subtitle_window import SubtitleWindow, SubtitleWindowThread

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

logger = logging.getLogger(__name__)


def test_system_audio_capture():
    """测试系统音频捕获"""
    logger.info("\n" + "=" * 80)
    logger.info("🧪 测试 1: 系统音频捕获器")
    logger.info("=" * 80)

    try:
        # 创建捕获器
        capturer = SystemAudioCapturer(
            device_name="立体声混音",
            fallback_device="CABLE Output",
            sample_rate=16000,
            channels=1,
            chunk_size=1600
        )

        # 启动捕获
        capturer.start()

        # 捕获5秒钟的音频
        logger.info("📥 正在捕获5秒音频...")
        start_time = time.time()
        chunk_count = 0

        while time.time() - start_time < 5:
            chunk = capturer.get_chunk(timeout=0.5)
            if chunk:
                chunk_count += 1
                logger.info(f"✅ 接收到音频块 {chunk_count}: {len(chunk)} bytes")

        # 停止捕获
        capturer.stop()

        logger.info(f"\n✅ 测试通过: 捕获了 {chunk_count} 个音频块")
        return True

    except Exception as e:
        logger.error(f"\n❌ 测试失败: {e}", exc_info=True)
        return False


def test_subtitle_window():
    """测试字幕窗口"""
    logger.info("\n" + "=" * 80)
    logger.info("🧪 测试 2: 字幕窗口")
    logger.info("=" * 80)

    try:
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
            show_timestamp=False
        )

        # 使用线程包装器
        window_thread = SubtitleWindowThread(subtitle_window)

        # 启动窗口
        window_thread.start()

        # 模拟字幕更新
        logger.info("📺 显示测试字幕...")

        test_subtitles = [
            "这是第一条测试字幕",
            "这是第二条测试字幕",
            "Phase 2 双向翻译系统",
            "字幕窗口功能正常",
            "测试完成！"
        ]

        for i, subtitle in enumerate(test_subtitles, 1):
            logger.info(f"📝 更新字幕 {i}: {subtitle}")
            window_thread.update_subtitle(subtitle)

            # 处理UI事件
            for _ in range(10):  # 处理1秒的事件
                window_thread.process_events()
                time.sleep(0.1)

            time.sleep(1)  # 等待1秒再显示下一条

        # 保持窗口显示3秒
        logger.info("⏳ 字幕窗口将保持3秒...")
        for _ in range(30):
            window_thread.process_events()
            time.sleep(0.1)

        # 停止窗口
        window_thread.stop()

        logger.info("\n✅ 测试通过: 字幕窗口显示正常")
        return True

    except Exception as e:
        logger.error(f"\n❌ 测试失败: {e}", exc_info=True)
        return False


def test_config_loading():
    """测试配置文件加载"""
    logger.info("\n" + "=" * 80)
    logger.info("🧪 测试 3: 配置文件加载")
    logger.info("=" * 80)

    try:
        import yaml

        # 测试 config_v2.yaml
        with open("config_v2.yaml", 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        # 验证必需的配置项
        required_keys = [
            'volcengine',
            'audio',
            'channels',
            'subtitle_window'
        ]

        for key in required_keys:
            if key not in config:
                raise ValueError(f"配置文件缺少必需的键: {key}")
            logger.info(f"✅ 配置项 '{key}' 存在")

        # 验证火山引擎配置
        volc_config = config['volcengine']
        if not volc_config.get('app_key') or not volc_config.get('access_key'):
            logger.warning("⚠️  警告: 火山引擎密钥未配置")

        # 验证通道配置
        channels = config['channels']
        logger.info(f"✅ Channel 1 (中→英): {channels['zh_to_en']['mode']}, 启用: {channels['zh_to_en']['enabled']}")
        logger.info(f"✅ Channel 2 (英→中): {channels['en_to_zh']['mode']}, 启用: {channels['en_to_zh']['enabled']}")

        # 验证字幕窗口配置
        subtitle_cfg = config['subtitle_window']
        logger.info(f"✅ 字幕窗口: {subtitle_cfg['width']}x{subtitle_cfg['height']}, 位置: {subtitle_cfg['position']}")

        logger.info("\n✅ 测试通过: 配置文件完整且有效")
        return True

    except Exception as e:
        logger.error(f"\n❌ 测试失败: {e}", exc_info=True)
        return False


def main():
    """主测试函数"""
    logger.info("\n" + "=" * 80)
    logger.info("🚀 Phase 2 组件测试套件")
    logger.info("=" * 80)
    logger.info("")

    results = {}

    # 测试1: 配置文件加载
    results['config'] = test_config_loading()

    # 测试2: 系统音频捕获
    logger.info("\n⏳ 准备测试系统音频捕获...")
    time.sleep(2)
    results['audio_capture'] = test_system_audio_capture()

    # 测试3: 字幕窗口
    logger.info("\n⏳ 准备测试字幕窗口...")
    time.sleep(2)
    results['subtitle_window'] = test_subtitle_window()

    # 打印测试结果
    logger.info("\n" + "=" * 80)
    logger.info("📊 测试结果汇总")
    logger.info("=" * 80)

    all_passed = True
    for test_name, result in results.items():
        status = "✅ 通过" if result else "❌ 失败"
        logger.info(f"{test_name}: {status}")
        if not result:
            all_passed = False

    logger.info("=" * 80)

    if all_passed:
        logger.info("\n🎉 所有测试通过！Phase 2 组件工作正常")
        logger.info("\n📋 下一步:")
        logger.info("1. 确保火山引擎 API 密钥已配置")
        logger.info("2. 检查 Zoom 音频设置")
        logger.info("3. 运行: python main_v2.py")
        return 0
    else:
        logger.error("\n❌ 部分测试失败，请检查错误信息")
        return 1


if __name__ == "__main__":
    sys.exit(main())
