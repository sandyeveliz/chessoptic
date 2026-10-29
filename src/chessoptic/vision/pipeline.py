"""Vision pipeline thread: source → rectify → stability → occupancy → events on the bus."""

from __future__ import annotations

import logging
import threading
import time
from collections import deque

from chessoptic.capture.source import FrameSource, Image
from chessoptic.capture.webcam import WebcamSource
from chessoptic.core.bus import EventBus
from chessoptic.core.events import (
    CameraState,
    CameraStatus,
    FrameEvent,
    OccupancyFrame,
    StabilityEvent,
)
from chessoptic.vision.calibration import Calibration
from chessoptic.vision.features import Features, extract_features
from chessoptic.vision.occupancy import OccupancyClassifier
from chessoptic.vision.stability import StabilityDetector

log = logging.getLogger(__name__)

LOW_FPS = 6.0
RECENT_FRAMES = 24


class VisionPipeline:
    def __init__(
        self,
        bus: EventBus,
        analysis_fps: float = 12.0,
        ui_fps: float = 12.0,
        stability_window_ms: int = 750,
    ) -> None:
        self._bus = bus
        self._analysis_period = 1.0 / analysis_fps
        self._ui_period = 1.0 / ui_fps
        self._stability = StabilityDetector(window_ms=stability_window_ms)
        self._lock = threading.RLock()
        self._source: FrameSource | None = None
        self._calibration: Calibration | None = None
        self._classifier: OccupancyClassifier | None = None
        self._recent: deque[Image] = deque(maxlen=RECENT_FRAMES)
        self._last_stable: Image | None = None
        self._last_features: Features | None = None
        self._last_grid: tuple[int, ...] | None = None
        self._reference: tuple[Features, tuple[int, ...]] | None = None
        self._mark_pending = False
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    # ---- configuration (thread-safe) ------------------------------------

    def set_source(self, source: FrameSource | None) -> None:
        with self._lock:
            old, self._source = self._source, source
            self._stability.reset()
            self._recent.clear()
            self._last_stable = None
        if old is not None:
            old.close()

    def set_calibration(self, calibration: Calibration | None) -> None:
        with self._lock:
            self._calibration = calibration
            self._stability.reset()
            self._recent.clear()
            self._last_stable = None

    def set_stability_window(self, window_ms: int) -> None:
        with self._lock:
            self._stability.window_ms = window_ms

    def set_classifier(self, classifier: OccupancyClassifier | None) -> None:
        with self._lock:
            self._classifier = classifier
            self._reference = None
            self._mark_pending = classifier is not None

    def mark_reference(self) -> None:
        """The board now shows an accepted position: later frames report changes against it."""
        with self._lock:
            if self._last_features is not None and self._last_grid is not None:
                self._reference = (self._last_features, self._last_grid)
                self._mark_pending = False
            else:
                self._mark_pending = True

    @property
    def classifier(self) -> OccupancyClassifier | None:
        return self._classifier

    @property
    def calibration(self) -> Calibration | None:
        return self._calibration

    @property
    def source(self) -> FrameSource | None:
        return self._source

    def recent_rectified(self) -> list[Image]:
        with self._lock:
            return list(self._recent)

    def last_stable_rectified(self) -> Image | None:
        with self._lock:
            return self._last_stable

    def train_initial(self) -> OccupancyClassifier | None:
        """Fit a classifier from the last stable rectified frame (assumed: start position)."""
        with self._lock:
            frame = self._last_stable
            calibration = self._calibration
        if frame is None or calibration is None:
            return None
        classifier = OccupancyClassifier()
        classifier.fit_initial(extract_features(frame, calibration.a1_corner))
        if not classifier.trained:
            return None
        self.set_classifier(classifier)
        return classifier

    def _update_reference(
        self,
        classifier: OccupancyClassifier,
        features: Features,
        grid: tuple[int, ...],
        stable: bool,
    ) -> tuple[bool, ...]:
        with self._lock:
            self._last_features, self._last_grid = features, grid
            if self._mark_pending or (self._reference is None and stable):
                self._reference = (features, grid)
                self._mark_pending = False
            reference = self._reference
        if reference is None:
            return ()
        changed = classifier.change_flags(features, reference[0])
        # Same labels, still: only light drifted; follow it so old shadows don't linger.
        if stable and grid == reference[1] and not any(changed):
            with self._lock:
                self._reference = (features, grid)
        return changed

    # ---- thread ----------------------------------------------------------

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="vision", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=3)
            self._thread = None
        self.set_source(None)

    def _loop(self) -> None:
        last_ui = 0.0
        last_analysis = 0.0
        last_status = 0.0
        while not self._stop.is_set():
            with self._lock:
                source = self._source
                calibration = self._calibration
                classifier = self._classifier
            if source is None:
                time.sleep(0.05)
                continue

            frame = source.read()
            now = time.monotonic()
            if frame is None:
                if isinstance(source, WebcamSource) and not source.healthy:
                    self._bus.publish(CameraStatus(CameraState.DISCONNECTED, 0.0, source.name))
                    time.sleep(0.5)
                else:
                    time.sleep(0.01)
                continue

            rectified: Image | None = None
            stability = None
            if calibration is not None:
                rectified = calibration.warp(frame.image)
                stability = self._stability.update(rectified, now)
                with self._lock:
                    self._recent.append(rectified)
                    if stability.stable:
                        self._last_stable = rectified

            if now - last_ui >= self._ui_period:
                last_ui = now
                self._bus.publish(FrameEvent(frame.image, rectified, now))

            if stability is not None and now - last_analysis >= self._analysis_period:
                last_analysis = now
                self._bus.publish(
                    StabilityEvent(stability.motion, stability.moving, stability.stable, now)
                )
                if classifier is not None and classifier.trained and rectified is not None:
                    try:
                        features = extract_features(rectified, calibration.a1_corner)  # type: ignore[union-attr]
                        grid, confidence = classifier.predict(features)
                    except Exception:
                        log.exception("occupancy prediction failed")
                    else:
                        changed = self._update_reference(
                            classifier, features, grid, stability.stable
                        )
                        self._bus.publish(
                            OccupancyFrame(
                                grid, confidence, stability.stable, stability.motion, now, changed
                            )
                        )

            if now - last_status >= 1.0:
                last_status = now
                fps = source.fps if isinstance(source, WebcamSource) else 0.0
                state = CameraState.LOW_FPS if 0 < fps < LOW_FPS else CameraState.OK
                self._bus.publish(CameraStatus(state, fps, source.name))
