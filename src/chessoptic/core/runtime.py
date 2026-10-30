"""CoreRuntime: one object that owns the bus, the vision thread and the setup flow."""

from __future__ import annotations

import dataclasses
import logging
import threading
import time
from collections.abc import Callable

import chess

from chessoptic.adapters import create_adapter
from chessoptic.board.occupancy import Grid
from chessoptic.capture.webcam import CameraInfo, WebcamSource, list_cameras
from chessoptic.core import debug
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
    DriverState,
    FrameEvent,
    LogEntry,
    MoveTestProgress,
    OccupancyFrame,
    Phase,
    PositionMismatch,
    SetupCheckReport,
)
from chessoptic.core.health import HealthAggregator
from chessoptic.core.setup import SetupFlow
from chessoptic.game.modes import get_mode
from chessoptic.game.session import GameSession
from chessoptic.vision.calibration import Calibration
from chessoptic.vision.check import run_setup_check
from chessoptic.vision.occupancy import OccupancyClassifier
from chessoptic.vision.pipeline import VisionPipeline

log = logging.getLogger(__name__)

DUMP_COOLDOWN_S = 20.0


def _now() -> str:
    return time.strftime("%H:%M:%S")


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


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
        self.session: GameSession | None = None
        self._dumped: dict[str, tuple[tuple[str, str], float]] = {}
        self._last_frame: FrameEvent | None = None
        self._last_occupancy: OccupancyFrame | None = None
        self.bus.subscribe(DriverState, self._on_driver_state)
        self.bus.subscribe(FrameEvent, self._remember_frame)
        self.bus.subscribe(OccupancyFrame, self._remember_occupancy)
        self.bus.subscribe(MoveTestProgress, self._on_move_test_progress)
        self.bus.subscribe(PositionMismatch, self._on_position_mismatch)
        self.pipeline.start()

    # ---- learning ----------------------------------------------------------

    def _on_position_accepted(self, expected: Grid) -> None:
        self.pipeline.mark_reference(expected)
        self._maybe_dump_phantoms(expected)

    def correct_square(self, square: int, expected: Grid) -> bool:
        """The user says the camera is wrong on `square`; teach it the expected reading."""
        ok = self.pipeline.refine(expected, {square}, alpha=0.5)
        if ok:
            name = chess.square_name(square)
            self.bus.publish(LogEntry(_now(), "event", f"{name} corregida a mano"))
        return ok

    def save_classifier(self) -> None:
        """Persist a refined classifier into the camera profile."""
        classifier = self.pipeline.classifier
        if self.profile is None or classifier is None or not self.pipeline.classifier_dirty:
            return
        self.profile = dataclasses.replace(
            self.profile, classifier=classifier.to_dict(), updated=_now_iso()
        )
        save_profile(self.profile)
        self.pipeline.classifier_dirty = False

    # ---- diagnostics -------------------------------------------------------

    def _maybe_dump_phantoms(self, expected: Grid) -> None:
        """Keep a frame when the camera sees pieces on squares that should be empty."""
        occ = self._last_occupancy
        if occ is None:
            return
        phantoms = [sq for sq in chess.SQUARES if expected[sq] == 0 and occ.grid[sq] != 0]
        if phantoms:
            self._dump("phantom", {"squares": phantoms, "expected": list(expected)})

    def _remember_frame(self, event: FrameEvent) -> None:
        self._last_frame = event

    def _remember_occupancy(self, event: OccupancyFrame) -> None:
        self._last_occupancy = event

    def _on_move_test_progress(self, event: MoveTestProgress) -> None:
        if event.mismatched:
            self._dump(
                "movetest", {"stage": str(event.stage), "mismatched": list(event.mismatched)}
            )

    def _on_position_mismatch(self, event: PositionMismatch) -> None:
        issues = [
            {"square": i.square, "expected": i.expected, "seen": i.seen} for i in event.issues
        ]
        self._dump("mismatch", {"issues": issues})

    def _dump(self, tag: str, info: dict[str, object]) -> None:
        """One dump per distinct situation, at most one every few seconds per tag."""
        if not self.config.save_error_frames:
            return
        key = (tag, repr(sorted(info.items())))
        now = time.monotonic()
        last = self._dumped.get(tag)
        if last is not None and last[0] == key and now - last[1] < DUMP_COOLDOWN_S:
            return
        self._dumped[tag] = (key, now)
        frame, occ = self._last_frame, self._last_occupancy
        calibration = self.pipeline.calibration
        details: dict[str, object] = {
            **info,
            "a1": calibration.a1_corner if calibration is not None else None,
            "grid": list(occ.grid) if occ is not None else None,
            "confidence": [round(c, 3) for c in occ.confidence] if occ is not None else None,
            "camera": self.camera.key if self.camera is not None else None,
        }
        debug.dump(
            tag,
            frame.raw if frame is not None else None,
            frame.rectified if frame is not None else None,
            details,
        )

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
            if self.session is None:
                self.start_session()

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
        self.start_session(provider)

    # ---- game session ----------------------------------------------------

    def start_session(self, provider: str | None = None) -> GameSession:
        """(Re)create the game session for `provider` (defaults to the configured one)."""
        if self.session is not None:
            self.session.stop()
        name = provider or self.config.provider
        adapter = create_adapter(name, self.config)
        self.session = GameSession(
            self.bus,
            adapter,
            get_mode("free"),
            mismatch_grace_ms=2000,
            promotion_default=self.config.promotion_default,
            on_accept=self._on_position_accepted,
        )
        self.session.start()
        return self.session

    def _on_driver_state(self, state: DriverState) -> None:
        # The initial-position check only matters while no game is running.
        self.setup.watch_initial_position(state.phase == Phase.STANDBY)

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
        self.save_classifier()
        if self.session is not None:
            self.session.stop()
        self.pipeline.stop()
