"""Aggregates camera / board / link status into the HealthState shown by the pill and strip."""

from __future__ import annotations

from chessoptic.core.bus import EventBus
from chessoptic.core.events import (
    CalibrationChanged,
    CameraState,
    CameraStatus,
    ClassifierTrained,
    ComponentHealth,
    HealthLevel,
    HealthState,
    LinkState,
    LinkStatus,
    OccupancyFrame,
)

LOW_CONFIDENCE = 0.3


class HealthAggregator:
    def __init__(self, bus: EventBus) -> None:
        self._bus = bus
        self._camera = ComponentHealth(HealthLevel.IDLE, "Cámara", "buscando")
        self._calibrated = False
        self._trained = False
        self._confidence: float | None = None
        self._moving = False
        self._link = ComponentHealth(HealthLevel.IDLE, "Enlace", "inactivo")
        self._last: HealthState | None = None
        bus.subscribe(CameraStatus, self._on_camera)
        bus.subscribe(CalibrationChanged, self._on_calibration)
        bus.subscribe(ClassifierTrained, self._on_trained)
        bus.subscribe(OccupancyFrame, self._on_occupancy)
        bus.subscribe(LinkStatus, self._on_link)

    # ---- inputs ----------------------------------------------------------

    def _on_camera(self, event: CameraStatus) -> None:
        if event.state == CameraState.OK:
            self._camera = ComponentHealth(HealthLevel.OK, "Cámara", f"{event.fps:.0f} fps")
        elif event.state == CameraState.LOW_FPS:
            self._camera = ComponentHealth(HealthLevel.WARN, "Cámara", f"{event.fps:.0f} fps")
        elif event.state == CameraState.DISCONNECTED:
            self._camera = ComponentHealth(HealthLevel.ERR, "Cámara", "desconectada")
        else:
            self._camera = ComponentHealth(HealthLevel.ERR, "Cámara", "sin cámara")
        self._emit()

    def _on_calibration(self, event: CalibrationChanged) -> None:
        self._calibrated = event.calibration is not None
        if not self._calibrated:
            self._trained = False
            self._confidence = None
        self._emit()

    def _on_trained(self, event: ClassifierTrained) -> None:
        self._trained = event.trained
        self._emit()

    def _on_occupancy(self, event: OccupancyFrame) -> None:
        self._moving = not event.stable
        if event.stable:
            self._confidence = event.mean_confidence
        self._emit()

    def _on_link(self, event: LinkStatus) -> None:
        level = {
            LinkState.CONNECTED: HealthLevel.OK,
            LinkState.ANNOUNCING: HealthLevel.WARN,
            LinkState.LOST: HealthLevel.ERR,
            LinkState.INACTIVE: HealthLevel.IDLE,
        }[event.state]
        detail = (
            event.client
            if event.state == LinkState.CONNECTED
            else {
                LinkState.ANNOUNCING: "anunciando…",
                LinkState.LOST: "perdido",
                LinkState.INACTIVE: "inactivo",
            }.get(event.state, "")
        )
        self.set_link(level, detail)

    def set_link(self, level: HealthLevel, detail: str) -> None:
        self._link = ComponentHealth(level, "Enlace", detail)
        self._emit()

    # ---- aggregation -----------------------------------------------------

    def _board(self) -> ComponentHealth:
        if not self._calibrated:
            return ComponentHealth(HealthLevel.IDLE, "Tablero", "sin calibrar")
        if not self._trained:
            return ComponentHealth(HealthLevel.IDLE, "Tablero", "sin verificar")
        if self._confidence is None:
            return ComponentHealth(HealthLevel.WARN, "Tablero", "esperando")
        if self._confidence < LOW_CONFIDENCE:
            return ComponentHealth(HealthLevel.WARN, "Tablero", f"Confianza {self._confidence:.0%}")
        return ComponentHealth(HealthLevel.OK, "Tablero", f"Confianza {self._confidence:.0%}")

    def _emit(self) -> None:
        board = self._board()
        camera, link = self._camera, self._link

        if camera.level == HealthLevel.ERR:
            level, text = HealthLevel.ERR, "Sin cámara"
        elif not self._calibrated:
            level, text = HealthLevel.IDLE, "Sin calibrar"
        elif not self._trained:
            level, text = HealthLevel.IDLE, "Sin verificar"
        elif link.level == HealthLevel.ERR:
            level, text = HealthLevel.ERR, "Enlace perdido"
        elif board.level == HealthLevel.WARN:
            level, text = HealthLevel.WARN, "Revisar tablero"
        elif camera.level == HealthLevel.WARN:
            level, text = HealthLevel.WARN, "Cámara lenta"
        elif link.level == HealthLevel.WARN:
            level, text = HealthLevel.WARN, "Esperando cliente"
        else:
            level, text = HealthLevel.OK, "Driver OK"

        state = HealthState(level, text, camera, board, link)
        if state != self._last:
            self._last = state
            self._bus.publish(state)

    @property
    def state(self) -> HealthState:
        return self._last or HealthState.starting()
