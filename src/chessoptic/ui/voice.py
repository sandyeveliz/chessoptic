"""MoveVoice: reads moves aloud with the OS speech engine through Qt TextToSpeech.

No extra dependency: PySide6 ships QtTextToSpeech, backed by WinRT/SAPI on Windows,
AVSpeechSynthesizer on macOS and speech-dispatcher/flite on Linux. The voices are whatever
the OS has installed, so a language may have none; `status()` explains what to install.
"""

from __future__ import annotations

import logging
import sys

from PySide6.QtCore import QLocale, QObject

from chessoptic.game.notation import normalize_language, spoken_san

log = logging.getLogger(__name__)

try:
    from PySide6.QtTextToSpeech import QTextToSpeech
except ImportError:  # some Linux PySide6 builds ship without the module
    QTextToSpeech = None  # type: ignore[assignment,misc]

# Best engine first; "mock" is Qt's test backend and never speaks.
_ENGINE_PREFERENCE = ("winrt", "sapi", "darwin", "speechd", "flite", "android")
_QT_LANGUAGE = {"es": QLocale.Language.Spanish, "en": QLocale.Language.English}
_INSTALL_HINT = {
    "win32": "Instalá una voz desde Configuración > Hora e idioma > Voz > Agregar voces.",
    "darwin": "Instalá una voz desde Ajustes del Sistema > Accesibilidad > Contenido leído.",
}


class MoveVoice(QObject):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._tts: QTextToSpeech | None = None
        self._error = ""
        self._language = "es"
        self._matched = False
        if QTextToSpeech is None:
            self._error = "Esta instalación de Qt no incluye síntesis de voz."
            return
        engines = [e for e in QTextToSpeech.availableEngines() if e != "mock"]
        ordered = [e for e in _ENGINE_PREFERENCE if e in engines] + [
            e for e in engines if e not in _ENGINE_PREFERENCE
        ]
        if not ordered:
            self._error = "No hay un motor de voz disponible en el sistema."
            return
        self._tts = QTextToSpeech(ordered[0], self)
        log.info("speech engine: %s", ordered[0])
        if self._tts.state() == QTextToSpeech.State.Error:
            self._error = f"El motor de voz falló: {self._tts.errorString()}"
            self._tts = None

    @property
    def available(self) -> bool:
        return self._tts is not None

    def voices(self, language: str) -> list[str]:
        """Installed voice names for a notation language ('es' / 'en')."""
        if self._tts is None:
            return []
        wanted = _QT_LANGUAGE[normalize_language(language)]
        return [v.name() for v in self._tts.availableVoices() if v.locale().language() == wanted]

    def configure(self, language: str, voice_name: str | None) -> None:
        """Pick the named voice, or the first one for the language, or leave the default."""
        self._language = normalize_language(language)
        if self._tts is None:
            return
        wanted = _QT_LANGUAGE[self._language]
        candidates = [v for v in self._tts.availableVoices() if v.locale().language() == wanted]
        chosen = next((v for v in candidates if v.name() == voice_name), None)
        if chosen is None and candidates:
            chosen = candidates[0]
        self._matched = chosen is not None
        if chosen is not None:
            self._tts.setVoice(chosen)

    def status(self) -> str:
        """Empty when the configured language has a voice; otherwise what's wrong."""
        if self._error:
            return self._error
        if not self._matched:
            name = "español" if self._language == "es" else "inglés"
            hint = _INSTALL_HINT.get(sys.platform, "Instalá una voz para ese idioma.")
            return f"No hay voces en {name}: se usa la voz por defecto. {hint}"
        return ""

    def say_move(self, san: str) -> str:
        """Speak a SAN move in the configured language; returns the phrase."""
        text = spoken_san(san, self._language)
        if self._tts is not None:
            # A new move interrupts whatever was being said.
            self._tts.stop()
            self._tts.say(text)
        return text
