"""First-run wizard: camera, framing, corners, initial position, check, move test, provider."""

from __future__ import annotations

import threading

import chess
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from chessoptic.capture.webcam import CameraInfo
from chessoptic.core.events import (
    CamerasListed,
    CheckLevel,
    ClassifierTrained,
    InitialPositionCheck,
    MoveTestProgress,
    MoveTestStage,
    OccupancyFrame,
    SetupCheckReport,
)
from chessoptic.core.runtime import CoreRuntime
from chessoptic.ui.bridge import CoreBridge, UiFrames
from chessoptic.ui.theme import TOKENS
from chessoptic.ui.widgets.camera_view import CameraView
from chessoptic.ui.widgets.stepper import Stepper
from chessoptic.vision.calibration import (
    A1_CORNERS,
    A1_LABELS,
    Calibration,
    Corner,
    default_corners,
)

STEP_TITLES = (
    "Cámara",
    "Encuadre",
    "Esquinas",
    "Posición inicial",
    "Chequeo de detección",
    "Prueba de jugada",
    "Proveedor",
)

PROVIDERS: tuple[tuple[str, str], ...] = (
    ("tracking", "Solo seguimiento (anotar la partida)"),
    ("stockfish", "Stockfish local"),
    ("lichess", "Lichess (próximamente)"),
    ("chesscom", "chess.com vía Chessconnect (próximamente)"),
)

LEVEL_TEXT: dict[CheckLevel, tuple[str, str]] = {
    CheckLevel.GOOD: ("Bien", TOKENS.ok),
    CheckLevel.FAIR: ("Justo", TOKENS.warn),
    CheckLevel.POOR: ("Insuficiente", TOKENS.err),
}


def _section(text: str, parent: QWidget) -> QLabel:
    label = QLabel(text.upper(), parent)
    label.setObjectName("sectionLabel")
    return label


def _title(text: str, parent: QWidget) -> QLabel:
    label = QLabel(text, parent)
    label.setStyleSheet(f"font-family: '{TOKENS.font_display}'; font-size: 17px; font-weight: 600;")
    label.setWordWrap(True)
    return label


def _muted(text: str, parent: QWidget) -> QLabel:
    label = QLabel(text, parent)
    label.setObjectName("muted")
    label.setWordWrap(True)
    return label


def _button(text: str, parent: QWidget, primary: bool = False) -> QPushButton:
    button = QPushButton(text, parent)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    if primary:
        button.setProperty("primary", "true")
    return button


def square_name(square: int) -> str:
    return chess.square_name(square)


