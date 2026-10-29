"""CoreRuntime: one object that owns the bus, the vision thread and the setup flow."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable

from chessoptic.capture.webcam import CameraInfo, WebcamSource, list_cameras
from chessoptic.core.bus import EventBus
from chessoptic.core.config import (
    AppConfig,
    CameraProfile,
    load_profile,
    save_config,
    save_profile,
)
from chessoptic.core.events import (
    CalibrationChanged,
    CamerasListed,
    CameraState,
    CameraStatus,
    ClassifierTrained,
    SetupCheckReport,
)
from chessoptic.core.health import HealthAggregator
from chessoptic.core.setup import SetupFlow
from chessoptic.vision.calibration import Calibration
from chessoptic.vision.check import run_setup_check
from chessoptic.vision.occupancy import OccupancyClassifier
from chessoptic.vision.pipeline import VisionPipeline

log = logging.getLogger(__name__)


class CoreRuntime:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.bus = EventBus()
        self.pipeline = VisionPipeline(self.bus, stability_window_ms=config.stability_ms)
        self.health = HealthAggregator(self.bus)
        self.setup = SetupFlow(self.bus, self.pipeline)
        self.cameras: list[CameraInfo] = []
        self.camera: CameraInfo | None = None
        self.profile: CameraProfile | None = None
        self.pipeline.start()

    # ---- cameras ---------------------------------------------------------

    def list_cameras_async(self, done: Callable[[list[CameraInfo]], None] | None = None) -> None:
        def worker() -> None:
            cameras = list_cameras()
            self.cameras = cameras
            self.bus.publish(CamerasListed(tuple(cameras)))
            if not cameras:
                self.bus.publish(CameraStatus(CameraState.NO_CAMERA, 0.0, ""))
            if done is not None:
                done(cameras)

        threading.Thread(target=worker, name="list-cameras", daemon=True).start()

    def open_camera(self, info: CameraInfo) -> bool:
        try:
            source = WebcamSource(info)
        except OSError as exc:
            log.error("cannot open camera %s: %s", info.label, exc)
            self.bus.publish(CameraStatus(CameraState.DISCONNECTED, 0.0, info.name))
            return False
        self.camera = info
        self.config.camera = info.key
        save_config(self.config)
        self.pipeline.set_source(source)
        self.profile = load_profile(info.key)
        if self.profile is not None:
            self._apply_profile(self.profile)
        else:
            self.pipeline.set_calibration(None)
            self.pipeline.set_classifier(None)
            self.bus.publish(CalibrationChanged(None))
            self.bus.publish(ClassifierTrained(False))
        return True

    def has_profile(self, info: CameraInfo) -> bool:
        return load_profile(info.key) is not None

    def _apply_profile(self, profile: CameraProfile) -> None:
        calibration = Calibration.from_dict(profile.calibration)
        self.pipeline.set_calibration(calibration)
        self.bus.publish(CalibrationChanged(calibration))
        classifier = (
            OccupancyClassifier.from_dict(profile.classifier) if profile.classifier else None
        )
        self.pipeline.set_classifier(classifier)
        self.bus.publish(ClassifierTrained(bool(classifier and classifier.trained)))
        if classifier is not None and classifier.trained:
            self.setup.watch_initial_position(True)

    # ---- calibration & setup ----------------------------------------------

    @property
    def calibration(self) -> Calibration | None:
        return self.pipeline.calibration

    def set_calibration(self, calibration: Calibration | None) -> None:
        self.pipeline.set_calibration(calibration)
        self.pipeline.set_classifier(None)
        self.bus.publish(CalibrationChanged(calibration))
        self.bus.publish(ClassifierTrained(False))

    def arm_initial_training(self) -> None:
        self.setup.arm_initial_training()

    def run_setup_check(self) -> SetupCheckReport:
        calibration = self.pipeline.calibration
        classifier = self.pipeline.classifier
        frames = self.pipeline.recent_rectified()
        if calibration is None or classifier is None:
            report = run_setup_check([], OccupancyClassifier(), "bottom-left")
        else:
            report = run_setup_check(frames[-10:], classifier, calibration.a1_corner)
        self.bus.publish(report)
        return report

    def start_move_test(self) -> None:
        self.setup.start_move_test()

    def stop_move_test(self) -> None:
        self.setup.stop_move_test()

    def finish_setup(self, provider: str, check_level: str | None) -> None:
        """Persist the camera profile (calibration + classifier) and the chosen provider."""
        calibration = self.pipeline.calibration
        if self.camera is None or calibration is None:
            return
        classifier = self.pipeline.classifier
        self.profile = CameraProfile(
            camera_key=self.camera.key,
            calibration=calibration.to_dict(),
            classifier=classifier.to_dict() if classifier and classifier.trained else None,
            check_level=check_level,
        )
        save_profile(self.profile)
        self.config.provider = provider
        save_config(self.config)
        self.setup.stop_move_test()
        self.setup.watch_initial_position(True)

    def set_camera_auto(self, what: str, enabled: bool) -> None:
        """Best-effort autofocus / autoexposure toggle; silently ignored if unsupported."""
        import cv2

        source = self.pipeline.source
        if not isinstance(source, WebcamSource):
            return
        if what == "focus":
            source.set_property(cv2.CAP_PROP_AUTOFOCUS, 1.0 if enabled else 0.0)
        elif what == "exposure":
            # DirectShow convention: 0.75 = auto, 0.25 = manual.
            source.set_property(cv2.CAP_PROP_AUTO_EXPOSURE, 0.75 if enabled else 0.25)

    def set_stability_ms(self, value: int) -> None:
        self.config.stability_ms = value
        self.pipeline.set_stability_window(value)
        save_config(self.config)

    # ---- lifecycle -------------------------------------------------------

    def shutdown(self) -> None:
        self.pipeline.stop()
