"""'Cámara' tab: device, raw/rectified view, recalibrate, best-effort exposure/focus lock."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from chessoptic.core.events import CalibrationChanged, CameraStatus, OccupancyFrame
from chessoptic.core.runtime import CoreRuntime
from chessoptic.ui.bridge import CoreBridge, UiFrames
from chessoptic.ui.widgets.camera_view import CameraView


class CameraTab(QWidget):
    recalibrate_requested = Signal()
    recheck_requested = Signal()

    def __init__(
        self, runtime: CoreRuntime, bridge: CoreBridge, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._runtime = runtime
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
        layout.setSpacing(10)

        title = QLabel("CÁMARA", page)
        title.setObjectName("sectionLabel")
        layout.addWidget(title)
        self._device = QLabel("—", page)
        layout.addWidget(self._device)

        modes = QHBoxLayout()
        self._mode_group = QButtonGroup(page)
        for key, label in (("rectified", "Rectificada"), ("raw", "Cruda")):
            radio = QRadioButton(label, page)
            radio.setProperty("mode", key)
            radio.setChecked(key == "rectified")
            self._mode_group.addButton(radio)
            modes.addWidget(radio)
        modes.addStretch(1)
        layout.addLayout(modes)

        self._view = CameraView("rectified", page)
        layout.addWidget(self._view)
        self._mode_group.buttonClicked.connect(
            lambda b: self._view.set_mode(str(b.property("mode")))
        )

        locks = QFrame(page)
        locks.setObjectName("card")
        locks_layout = QVBoxLayout(locks)
        hint = QLabel(
            "Fijar enfoque y exposición evita falsos positivos. Depende de la cámara y del "
            "sistema; si no tiene efecto, usá el software del fabricante.",
            locks,
        )
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        locks_layout.addWidget(hint)
        self._autofocus = QCheckBox("Autoenfoque", locks)
        self._autofocus.setChecked(True)
        self._autofocus.toggled.connect(lambda on: runtime.set_camera_auto("focus", on))
        self._autoexposure = QCheckBox("Autoexposición", locks)
        self._autoexposure.setChecked(True)
        self._autoexposure.toggled.connect(lambda on: runtime.set_camera_auto("exposure", on))
        locks_layout.addWidget(self._autofocus)
        locks_layout.addWidget(self._autoexposure)
        layout.addWidget(locks)

        actions = QHBoxLayout()
        recalibrate = QPushButton("Recalibrar", page)
        recalibrate.setCursor(Qt.CursorShape.PointingHandCursor)
        recalibrate.clicked.connect(self.recalibrate_requested.emit)
        recheck = QPushButton("Verificar detección", page)
        recheck.setCursor(Qt.CursorShape.PointingHandCursor)
        recheck.clicked.connect(self.recheck_requested.emit)
        actions.addWidget(recalibrate)
        actions.addWidget(recheck)
        layout.addLayout(actions)
        layout.addStretch(1)

        bridge.frames_ready.connect(self._on_frames)
        bridge.occupancy.connect(self._on_occupancy)
        bridge.camera_status.connect(self._on_status)
        bridge.calibration_changed.connect(self._on_calibration)

    def _on_calibration(self, event: CalibrationChanged) -> None:
        if event.calibration is None:
            self._view.set_corners(None)
            return
        self._view.set_a1(event.calibration.a1_corner)
        self._view.set_corners(event.calibration.corners)

    def _on_frames(self, frames: UiFrames) -> None:
        self._view.set_frames(frames.raw, frames.rectified)

    def _on_occupancy(self, event: OccupancyFrame) -> None:
        self._view.set_overlay(event.grid, event.confidence)
        self._view.set_caption(f"confianza {event.mean_confidence:.0%}")

    def _on_status(self, status: CameraStatus) -> None:
        self._device.setText(f"{status.device or 'sin cámara'} · {status.fps:.0f} fps")
