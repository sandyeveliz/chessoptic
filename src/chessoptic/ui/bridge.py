"""CoreBridge: re-emits core events as Qt signals so views update on the GUI thread."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QImage

from chessoptic.core.bus import EventBus
from chessoptic.core.events import (
    CalibrationChanged,
    CamerasListed,
    CameraStatus,
    ClassifierTrained,
    FrameEvent,
    HealthState,
    InitialPositionCheck,
    MoveTestProgress,
    OccupancyFrame,
    SetupCheckReport,
    StabilityEvent,
)


@dataclass(frozen=True)
class UiFrames:
    raw: QImage
    rectified: QImage | None


def to_qimage(image: np.ndarray) -> QImage:
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    h, w = rgb.shape[:2]
    # .copy(): the numpy buffer belongs to the vision thread.
    return QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy()


class CoreBridge(QObject):
    health_changed = Signal(object)
    frames_ready = Signal(object)
    camera_status = Signal(object)
    cameras_listed = Signal(object)
    calibration_changed = Signal(object)
    classifier_trained = Signal(object)
    stability = Signal(object)
    occupancy = Signal(object)
    initial_check = Signal(object)
    setup_check = Signal(object)
    move_test = Signal(object)

    def __init__(self, bus: EventBus, parent: QObject | None = None) -> None:
        super().__init__(parent)
        bus.subscribe(HealthState, self.health_changed.emit)
        bus.subscribe(FrameEvent, self._on_frame)
        bus.subscribe(CameraStatus, self.camera_status.emit)
        bus.subscribe(CamerasListed, self.cameras_listed.emit)
        bus.subscribe(CalibrationChanged, self.calibration_changed.emit)
        bus.subscribe(ClassifierTrained, self.classifier_trained.emit)
        bus.subscribe(StabilityEvent, self.stability.emit)
        bus.subscribe(OccupancyFrame, self.occupancy.emit)
        bus.subscribe(InitialPositionCheck, self.initial_check.emit)
        bus.subscribe(SetupCheckReport, self.setup_check.emit)
        bus.subscribe(MoveTestProgress, self.move_test.emit)

    def _on_frame(self, event: FrameEvent) -> None:
        rectified = to_qimage(event.rectified) if event.rectified is not None else None
        self.frames_ready.emit(UiFrames(to_qimage(event.raw), rectified))
