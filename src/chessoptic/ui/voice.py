"""MoveVoice: reads moves aloud. The UI only talks to this facade.

How it speaks is a strategy (`Speaker`):
- `SystemSpeaker`: the OS voices through Qt TextToSpeech. Always there, no download.
- `NeuralSpeaker`: any `chessoptic.speech.Synthesizer` (Piper, Kokoro, ...) rendered off
  the GUI thread and played with Qt Multimedia. Optional: downloaded from Settings.

A neural engine that isn't downloaded yet falls back to the system voice, so the user
always hears something.
"""

from __future__ import annotations

import logging
import sys
import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Protocol

import numpy as np
from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QLocale, QObject, Signal

from chessoptic.game.notation import normalize_language, spoken_san
from chessoptic.speech import (
    SYNTHESIZERS,
    Audio,
    Download,
    Synthesizer,
    VoiceOption,
    create_synthesizer,
)
from chessoptic.speech.install import InstallError, install

log = logging.getLogger(__name__)

try:
    from PySide6.QtTextToSpeech import QTextToSpeech
except ImportError:  # some Linux PySide6 builds ship without the module
    QTextToSpeech = None  # type: ignore[assignment,misc]

try:
    from PySide6.QtMultimedia import QAudioFormat, QAudioSink, QMediaDevices
except ImportError:
    QAudioSink = None  # type: ignore[assignment,misc]

SYSTEM = "system"
# Best engine first; "mock" is Qt's test backend and never speaks.
_ENGINE_PREFERENCE = ("winrt", "sapi", "darwin", "speechd", "flite", "android")
_QT_LANGUAGE = {"es": QLocale.Language.Spanish, "en": QLocale.Language.English}
_INSTALL_HINT = {
    "win32": "Instalá una voz desde Configuración > Hora e idioma > Voz > Agregar voces.",
    "darwin": "Instalá una voz desde Ajustes del Sistema > Accesibilidad > Contenido leído.",
}


@dataclass(frozen=True)
class EngineChoice:
    name: str
    label: str
    description: str
    license_note: str
    downloadable: bool


@dataclass(frozen=True)
class VoiceChoice:
    id: str
    label: str
    ready: bool
    size_mb: int  # what's left to download for it


class Speaker(Protocol):
    def say(self, text: str) -> None: ...

    def stop(self) -> None: ...


# ---------------------------------------------------------------- system voices


class SystemSpeaker(QObject):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._tts: QTextToSpeech | None = None
        self.error = ""
        self.matched = False
        if QTextToSpeech is None:
            self.error = "Esta instalación de Qt no incluye síntesis de voz."
            return
        engines = [e for e in QTextToSpeech.availableEngines() if e != "mock"]
        ordered = [e for e in _ENGINE_PREFERENCE if e in engines] + [
            e for e in engines if e not in _ENGINE_PREFERENCE
        ]
        if not ordered:
            self.error = "No hay un motor de voz disponible en el sistema."
            return
        self._tts = QTextToSpeech(ordered[0], self)
        log.info("system speech engine: %s", ordered[0])
        if self._tts.state() == QTextToSpeech.State.Error:
            self.error = f"El motor de voz falló: {self._tts.errorString()}"
            self._tts = None

    @property
    def available(self) -> bool:
        return self._tts is not None

    def voices(self, language: str) -> list[str]:
        if self._tts is None:
            return []
        wanted = _QT_LANGUAGE[language]
        return [v.name() for v in self._tts.availableVoices() if v.locale().language() == wanted]

    def configure(self, language: str, voice_name: str | None) -> None:
        if self._tts is None:
            return
        wanted = _QT_LANGUAGE[language]
        candidates = [v for v in self._tts.availableVoices() if v.locale().language() == wanted]
        chosen = next((v for v in candidates if v.name() == voice_name), None)
        if chosen is None and candidates:
            chosen = candidates[0]
        self.matched = chosen is not None
        if chosen is not None:
            self._tts.setVoice(chosen)

    def voice_name(self) -> str | None:
        return self._tts.voice().name() if self._tts is not None else None

    def say(self, text: str) -> None:
        if self._tts is not None:
            self._tts.stop()
            self._tts.say(text)

    def stop(self) -> None:
        if self._tts is not None:
            self._tts.stop()


# ---------------------------------------------------------------- neural voices


