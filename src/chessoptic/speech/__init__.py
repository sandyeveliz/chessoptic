"""Optional neural voices. The OS voice (Qt TextToSpeech) lives in the UI layer.

To add an engine: write a `Synthesizer` adapter in its own module and register it here.
"""

from __future__ import annotations

from pathlib import Path

from chessoptic.core.config import data_dir
from chessoptic.speech.base import Audio, Download, EngineInfo, Synthesizer, VoiceOption
from chessoptic.speech.kokoro import KokoroSynthesizer
from chessoptic.speech.piper import PiperSynthesizer

SYNTHESIZERS: tuple[type[Synthesizer], ...] = (PiperSynthesizer, KokoroSynthesizer)


def models_dir() -> Path:
    return data_dir() / "voices"


def create_synthesizer(name: str) -> Synthesizer | None:
    cls = next((s for s in SYNTHESIZERS if s.info.name == name), None)
    return cls(models_dir() / name) if cls is not None else None


__all__ = [
    "SYNTHESIZERS",
    "Audio",
    "Download",
    "EngineInfo",
    "Synthesizer",
    "VoiceOption",
    "create_synthesizer",
    "models_dir",
]