class WizardView(QWidget):
    finished = Signal()
    _camera_opened = Signal(object, bool)

    def __init__(
        self, runtime: CoreRuntime, bridge: CoreBridge, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._camera_opened.connect(self._camera_opened_ui)
        self._runtime = runtime
        self._bridge = bridge
        self._cameras: list[CameraInfo] = []
        self._frames: UiFrames | None = None
        self._corners: tuple[Corner, Corner, Corner, Corner] | None = None
        self._a1 = "bottom-left"
        self._check_level: CheckLevel | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(10)

        self._stepper = Stepper(len(STEP_TITLES), self)
        root.addWidget(self._stepper)
        self._step_label = _muted("", self)
        root.addWidget(self._step_label)

        self._stack = QStackedWidget(self)
        root.addWidget(self._stack, 1)
        for builder in (
            self._build_camera_step,
            self._build_framing_step,
            self._build_corners_step,
            self._build_initial_step,
            self._build_check_step,
            self._build_move_test_step,
            self._build_provider_step,
        ):
            page = QWidget(self)
            builder(page)
            scroll = QScrollArea(self)
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setWidget(page)
            self._stack.addWidget(scroll)

        bridge.cameras_listed.connect(self._on_cameras)
        bridge.frames_ready.connect(self._on_frames)
        bridge.classifier_trained.connect(self._on_trained)
        bridge.initial_check.connect(self._on_initial_check)
        bridge.occupancy.connect(self._on_occupancy)
        bridge.setup_check.connect(self._on_setup_check)
        bridge.move_test.connect(self._on_move_test)

    # ---- navigation ---------------------------------------------------------

    def start(self, step: int = 0) -> None:
        self.go_to(step)
        if step == 0:
            self._runtime.list_cameras_async()
            self._camera_hint.setText("Buscando cámaras…")

    def go_to(self, index: int) -> None:
        previous = self._stack.currentIndex()
        if previous == 5:
            self._runtime.stop_move_test()
        self._stack.setCurrentIndex(index)
        self._stepper.set_current(index)
        self._step_label.setText(f"Paso {index + 1} de {len(STEP_TITLES)} · {STEP_TITLES[index]}")
        if index == 2:
            self._enter_corners()
        elif index == 3:
            self._enter_initial()
        elif index == 4:
            self._enter_check()
        elif index == 5:
            self._enter_move_test()

    # ---- step 1: camera -----------------------------------------------------

    def _build_camera_step(self, page: QWidget) -> None:
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(_title("Preparando el tablero", page))
        layout.addWidget(
            _muted("ChessOptic revisa cámara, calibración y tablero antes de jugar.", page)
        )
        layout.addWidget(_section("Cámara", page))
        self._camera_combo = QComboBox(page)
        self._camera_combo.currentIndexChanged.connect(self._on_camera_selected)
        layout.addWidget(self._camera_combo)
        self._camera_preview = CameraView("raw", page)
        self._camera_preview.set_placeholder("Vista previa de la cámara")
        layout.addWidget(self._camera_preview)
        self._camera_hint = _muted("", page)
        layout.addWidget(self._camera_hint)
        self._use_saved = _button("Usar la calibración guardada", page)
        self._use_saved.clicked.connect(lambda: self.go_to(3))
        self._use_saved.hide()
        layout.addWidget(self._use_saved)
        self._use_camera = _button("Usar esta cámara y calibrar", page, primary=True)
        self._use_camera.setEnabled(False)
        self._use_camera.clicked.connect(lambda: self.go_to(1))
        layout.addWidget(self._use_camera)
        layout.addWidget(
            _muted(
                "¿No aparece tu cámara? Revisá los permisos del sistema o corré "
                "`chessoptic doctor`.",
                page,
            )
        )
        layout.addStretch(1)

    def _on_cameras(self, event: CamerasListed) -> None:
        self._cameras = list(event.cameras)
        self._camera_combo.blockSignals(True)
        self._camera_combo.clear()
        for info in self._cameras:
            self._camera_combo.addItem(info.label, info)
        self._camera_combo.blockSignals(False)
        if not self._cameras:
            self._camera_hint.setText("No se encontró ninguna cámara.")
            return
        self._camera_hint.setText(f"{len(self._cameras)} cámara(s) encontrada(s).")
        preferred = next(
            (i for i, c in enumerate(self._cameras) if c.key == self._runtime.config.camera), 0
        )
        self._camera_combo.setCurrentIndex(preferred)
        self._on_camera_selected(preferred)

    def _on_camera_selected(self, index: int) -> None:
        if index < 0 or index >= len(self._cameras):
            return
        info = self._cameras[index]
        self._use_camera.setEnabled(False)
        self._camera_hint.setText(f"Abriendo {info.name}…")

        def worker() -> None:
            ok = self._runtime.open_camera(info)
            # Signals are thread-safe: Qt queues the slot on the GUI thread.
            self._camera_opened.emit(info, ok)

        threading.Thread(target=worker, name="open-camera", daemon=True).start()

    def _camera_opened_ui(self, info: CameraInfo, ok: bool) -> None:
        if not ok:
            self._camera_hint.setText(f"No se pudo abrir {info.name}.")
            return
        self._use_camera.setEnabled(True)
        has_profile = self._runtime.has_profile(info)
        self._use_saved.setVisible(has_profile)
        self._camera_hint.setText(
            "Hay una calibración guardada para esta cámara." if has_profile else "Cámara lista."
        )

    # ---- step 2: framing ----------------------------------------------------

    def _build_framing_step(self, page: QWidget) -> None:
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(_title("Encuadrá el tablero", page))
        self._framing_view = CameraView("raw", page)
        self._framing_view.set_guide(True)
        layout.addWidget(self._framing_view)
        tips = QFrame(page)
        tips.setObjectName("card")
        tips_layout = QVBoxLayout(tips)
        for text in (
            "• El tablero entero dentro de la guía, ocupando la mayor parte de la imagen.",
            "• Cámara fija: si se mueve después, hay que recalibrar.",
            "• Luz pareja, sin ventana de fondo ni sombras largas.",
            "• Desde arriba es lo más fácil; en diagonal funciona si no es muy baja.",
        ):
            tips_layout.addWidget(_muted(text, tips))
        layout.addWidget(tips)
        row = QHBoxLayout()
        back = _button("Atrás", page)
        back.clicked.connect(lambda: self.go_to(0))
        nxt = _button("Continuar", page, primary=True)
        nxt.clicked.connect(lambda: self.go_to(2))
        row.addWidget(back)
        row.addWidget(nxt, 1)
        layout.addLayout(row)
        layout.addStretch(1)

    # ---- step 3: corners ----------------------------------------------------

    def _build_corners_step(self, page: QWidget) -> None:
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(_title("Marcá las 4 esquinas", page))
        layout.addWidget(
            _muted("Arrastrá las manijas a las esquinas exteriores de la zona de juego.", page)
        )
        self._corner_view = CameraView("raw", page)
        self._corner_view.set_editable(True)
        self._corner_view.corners_changed.connect(self._on_corners_dragged)
        self._corner_view.corner_drag_finished.connect(self._on_corners_dropped)
        layout.addWidget(self._corner_view)
        layout.addWidget(_section("Vista rectificada", page))
        self._corner_preview = CameraView("rectified", page)
        self._corner_preview.setMaximumHeight(200)
        layout.addWidget(self._corner_preview)
        layout.addWidget(_section("¿Dónde está la casilla a1?", page))
        self._a1_group = QButtonGroup(page)
        for key in A1_CORNERS:
            radio = QRadioButton(A1_LABELS[key], page)
            radio.setProperty("a1", key)
            radio.setChecked(key == self._a1)
            self._a1_group.addButton(radio)
            layout.addWidget(radio)
        self._a1_group.buttonClicked.connect(self._on_a1_changed)
        row = QHBoxLayout()
        back = _button("Atrás", page)
        back.clicked.connect(lambda: self.go_to(1))
        confirm = _button("Confirmar esquinas", page, primary=True)
        confirm.clicked.connect(lambda: self.go_to(3))
        row.addWidget(back)
        row.addWidget(confirm, 1)
        layout.addLayout(row)
        layout.addStretch(1)

    def _enter_corners(self) -> None:
        calibration = self._runtime.calibration
        if calibration is not None:
            self._corners = calibration.corners
            self._a1 = calibration.a1_corner
        elif self._frames is not None:
            size = (self._frames.raw.width(), self._frames.raw.height())
            self._corners = default_corners(size)
        if self._corners is not None:
            self._corner_view.set_corners(self._corners)
            self._push_calibration()
        for button in self._a1_group.buttons():
            button.setChecked(button.property("a1") == self._a1)
        self._corner_preview.set_a1(self._a1)

    def _on_corners_dragged(self, corners: object) -> None:
        self._corners = corners  # type: ignore[assignment]

    def _on_corners_dropped(self, corners: object) -> None:
        self._corners = corners  # type: ignore[assignment]
        self._push_calibration()

    def _on_a1_changed(self, button: QRadioButton) -> None:
        self._a1 = str(button.property("a1"))
        self._corner_preview.set_a1(self._a1)
        self._push_calibration()

    def _push_calibration(self) -> None:
        if self._corners is None or self._frames is None:
            return
        size = (self._frames.raw.width(), self._frames.raw.height())
        self._runtime.set_calibration(Calibration(self._corners, self._a1, size))

    # ---- step 4: initial position --------------------------------------------

    def _build_initial_step(self, page: QWidget) -> None:
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(_title("Armá la posición inicial", page))
        self._initial_hint = _muted("Poné las 32 piezas y sacá la mano del encuadre.", page)
        layout.addWidget(self._initial_hint)
        counters = QHBoxLayout()
        self._white_count = QLabel("Blancas —", page)
        self._black_count = QLabel("Negras —", page)
        for label in (self._white_count, self._black_count):
            label.setObjectName("mono")
            counters.addWidget(label)
        layout.addLayout(counters)
        self._initial_view = CameraView("rectified", page)
        layout.addWidget(self._initial_view)
        row = QHBoxLayout()
        back = _button("Esquinas", page)
        back.clicked.connect(lambda: self.go_to(2))
        retrain = _button("Volver a aprender", page)
        retrain.clicked.connect(self._enter_initial)
        self._initial_next = _button("Continuar", page, primary=True)
        self._initial_next.setEnabled(False)
        self._initial_next.clicked.connect(lambda: self.go_to(4))
        row.addWidget(back)
        row.addWidget(retrain)
        row.addWidget(self._initial_next, 1)
        layout.addLayout(row)
        layout.addStretch(1)

    def _enter_initial(self) -> None:
        self._initial_view.set_a1(self._a1)
        self._initial_view.set_overlay(None, None)
        self._initial_view.set_highlights({})
        self._initial_next.setEnabled(False)
        self._initial_hint.setText(
            "Aprendiendo cómo se ven tus piezas… esperando una imagen quieta."
        )
        self._white_count.setText("Blancas —")
        self._black_count.setText("Negras —")
        self._runtime.arm_initial_training()

    def _on_trained(self, event: ClassifierTrained) -> None:
        if event.trained and self._stack.currentIndex() == 3:
            self._initial_hint.setText("Listo. Revisá que las 32 piezas se vean en su lugar.")

    def _on_initial_check(self, check: InitialPositionCheck) -> None:
        self._white_count.setText(f"Blancas {check.white} / 16")
        self._black_count.setText(f"Negras {check.black} / 16")
        highlights = {sq: "missing" for sq in check.missing}
        highlights.update({sq: "error" for sq in check.extra + check.wrong_color})
        self._initial_view.set_highlights(highlights)
        self._initial_next.setEnabled(check.complete)
        if self._stack.currentIndex() != 3:
            return
        if check.complete:
            self._initial_hint.setText("Posición inicial completa: 32 / 32.")
        else:
            parts = []
            if check.missing:
                parts.append("faltan " + ", ".join(square_name(s) for s in check.missing[:6]))
            if check.extra:
                parts.append("sobran " + ", ".join(square_name(s) for s in check.extra[:6]))
            if check.wrong_color:
                parts.append(
                    "color dudoso en " + ", ".join(square_name(s) for s in check.wrong_color[:6])
                )
            self._initial_hint.setText("Casillas marcadas: " + "; ".join(parts) + ".")

    # ---- step 5: detection check -------------------------------------------------

    def _build_check_step(self, page: QWidget) -> None:
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(_title("¿Coincide con tu tablero?", page))
        layout.addWidget(
            _muted(
                "Los círculos son las piezas que ChessOptic ve. "
                "Las casillas con borde rojo son dudosas.",
                page,
            )
        )
        self._check_view = CameraView("rectified", page)
        layout.addWidget(self._check_view)
        answer = QHBoxLayout()
        no = _button("No coincide", page)
        no.clicked.connect(self._check_no)
        yes = _button("Sí, coincide", page, primary=True)
        yes.clicked.connect(self._check_yes)
        answer.addWidget(no)
        answer.addWidget(yes, 1)
        layout.addLayout(answer)
        self._report_card = QFrame(page)
        self._report_card.setObjectName("card")
        self._report_layout = QVBoxLayout(self._report_card)
        self._report_card.hide()
        layout.addWidget(self._report_card)
        row = QHBoxLayout()
        retry = _button("Reintentar", page)
        retry.clicked.connect(self._enter_check)
        corners = _button("Esquinas", page)
        corners.clicked.connect(lambda: self.go_to(2))
        self._check_next = _button("Continuar", page, primary=True)
        self._check_next.clicked.connect(lambda: self.go_to(5))
        row.addWidget(retry)
        row.addWidget(corners)
        row.addWidget(self._check_next, 1)
        layout.addLayout(row)
        layout.addStretch(1)

    def _enter_check(self) -> None:
        self._check_view.set_a1(self._a1)
        self._report_card.hide()
        self._check_next.setText("Continuar")
        self._runtime.run_setup_check()

    def _check_yes(self) -> None:
        self._report_card.show()

    def _check_no(self) -> None:
        self._report_card.show()
        self._add_report_line(
            "Si las piezas no aparecen donde están, suele ser contraste o luz. Revisá los "
            "hallazgos, corregí y volvé a 'Posición inicial' para que aprenda de nuevo.",
            TOKENS.err,
        )

    def _add_report_line(self, text: str, color: str | None = None) -> None:
        label = QLabel(text, self._report_card)
        label.setWordWrap(True)
        if color:
            label.setStyleSheet(f"color: {color};")
        self._report_layout.addWidget(label)

    def _on_setup_check(self, report: SetupCheckReport) -> None:
        self._check_level = report.level
        while self._report_layout.count():
            item = self._report_layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()
        text, color = LEVEL_TEXT[report.level]
        head = QLabel(
            f"Detección: {text} · confianza media {report.mean_confidence:.0%}", self._report_card
        )
        head.setStyleSheet(f"font-weight: 600; color: {color};")
        self._report_layout.addWidget(head)
        if not report.findings:
            self._add_report_line("Sin problemas detectados con esta cámara, tablero y luz.")
        for finding in report.findings:
            self._add_report_line(f"• {finding.message}")
            self._add_report_line(f"   → {finding.action}", TOKENS.muted)
        self._report_card.show()
        self._check_view.set_highlights({sq: "error" for sq in report.suspicious})
        self._check_next.setText(
            "Continuar" if report.level == CheckLevel.GOOD else "Continuar igual"
        )

    # ---- step 6: move test -------------------------------------------------------

    def _build_move_test_step(self, page: QWidget) -> None:
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(_title("Probá una jugada", page))
        self._move_hint = _muted("", page)
        layout.addWidget(self._move_hint)
        self._move_big = QLabel("e2–e4", page)
        self._move_big.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._move_big.setStyleSheet(
            f"font-family: '{TOKENS.font_mono}'; font-size: 34px; font-weight: 600; "
            f"color: {TOKENS.turn};"
        )
        layout.addWidget(self._move_big)
        self._move_latency = _muted("", page)
        self._move_latency.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._move_latency)
        self._move_view = CameraView("rectified", page)
        layout.addWidget(self._move_view)
        row = QHBoxLayout()
        retry = _button("Reintentar", page)
        retry.clicked.connect(self._enter_move_test)
        self._move_next = _button("Listo", page, primary=True)
        self._move_next.setEnabled(False)
        self._move_next.clicked.connect(lambda: self.go_to(6))
        skip = _button("Saltar", page)
        skip.clicked.connect(lambda: self.go_to(6))
        row.addWidget(retry)
        row.addWidget(skip)
        row.addWidget(self._move_next, 1)
        layout.addLayout(row)
        layout.addStretch(1)

    def _enter_move_test(self) -> None:
        self._move_view.set_a1(self._a1)
        self._move_view.set_highlights({chess.E2: "origin", chess.E4: "destination"})
        self._move_hint.setText("Mové el peón de e2 a e4, soltalo y sacá la mano.")
        self._move_latency.setText("")
        self._move_next.setEnabled(False)
        self._runtime.start_move_test()

    def _on_move_test(self, progress: MoveTestProgress) -> None:
        self._move_hint.setText(progress.detail)
        if progress.latency_ms is not None:
            self._move_latency.setText(f"detectada {progress.latency_ms:.0f} ms después de soltar")
        if progress.stage == MoveTestStage.WAITING_BACK:
            self._move_view.set_highlights({chess.E4: "origin", chess.E2: "destination"})
        elif progress.stage == MoveTestStage.DONE:
            self._move_view.set_highlights({})
            self._move_next.setEnabled(True)

    # ---- step 7: provider ---------------------------------------------------------

    def _build_provider_step(self, page: QWidget) -> None:
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(_title("¿Con quién jugás?", page))
        layout.addWidget(_section("Proveedor", page))
        from chessoptic.adapters.local.stockfish import find_stockfish

        stockfish_found = find_stockfish(self._runtime.config) is not None
        self._provider_group = QButtonGroup(page)
        for key, label in PROVIDERS:
            enabled = key == "tracking" or (key == "stockfish" and stockfish_found)
            if key == "stockfish" and not stockfish_found:
                label += " (no encontrado: instalalo o indicá la ruta en Ajustes)"
            radio = QRadioButton(label, page)
            radio.setProperty("provider", key)
            radio.setEnabled(enabled)
            radio.setChecked(key == self._runtime.config.provider and enabled)
            self._provider_group.addButton(radio)
            layout.addWidget(radio)
        if self._provider_group.checkedButton() is None:
            self._provider_group.buttons()[0].setChecked(True)
        self._provider_group.buttonClicked.connect(self._on_provider_choice)
        self._color_box = QWidget(page)
        color_layout = QHBoxLayout(self._color_box)
        color_layout.setContentsMargins(0, 0, 0, 0)
        color_layout.addWidget(QLabel("Jugás con:", self._color_box))
        self._color_group = QButtonGroup(self._color_box)
        for key, label in (("white", "Blancas"), ("black", "Negras")):
            radio = QRadioButton(label, self._color_box)
            radio.setProperty("color", key)
            radio.setChecked(key == self._runtime.config.my_color)
            self._color_group.addButton(radio)
            color_layout.addWidget(radio)
        color_layout.addStretch(1)
        layout.addWidget(self._color_box)
        self._color_box.setVisible(self._runtime.config.provider == "stockfish")
        layout.addWidget(
            _muted(
                "En 'Solo seguimiento' ChessOptic anota lo que pasa en el tablero "
                "y lo exporta como PGN. Con Stockfish, el nivel se ajusta en Ajustes.",
                page,
            )
        )
        row = QHBoxLayout()
        back = _button("Atrás", page)
        back.clicked.connect(lambda: self.go_to(5))
        start = _button("Empezar", page, primary=True)
        start.clicked.connect(self._finish)
        row.addWidget(back)
        row.addWidget(start, 1)
        layout.addLayout(row)
        layout.addStretch(1)

    def _on_provider_choice(self, button: QRadioButton) -> None:
        self._color_box.setVisible(str(button.property("provider")) == "stockfish")

    def _finish(self) -> None:
        button = self._provider_group.checkedButton()
        provider = str(button.property("provider")) if button is not None else "tracking"
        color_button = self._color_group.checkedButton()
        if color_button is not None:
            self._runtime.config.my_color = str(color_button.property("color"))
        level = str(self._check_level) if self._check_level is not None else None
        self._runtime.finish_setup(provider, level)
        self.finished.emit()

    # ---- shared frame / overlay updates ----------------------------------------

    def _on_frames(self, frames: UiFrames) -> None:
        self._frames = frames
        for view in (self._camera_preview, self._framing_view, self._corner_view):
            view.set_frames(frames.raw, frames.rectified)
        for view in (self._corner_preview, self._initial_view, self._check_view, self._move_view):
            view.set_frames(frames.raw, frames.rectified)

    def _on_occupancy(self, event: OccupancyFrame) -> None:
        for view in (self._initial_view, self._check_view, self._move_view):
            view.set_overlay(event.grid, event.confidence)
            view.set_caption(
                f"confianza {event.mean_confidence:.0%}" + ("" if event.stable else " · moviendo")
            )
