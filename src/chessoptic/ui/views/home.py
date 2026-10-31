"""'Inicio' tab: what's ready and what's missing. Only playing requires a calibrated camera."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from chessoptic.adapters import AVAILABLE
from chessoptic.capture.webcam import CameraInfo
from chessoptic.core.runtime import CoreRuntime
from chessoptic.ui.bridge import CoreBridge
from chessoptic.ui.theme import TOKENS
from chessoptic.ui.voice import MoveVoice

LEVEL_LABELS = {"good": "bueno", "fair": "justo", "poor": "insuficiente"}


class _StatusRow(QWidget):
    """Dot · title + detail · optional action link."""

    def __init__(self, title: str, action: str | None, parent: QWidget) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(10)
        self._dot = QLabel(self)
        self._dot.setFixedSize(12, 12)
        layout.addWidget(self._dot, 0, Qt.AlignmentFlag.AlignVCenter)
        text = QVBoxLayout()
        text.setSpacing(0)
        name = QLabel(title, self)
        name.setStyleSheet("font-weight: 600;")
        self._detail = QLabel("", self)
        self._detail.setObjectName("muted")
        self._detail.setWordWrap(True)
        text.addWidget(name)
        text.addWidget(self._detail)
        layout.addLayout(text, 1)
        self.action: QPushButton | None = None
        if action:
            self.action = QPushButton(action, self)
            self.action.setFlat(True)
            self.action.setCursor(Qt.CursorShape.PointingHandCursor)
            self.action.setStyleSheet(
                f"QPushButton {{ color: {TOKENS.turn}; font-weight: 600; border: 0; "
                "background: transparent; padding: 4px 0; }"
            )
            layout.addWidget(self.action)

    def set(self, level: str, detail: str, action: str | None = None) -> None:
        """level: 'ok' | 'warn' | 'idle'."""
        if level == "ok":
            style = f"background: {TOKENS.ok}; border-radius: 6px;"
        elif level == "warn":
            style = f"background: {TOKENS.warn}; border-radius: 6px;"
        else:
            style = f"border: 2px solid {TOKENS.line_strong}; border-radius: 6px;"
        self._dot.setStyleSheet(style)
        self._detail.setText(detail)
        if self.action is not None and action is not None:
            self.action.setText(action)


class HomeView(QWidget):
    play_requested = Signal()
    calibrate_requested = Signal()  # full setup from the camera step
    recheck_requested = Signal()  # detection check only
    settings_requested = Signal()
    _camera_opened = Signal()

    def __init__(
        self,
        runtime: CoreRuntime,
        bridge: CoreBridge,
        voice: MoveVoice,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._runtime = runtime
        self._voice = voice
        self._searching = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        title = QLabel("Inicio", self)
        title.setStyleSheet(
            f"font-family: '{TOKENS.font_display}'; font-size: 20px; font-weight: 700;"
        )
        layout.addWidget(title)
        self._summary = QLabel("", self)
        self._summary.setObjectName("muted")
        self._summary.setWordWrap(True)
        layout.addWidget(self._summary)

        label = QLabel("ESTADO", self)
        label.setObjectName("sectionLabel")
        layout.addWidget(label)
        card = QFrame(self)
        card.setObjectName("card")
        rows = QVBoxLayout(card)
        rows.setContentsMargins(12, 6, 12, 6)
        rows.setSpacing(2)
        self._camera = _StatusRow("Cámara", "Elegir", card)
        self._calibration = _StatusRow("Calibración", "Calibrar", card)
        self._detection = _StatusRow("Detección", "Rechequear", card)
        self._rival = _StatusRow("Rival", "Cambiar", card)
        self._voice_row = _StatusRow("Voz", "Probar", card)
        for row in (self._camera, self._calibration, self._detection, self._rival, self._voice_row):
            rows.addWidget(row)
        layout.addWidget(card)
        self._connect(self._camera, self.calibrate_requested.emit)
        self._connect(self._calibration, self.calibrate_requested.emit)
        self._connect(self._detection, self.recheck_requested.emit)
        self._connect(self._rival, self.settings_requested.emit)
        self._connect(self._voice_row, self._test_voice)

        self._play = QPushButton("Jugar", self)
        self._play.setProperty("primary", "true")
        self._play.setCursor(Qt.CursorShape.PointingHandCursor)
        self._play.setMinimumHeight(44)
        self._play.clicked.connect(self.play_requested.emit)
        layout.addWidget(self._play)
        self._play_hint = QLabel("Calibrá la cámara para habilitar la partida.", self)
        self._play_hint.setObjectName("muted")
        self._play_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._play_hint)
        self._calibrate = QPushButton("Calibrar cámara", self)
        self._calibrate.setCursor(Qt.CursorShape.PointingHandCursor)
        self._calibrate.setMinimumHeight(44)
        self._calibrate.clicked.connect(self.calibrate_requested.emit)
        layout.addWidget(self._calibrate)
        layout.addStretch(1)

        self._camera_opened.connect(self.refresh)
        bridge.camera_status.connect(lambda _e: self.refresh())
        bridge.calibration_changed.connect(lambda _e: self.refresh())
        bridge.classifier_trained.connect(lambda _e: self.refresh())
        self.refresh()

    @staticmethod
    def _connect(row: _StatusRow, slot: Callable[[], None]) -> None:
        if row.action is not None:
            row.action.clicked.connect(lambda _=False: slot())

    # ---- startup -------------------------------------------------------------

    def open_saved_camera(self) -> None:
        """Reopen the last camera in the background; its saved profile comes with it."""
        saved = self._runtime.config.camera
        if saved is None or self._runtime.camera_is_open():
            return
        self._searching = True
        self.refresh()

        def done(cameras: list[CameraInfo]) -> None:
            info = next((c for c in cameras if c.key == saved), None)
            if info is not None:
                self._runtime.open_camera(info)
            self._searching = False
            self._camera_opened.emit()  # thread-safe: queued to the GUI thread

        self._runtime.list_cameras_async(done)  # runs `done` on its worker thread

    # ---- state ---------------------------------------------------------------

    def ready_to_play(self) -> bool:
        classifier = self._runtime.pipeline.classifier
        return (
            self._runtime.camera_is_open()
            and self._runtime.calibration is not None
            and classifier is not None
            and classifier.trained
        )

    def refresh(self) -> None:
        runtime = self._runtime
        camera_open = runtime.camera_is_open()
        if camera_open and runtime.camera is not None:
            self._camera.set("ok", runtime.camera.label, "Cambiar")
        elif self._searching:
            self._camera.set("idle", "Buscando la cámara guardada…", "Elegir")
        elif runtime.config.camera:
            self._camera.set(
                "warn",
                "No se encontró la cámara guardada (¿desconectada o en uso por otra app?)",
                "Elegir",
            )
        else:
            self._camera.set("warn", "Todavía no elegiste una cámara", "Elegir")

        profile = runtime.profile
        if camera_open and runtime.calibration is not None:
            when = f"Guardada el {profile.updated[:10]}" if profile is not None else "Sin guardar"
            self._calibration.set("ok", when, "Recalibrar")
        else:
            self._calibration.set("warn", "No hay calibración para esta cámara", "Calibrar")

        classifier = runtime.pipeline.classifier
        trained = classifier is not None and classifier.trained
        if trained and profile is not None and profile.check_level:
            level = LEVEL_LABELS.get(profile.check_level, profile.check_level)
            self._detection.set("ok" if profile.check_level != "poor" else "warn", f"Nivel {level}")
        elif trained:
            self._detection.set("ok", "Piezas aprendidas")
        else:
            self._detection.set("idle", "Se chequea al calibrar")
        if self._detection.action is not None:
            self._detection.action.setVisible(trained)

        self._rival.set(*self._rival_status())

        status = self._voice.status()
        speak = runtime.config.speak_opponent_moves
        if not self._voice.available:
            self._voice_row.set("warn", status)
        else:
            name = self._voice.voice_name() or "voz por defecto"
            lang = "Español" if runtime.config.notation_language == "es" else "English"
            detail = f"{lang} · {name}" + ("" if speak else " · apagada")
            self._voice_row.set("warn" if status else "ok", detail)

        ready = self.ready_to_play()
        self._play.setEnabled(ready)
        self._play_hint.setVisible(not ready)
        self._calibrate.setVisible(not ready)
        self._summary.setText(
            "Todo listo. Armá la posición inicial y empezá la partida."
            if ready
            else "Podés revisar ajustes, voz y log sin calibrar. "
            "Para jugar hace falta la cámara calibrada."
        )

    def _rival_status(self) -> tuple[str, str]:
        config = self._runtime.config
        label = next((i.label for i in AVAILABLE if i.name == config.provider), config.provider)
        if config.provider == "stockfish":
            from chessoptic.adapters.local.stockfish import find_stockfish

            color = "blancas" if config.my_color == "white" else "negras"
            if find_stockfish(config) is None:
                return "warn", f"{label} · no encontrado, indicá la ruta en Ajustes"
            return "ok", f"{label} · nivel {config.stockfish_level} · jugás con {color}"
        return "ok", label

    def _test_voice(self) -> None:
        from chessoptic.game.notation import random_example_san

        self._voice.say_move(random_example_san())
