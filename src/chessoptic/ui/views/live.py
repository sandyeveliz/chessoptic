"""'En vivo': health strip, status block, rectified camera with overlay, recent events."""

from __future__ import annotations

import chess
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from chessoptic.core.events import HealthState, InitialPositionCheck, OccupancyFrame
from chessoptic.ui.bridge import CoreBridge, UiFrames
from chessoptic.ui.theme import TOKENS
from chessoptic.ui.widgets.camera_view import CameraView
from chessoptic.ui.widgets.health_strip import HealthStrip


class LiveView(QWidget):
    recalibrate_requested = Signal()

    def __init__(self, bridge: CoreBridge, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)
        page = QWidget(self)
        scroll.setWidget(page)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        self._strip = HealthStrip(page)
        layout.addWidget(self._strip)

        self._status = QFrame(page)
        self._status.setObjectName("card")
        status_layout = QVBoxLayout(self._status)
        self._status_title = QLabel("Listo para seguir la partida", self._status)
        self._status_title.setStyleSheet(
            f"font-family: '{TOKENS.font_display}'; font-size: 15px; font-weight: 600;"
        )
        self._status_detail = QLabel("", self._status)
        self._status_detail.setObjectName("muted")
        self._status_detail.setWordWrap(True)
        status_layout.addWidget(self._status_title)
        status_layout.addWidget(self._status_detail)
        layout.addWidget(self._status)

        header = QHBoxLayout()
        label = QLabel("CÁMARA · VISTA RECTIFICADA", page)
        label.setObjectName("sectionLabel")
        header.addWidget(label)
        header.addStretch(1)
        self._confidence = QLabel("", page)
        self._confidence.setObjectName("sectionLabel")
        header.addWidget(self._confidence)
        layout.addLayout(header)

        self._camera = CameraView("rectified", page)
        layout.addWidget(self._camera)

        actions = QHBoxLayout()
        recalibrate = QPushButton("Recalibrar", page)
        recalibrate.setCursor(Qt.CursorShape.PointingHandCursor)
        recalibrate.clicked.connect(self.recalibrate_requested.emit)
        actions.addWidget(recalibrate)
        actions.addStretch(1)
        layout.addLayout(actions)
        layout.addStretch(1)

        bridge.health_changed.connect(self.set_health)
        bridge.frames_ready.connect(self._on_frames)
        bridge.occupancy.connect(self._on_occupancy)
        bridge.initial_check.connect(self._on_initial_check)
        bridge.calibration_changed.connect(
            lambda event: (
                self._camera.set_a1(event.calibration.a1_corner) if event.calibration else None
            )
        )

    def set_health(self, state: HealthState) -> None:
        self._strip.set_state(state)

    def _on_frames(self, frames: UiFrames) -> None:
        self._camera.set_frames(frames.raw, frames.rectified)

    def _on_occupancy(self, event: OccupancyFrame) -> None:
        self._camera.set_overlay(event.grid, event.confidence)
        self._confidence.setText(
            f"{event.mean_confidence:.0%}" + ("" if event.stable else " · MOVIENDO")
        )

    def _on_initial_check(self, check: InitialPositionCheck) -> None:
        if check.complete:
            self._status_title.setText("Posición inicial · 32 / 32")
            self._status_detail.setText(
                "Hacé la primera jugada en el tablero. "
                "(El seguimiento de jugadas llega en el hito H2.)"
            )
            self._camera.set_highlights({})
            return
        self._status_title.setText(f"Tablero · blancas {check.white}/16 · negras {check.black}/16")
        names = ", ".join(
            chess.square_name(s) for s in (check.missing + check.extra + check.wrong_color)[:8]
        )
        self._status_detail.setText(f"Casillas que no coinciden con la posición inicial: {names}.")
        highlights = {sq: "missing" for sq in check.missing}
        highlights.update({sq: "error" for sq in check.extra + check.wrong_color})
        self._camera.set_highlights(highlights)
