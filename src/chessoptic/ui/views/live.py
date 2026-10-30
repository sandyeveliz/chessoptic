"""'En vivo': health strip, state block, rectified camera with overlay, last moves."""

from __future__ import annotations

import chess
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from chessoptic.board.occupancy import STARTPOS, Grid, from_board
from chessoptic.core.events import (
    AdapterError,
    CalibrationChanged,
    DriverState,
    DriverStateName,
    GameInfo,
    HealthState,
    InitialPositionCheck,
    OccupancyFrame,
    Phase,
    PositionMismatch,
)
from chessoptic.core.runtime import CoreRuntime
from chessoptic.game.session import PendingOpponentChanged
from chessoptic.ui.bridge import CoreBridge, UiFrames
from chessoptic.ui.widgets.camera_view import CameraView
from chessoptic.ui.widgets.health_strip import HealthStrip
from chessoptic.ui.widgets.moves_list import MovesList
from chessoptic.ui.widgets.state_block import StateBlock

KEEP_HIGHLIGHTS = (
    DriverStateName.MISMATCH,
    DriverStateName.REPLAY,
    DriverStateName.VERIFYING_BOARD,
)


class LiveView(QWidget):
    recalibrate_requested = Signal()

    def __init__(
        self, runtime: CoreRuntime, bridge: CoreBridge, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._runtime = runtime
        self._state: DriverState | None = None
        self._info: GameInfo | None = None
        # Everything fits the panel: the camera takes whatever height is left, so the state
        # block, the last moves and the actions never scroll out of sight.
        page = self
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 10, 16, 12)
        layout.setSpacing(10)

        self._strip = HealthStrip(page)
        layout.addWidget(self._strip)

        self._block = StateBlock(page)
        self._block.new_game.connect(self._new_game)
        self._block.end_game.connect(self._end_game)
        self._block.resync.connect(self._resync)
        self._block.promotion_chosen.connect(self._promotion)
        self._block.export_pgn.connect(self.export_pgn)
        layout.addWidget(self._block)

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
        self._camera.set_clickable(True)
        self._camera.square_clicked.connect(self._correct_square)
        self._camera.set_fit(True)
        self._camera.setMinimumHeight(160)
        layout.addWidget(self._camera, 1)

        moves_label = QLabel("ÚLTIMAS JUGADAS", page)
        moves_label.setObjectName("sectionLabel")
        layout.addWidget(moves_label)
        self._moves = MovesList(3, page)
        layout.addWidget(self._moves)

        actions = QHBoxLayout()
        recalibrate = QPushButton("Recalibrar", page)
        recalibrate.setCursor(Qt.CursorShape.PointingHandCursor)
        recalibrate.clicked.connect(self.recalibrate_requested.emit)
        export = QPushButton("Exportar PGN", page)
        export.clicked.connect(self.export_pgn)
        actions.addWidget(recalibrate)
        actions.addWidget(export)
        actions.addStretch(1)
        layout.addLayout(actions)

        bridge.health_changed.connect(self.set_health)
        bridge.frames_ready.connect(self._on_frames)
        bridge.occupancy.connect(self._on_occupancy)
        bridge.initial_check.connect(self._on_initial_check)
        bridge.driver_state.connect(self._on_state)
        bridge.game_info.connect(self._on_info)
        bridge.pending_changed.connect(self._on_pending)
        bridge.position_mismatch.connect(self._on_mismatch)
        bridge.adapter_error.connect(self._on_error)
        bridge.calibration_changed.connect(self._on_calibration)

    # ---- actions ---------------------------------------------------------

    def _new_game(self) -> None:
        if self._runtime.session:
            self._runtime.session.new_game()

    def _end_game(self) -> None:
        if self._runtime.session:
            self._runtime.session.end_game()

    def _resync(self) -> None:
        if self._runtime.session:
            self._runtime.session.resync()

    def _promotion(self, piece: int) -> None:
        if self._runtime.session:
            self._runtime.session.set_promotion(piece)

    def _expected_grid(self) -> Grid:
        if self._state is not None and self._state.phase == Phase.IN_GAME and self._info:
            return from_board(chess.Board(self._info.fen))
        return STARTPOS

    def _correct_square(self, square: int) -> None:
        if self._runtime.correct_square(square, self._expected_grid()):
            self._camera.set_caption(f"{chess.square_name(square)} corregida: aprendido")

    def export_pgn(self) -> None:
        session = self._runtime.session
        path = session.export_pgn() if session else None
        if path is None:
            QMessageBox.information(self, "Exportar PGN", "Todavía no hay jugadas para exportar.")
        else:
            QMessageBox.information(self, "Exportar PGN", f"Guardado en:\n{path}")

    # ---- updates ---------------------------------------------------------

    def set_health(self, state: HealthState) -> None:
        self._strip.set_state(state)

    def _on_calibration(self, event: CalibrationChanged) -> None:
        if event.calibration is not None:
            self._camera.set_a1(event.calibration.a1_corner)

    def _on_frames(self, frames: UiFrames) -> None:
        self._camera.set_frames(frames.raw, frames.rectified)

    def _on_occupancy(self, event: OccupancyFrame) -> None:
        self._camera.set_overlay(event.grid, event.confidence)
        self._confidence.setText(
            f"{event.mean_confidence:.0%}" + ("" if event.stable else " · MOVIENDO")
        )

    def _on_state(self, state: DriverState) -> None:
        self._state = state
        self._camera.set_expected(self._expected_grid())
        self._block.set_state(state)
        if state.state not in KEEP_HIGHLIGHTS:
            self._camera.set_highlights(self._last_move_highlights())

    def _on_info(self, info: GameInfo) -> None:
        self._info = info
        self._camera.set_expected(self._expected_grid())
        self._block.set_info(info)
        self._moves.set_info(info)
        if self._state and self._state.phase == Phase.IN_GAME:
            self._camera.set_highlights(self._last_move_highlights())

    def _on_pending(self, event: PendingOpponentChanged) -> None:
        self._block.set_pending(event.pending)
        if event.pending is not None:
            self._camera.set_highlights(
                {event.pending.from_square: "origin", event.pending.to_square: "destination"}
            )

    def _on_mismatch(self, event: PositionMismatch) -> None:
        self._camera.set_highlights({issue.square: "error" for issue in event.issues})

    def _on_error(self, event: AdapterError) -> None:
        QMessageBox.warning(self, "ChessOptic", event.message)

    def _on_initial_check(self, check: InitialPositionCheck) -> None:
        if self._state is not None and self._state.phase == Phase.IN_GAME:
            return
        if check.complete:
            self._camera.set_highlights({})
            return
        highlights = {sq: "missing" for sq in check.missing}
        highlights.update({sq: "error" for sq in check.extra + check.wrong_color})
        self._camera.set_highlights(highlights)

    def _last_move_highlights(self) -> dict[int, str]:
        if not self._info or not self._info.moves:
            return {}
        move = chess.Move.from_uci(self._info.moves[-1].uci)
        return {move.from_square: "origin", move.to_square: "destination"}