class AudioPlayer(QObject):
    """Plays mono float samples; a new clip cuts the previous one."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._sink: QAudioSink | None = None
        self._buffer: QBuffer | None = None

    @property
    def available(self) -> bool:
        return QAudioSink is not None

    def play(self, audio: Audio) -> None:
        if QAudioSink is None:
            return
        self.stop()
        fmt = QAudioFormat()
        fmt.setSampleRate(audio.sample_rate)
        fmt.setChannelCount(1)
        fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
        # A short tail of silence: some devices drop the last few milliseconds.
        tail = np.zeros(audio.sample_rate // 10, dtype=np.float32)
        pcm = (np.clip(np.concatenate([audio.samples, tail]), -1.0, 1.0) * 32767).astype(np.int16)
        self._buffer = QBuffer(self)
        self._buffer.setData(QByteArray(pcm.tobytes()))
        self._buffer.open(QIODevice.OpenModeFlag.ReadOnly)
        self._sink = QAudioSink(QMediaDevices.defaultAudioOutput(), fmt, self)
        self._sink.start(self._buffer)

    def stop(self) -> None:
        if self._sink is not None:
            self._sink.stop()
            self._sink.deleteLater()
            self._sink = None
        if self._buffer is not None:
            self._buffer.close()
            self._buffer.deleteLater()
            self._buffer = None


class NeuralSpeaker(QObject):
    """Adapts a `Synthesizer` (blocking, numpy) to the `Speaker` strategy."""

    _rendered = Signal(object, int)  # Audio, request id

    _CACHE_SIZE = 64

    def __init__(self, synth: Synthesizer, player: AudioPlayer, parent: QObject | None = None):
        super().__init__(parent)
        self.synth = synth
        self._player = player
        self._voice: VoiceOption | None = None
        # One worker: models load once and phrases come out in order.
        self._worker = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix=f"tts-{synth.info.name}"
        )
        self._cache: OrderedDict[tuple[str, str], Audio] = OrderedDict()
        self._request = 0
        self._closing = False
        self.error = ""
        self._rendered.connect(self._on_rendered)

    def set_voice(self, voice: VoiceOption | None) -> None:
        if voice != self._voice:
            self._voice = voice
            self.error = ""
            if voice is not None:
                self._worker.submit(self._render, "jaque", voice, -1)  # loads the model

    def say(self, text: str) -> None:
        if self._voice is None:
            return
        self._request += 1
        self._player.stop()
        self._worker.submit(self._render, text, self._voice, self._request)

    def stop(self) -> None:
        self._request += 1
        self._player.stop()

    def _render(self, text: str, voice: VoiceOption, request: int) -> None:
        key = (voice.id, text)
        audio = self._cache.get(key)
        if audio is None:
            try:
                audio = self.synth.synthesize(text, voice)
            except Exception as exc:  # third-party code: report, never crash the app
                if self._closing:
                    return  # the interpreter is shutting down under the import
                log.exception("%s failed", self.synth.info.name)
                self.error = f"{self.synth.info.label} falló: {exc}"
                return
            self._cache[key] = audio
            while len(self._cache) > self._CACHE_SIZE:
                self._cache.popitem(last=False)
        if request >= 0:
            self._rendered.emit(audio, request)  # queued to the GUI thread

    def _on_rendered(self, audio: Audio, request: int) -> None:
        if request == self._request:  # a newer move superseded this one
            self._player.play(audio)

    def shutdown(self) -> None:
        self._closing = True
        self._worker.shutdown(wait=False, cancel_futures=True)


# ---------------------------------------------------------------- facade


class MoveVoice(QObject):
    install_progress = Signal(str, float)  # text, 0..1 (-1 = unknown)
    install_finished = Signal(bool, str)  # ok, message

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._system = SystemSpeaker(self)
        self._player = AudioPlayer(self)
        self._neural: dict[str, NeuralSpeaker] = {}
        self._engine = SYSTEM
        self._language = "es"
        self._voice_id: str | None = None
        self._cancel: threading.Event | None = None

    # ---- catalogue ------------------------------------------------------------

    def engines(self) -> list[EngineChoice]:
        system = EngineChoice(
            SYSTEM,
            "Sistema",
            "Las voces que ya trae el sistema operativo. No hay que descargar nada.",
            "",
            False,
        )
        return [system] + [
            EngineChoice(s.info.name, s.info.label, s.info.description, s.info.license_note, True)
            for s in SYNTHESIZERS
        ]

    @property
    def engine(self) -> str:
        return self._engine

    def voice_options(self) -> list[VoiceChoice]:
        neural = self._neural_speaker()
        if neural is None:
            return [VoiceChoice(n, n, True, 0) for n in self._system.voices(self._language)]
        synth = neural.synth
        return [
            VoiceChoice(v.id, v.label, (m := synth.missing(v)).empty, m.size_mb)
            for v in synth.voices_for(self._language)
        ]

    # ---- configuration --------------------------------------------------------

    def configure(self, engine: str, language: str, voice_id: str | None) -> None:
        self._engine = engine if engine in {e.name for e in self.engines()} else SYSTEM
        self._language = normalize_language(language)
        self._voice_id = voice_id
        self._system.configure(self._language, voice_id if self._engine == SYSTEM else None)
        neural = self._neural_speaker()
        if neural is not None:
            voice = neural.synth.find_voice(voice_id, self._language)
            ready = voice is not None and neural.synth.missing(voice).empty
            neural.set_voice(voice if ready else None)

    def _neural_speaker(self) -> NeuralSpeaker | None:
        if self._engine == SYSTEM:
            return None
        if self._engine not in self._neural:
            synth = create_synthesizer(self._engine)
            if synth is None:
                return None
            self._neural[self._engine] = NeuralSpeaker(synth, self._player, self)
        return self._neural[self._engine]

    def _selected_voice(self) -> VoiceOption | None:
        neural = self._neural_speaker()
        return neural.synth.find_voice(self._voice_id, self._language) if neural else None

    def pending_download(self) -> Download | None:
        """What the selected neural voice still needs; None when it can speak."""
        neural = self._neural_speaker()
        voice = self._selected_voice()
        if neural is None or voice is None:
            return None
        missing = neural.synth.missing(voice)
        return None if missing.empty else missing

    def _speaker(self) -> Speaker:
        neural = self._neural_speaker()
        if neural is not None and self.pending_download() is None and self._player.available:
            return neural
        return self._system

    # ---- state for the UI -----------------------------------------------------

    @property
    def available(self) -> bool:
        return self._system.available or self._neural_speaker() is not None

    def voice_name(self) -> str | None:
        neural = self._neural_speaker()
        voice = self._selected_voice()
        if neural is not None and voice is not None and self.pending_download() is None:
            return f"{neural.synth.info.label} · {voice.label}"
        return self._system.voice_name()

    def status(self) -> str:
        """Empty when everything is fine; otherwise what's wrong and what is used instead."""
        neural = self._neural_speaker()
        if neural is not None:
            if not self._player.available:
                return (
                    "Esta instalación de Qt no puede reproducir audio: se usa la voz del sistema."
                )
            if self.pending_download() is not None:
                label = neural.synth.info.label
                return f"Falta descargar {label}: mientras, se usa la voz del sistema."
            return neural.error
        if self._system.error:
            return self._system.error
        if not self._system.matched:
            name = "español" if self._language == "es" else "inglés"
            hint = _INSTALL_HINT.get(sys.platform, "Instalá una voz para ese idioma.")
            return f"No hay voces del sistema en {name}: se usa la voz por defecto. {hint}"
        return ""

    # ---- speaking -------------------------------------------------------------

    def say_move(self, san: str) -> str:
        """Speak a SAN move in the configured language; returns the phrase."""
        text = spoken_san(san, self._language)
        self._system.stop()
        for neural in self._neural.values():
            neural.stop()
        self._speaker().say(text)
        return text

    # ---- downloads ------------------------------------------------------------

    @property
    def installing(self) -> bool:
        return self._cancel is not None

    def start_install(self) -> None:
        neural = self._neural_speaker()
        download = self.pending_download()
        if neural is None or download is None or self._cancel is not None:
            return
        cancel = threading.Event()
        self._cancel = cancel
        folder = neural.synth.folder

        def worker() -> None:
            try:
                install(download, folder, self.install_progress.emit, cancel)
            except InstallError as exc:  # includes cancellation
                self._finish(False, str(exc))
            except Exception as exc:
                log.exception("voice install failed")
                self._finish(False, f"Falló la descarga: {exc}")
            else:
                self._finish(True, f"{neural.synth.info.label} listo.")

        threading.Thread(target=worker, name="voice-install", daemon=True).start()

    def _finish(self, ok: bool, message: str) -> None:
        self._cancel = None
        self.install_finished.emit(ok, message)

    def cancel_install(self) -> None:
        if self._cancel is not None:
            self._cancel.set()

    def shutdown(self) -> None:
        self.cancel_install()
        for neural in self._neural.values():
            neural.shutdown()
