"""Kokoro-82M through kokoro-onnx: the most natural voices, one shared model for all.

Model and voices: Apache-2.0 (https://huggingface.co/hexgrad/Kokoro-82M), ONNX export by
https://github.com/thewh1teagle/kokoro-onnx (MIT). Pronunciation goes through espeak-ng
(GPL-3.0), installed with the package from Settings, never bundled with ChessOptic.
"""

from __future__ import annotations

import threading
from typing import Any

import numpy as np

from chessoptic.speech.base import Asset, Audio, EngineInfo, Synthesizer, VoiceOption

_RELEASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
_MODEL = Asset(f"{_RELEASE}/kokoro-v1.0.int8.onnx", "kokoro-v1.0.int8.onnx", 92)
_VOICES = Asset(f"{_RELEASE}/voices-v1.0.bin", "voices-v1.0.bin", 28)

INFO = EngineInfo(
    name="kokoro",
    label="Kokoro",
    description="Las voces más naturales; un poco más lenta. Un solo modelo para todas.",
    license_note=(
        "Modelo Apache-2.0. Usa espeak-ng (GPL-3.0) para la pronunciación; se instala "
        "aparte de ChessOptic."
    ),
    packages=("kokoro-onnx>=0.4,<1",),
    modules=("kokoro_onnx",),
    shared_assets=(_MODEL, _VOICES),
)

VOICES: tuple[VoiceOption, ...] = (
    VoiceOption("ef_dora", "Dora", "es"),
    VoiceOption("em_alex", "Alex", "es"),
    VoiceOption("em_santa", "Santa", "es"),
    VoiceOption("af_heart", "Heart · EE.UU.", "en"),
    VoiceOption("af_bella", "Bella · EE.UU.", "en"),
    VoiceOption("am_michael", "Michael · EE.UU.", "en"),
    VoiceOption("bf_emma", "Emma · Reino Unido", "en"),
    VoiceOption("bm_george", "George · Reino Unido", "en"),
)


def _espeak_language(voice: VoiceOption) -> str:
    if voice.language == "es":
        return "es"
    return "en-gb" if voice.id.startswith("b") else "en-us"


class KokoroSynthesizer(Synthesizer):
    info = INFO

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._model: Any = None
        self._lock = threading.Lock()

    def voices(self) -> list[VoiceOption]:
        return list(VOICES)

    def synthesize(self, text: str, voice: VoiceOption) -> Audio:
        with self._lock:
            if self._model is None:
                from kokoro_onnx import Kokoro

                self._model = Kokoro(str(self.path(_MODEL)), str(self.path(_VOICES)))
            samples, rate = self._model.create(text, voice=voice.id, lang=_espeak_language(voice))
        return Audio(np.asarray(samples, dtype=np.float32), int(rate))
