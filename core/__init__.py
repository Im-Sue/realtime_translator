"""
核心模块
"""

from .audio_capture import AudioCapturer
from .audio_output import AudioPlayer, OggOpusPlayer
from .volcengine_client import VolcengineTranslator, VolcengineConfig, TranslationResult
from .conflict_resolver import OpponentPriorityResolver, ConflictStatistics

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
