"""Piper (VITS exported to ONNX): fast on CPU, one model file per voice.

Engine: https://github.com/OHF-Voice/piper1-gpl (GPL-3.0). It is never bundled with
ChessOptic: the user downloads it from Settings, like any other optional voice.
Voices: https://huggingface.co/rhasspy/piper-voices (each with its own model card).
"""

from __future__ import annotations

import threading
from typing import Any

import numpy as np

from chessoptic.speech.base import Asset, Audio, EngineInfo, Synthesizer, VoiceOption

_HF = "https://huggingface.co/rhasspy/piper-voices/resolve/main"

INFO = EngineInfo(
    name="piper",
    label="Piper",
    description="Voces neuronales livianas, rápidas en cualquier PC. Un archivo por voz.",
    license_note=(
        "Motor GPL-3.0, se instala aparte de ChessOptic. Cada voz tiene su licencia "
        "(ficha en huggingface.co/rhasspy/piper-voices)."
    ),
    packages=("piper-tts>=1.3,<2",),
    modules=("piper",),
)


def _voice(key: str, label: str, language: str, size_mb: int) -> VoiceOption:
    lang_region, name, quality = key.split("-")
    base = f"{_HF}/{lang_region[:2]}/{lang_region}/{name}/{quality}/{key}"
    return VoiceOption(
        id=key,
        label=label,
        language=language,
        assets=(
            Asset(f"{base}.onnx", f"{key}.onnx", size_mb),
            Asset(f"{base}.onnx.json", f"{key}.onnx.json", 0),
        ),
    )


VOICES: tuple[VoiceOption, ...] = (
    _voice("es_AR-daniela-high", "Daniela · Argentina", "es", 114),
    _voice("es_MX-claude-high", "Claude · México", "es", 63),
    _voice("es_ES-davefx-medium", "Davefx · España", "es", 63),
    _voice("en_US-lessac-medium", "Lessac · EE.UU.", "en", 63),
    _voice("en_US-ryan-medium", "Ryan · EE.UU.", "en", 63),
    _voice("en_US-amy-medium", "Amy · EE.UU.", "en", 63),
)


class PiperSynthesizer(Synthesizer):
    info = INFO

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._loaded: dict[str, Any] = {}  # voice id -> PiperVoice
        self._lock = threading.Lock()

    def voices(self) -> list[VoiceOption]:
        return list(VOICES)

    def _model(self, voice: VoiceOption) -> Any:
        with self._lock:
            if voice.id not in self._loaded:
                from piper import PiperVoice

                self._loaded[voice.id] = PiperVoice.load(str(self.path(voice.assets[0])))
            return self._loaded[voice.id]

    def synthesize(self, text: str, voice: VoiceOption) -> Audio:
        chunks = list(self._model(voice).synthesize(text))
        if not chunks:
            return Audio(np.zeros(0, dtype=np.float32), 22050)
        samples = np.concatenate([c.audio_float_array for c in chunks]).astype(np.float32)
        return Audio(samples, int(chunks[0].sample_rate))
