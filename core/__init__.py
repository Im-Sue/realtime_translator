"""
核心模块

NOTE: 不在此处贪婪导入子模块。
各子模块（audio_capture, audio_output 等）依赖 sounddevice/numpy 等 C 扩展，
顶层导入会导致 `import core` 时触发全部加载链。
请直接从子模块导入：from core.audio_capture import AudioCapturer
"""

__all__ = [
    'AudioCapturer',
    'AudioPlayer',
    'OggOpusPlayer',
    'VolcengineTranslator',
    'VolcengineConfig',
    'TranslationResult',
    'OpponentPriorityResolver',
    'ConflictStatistics',
]
