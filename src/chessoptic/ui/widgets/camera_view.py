"""CameraView: raw frame with draggable corners, or rectified 8×8 view with occupancy overlay."""

from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QImage,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import QSizePolicy, QWidget

from chessoptic.board.occupancy import Occupancy
from chessoptic.ui.theme import TOKENS
from chessoptic.vision.calibration import Corner
from chessoptic.vision.squares import square_to_cell

HANDLE_RADIUS = 9.0
GRAB_DISTANCE = 22.0

HIGHLIGHT_COLORS: dict[str, str] = {
    "origin": TOKENS.hl_origin,
    "destination": TOKENS.hl_destination,
    "error": TOKENS.hl_error,
    "missing": TOKENS.hl_origin,
}


class CameraView(QWidget):
    corners_changed = Signal(object)  # tuple of 4 (x, y) in image pixels
    corner_drag_finished = Signal(object)

    def __init__(self, mode: str = "rectified", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._mode = mode
        self._raw: QImage | None = None
        self._rectified: QImage | None = None
        self._grid: tuple[int, ...] | None = None
        self._confidence: tuple[float, ...] | None = None
        self._highlights: dict[int, str] = {}
        self._a1 = "bottom-left"
        self._corners: list[Corner] | None = None
        self._editable = False
        self._guide = False
        self._drag_index: int | None = None
        self._caption = ""
        self._placeholder = "Sin imagen"
        self._fit = False  # True: take whatever height the layout gives (no height-for-width)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(120)

    def set_fit(self, fit: bool) -> None:
        """Fill the space the layout gives instead of forcing a square: the image is
        letterboxed, so the rest of the page never scrolls because of the camera."""
        self._fit = fit
        self.updateGeometry()

    # ---- state -----------------------------------------------------------

    def set_mode(self, mode: str) -> None:
        self._mode = mode
        self.update()

    def set_frames(self, raw: QImage | None, rectified: QImage | None) -> None:
        self._raw = raw
        self._rectified = rectified
        self.update()

    def set_overlay(
        self, grid: tuple[int, ...] | None, confidence: tuple[float, ...] | None
    ) -> None:
        self._grid = grid
        self._confidence = confidence
        self.update()

    def set_highlights(self, highlights: Mapping[int, str]) -> None:
        self._highlights = dict(highlights)
        self.update()

    def set_a1(self, a1_corner: str) -> None:
        self._a1 = a1_corner
        self.update()

    def set_corners(self, corners: tuple[Corner, Corner, Corner, Corner] | None) -> None:
        self._corners = list(corners) if corners else None
        self.update()

    def set_editable(self, editable: bool) -> None:
        self._editable = editable
        self.setCursor(Qt.CursorShape.CrossCursor if editable else Qt.CursorShape.ArrowCursor)

    def set_guide(self, visible: bool) -> None:
        self._guide = visible
        self.update()

    def set_caption(self, text: str) -> None:
        self._caption = text
        self.update()

    def set_placeholder(self, text: str) -> None:
        self._placeholder = text
        self.update()

    def heightForWidth(self, width: int) -> int:  # noqa: N802 - Qt override
        if self._mode == "rectified":
            return width
        if self._raw is not None and self._raw.width():
            return int(width * self._raw.height() / self._raw.width())
        return int(width * 9 / 16)

    def hasHeightForWidth(self) -> bool:  # noqa: N802 - Qt override
        return not self._fit

    # ---- geometry helpers --------------------------------------------------

    def _image(self) -> QImage | None:
        return self._rectified if self._mode == "rectified" else self._raw

    def _target_rect(self) -> QRectF:
        image = self._image()
        w, h = float(self.width()), float(self.height())
        if image is None or not image.width():
            side = min(w, h)
            return QRectF((w - side) / 2, (h - side) / 2, side, side)
        scale = min(w / image.width(), h / image.height())
        tw, th = image.width() * scale, image.height() * scale
        top = 0.0 if self._fit else (h - th) / 2  # fit mode: hug the content above, no gap
        return QRectF((w - tw) / 2, top, tw, th)

    def _to_widget(self, point: Corner, target: QRectF) -> QPointF:
        image = self._image()
        if image is None or not image.width():
            return QPointF(target.left(), target.top())
        sx, sy = target.width() / image.width(), target.height() / image.height()
        return QPointF(target.left() + point[0] * sx, target.top() + point[1] * sy)

    def _to_image(self, point: QPointF, target: QRectF) -> Corner:
        image = self._image()
        if image is None or not image.width():
            return (0.0, 0.0)
        sx, sy = image.width() / target.width(), image.height() / target.height()
        x = min(max((point.x() - target.left()) * sx, 0.0), float(image.width()))
        y = min(max((point.y() - target.top()) * sy, 0.0), float(image.height()))
        return (x, y)

    # ---- painting ------------------------------------------------------------

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 - Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        target = self._target_rect()
        image = self._image()

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(TOKENS.square_dark))
        painter.drawRoundedRect(target, 6, 6)

        if image is None or not image.width():
            painter.setPen(QColor(TOKENS.muted))
            painter.drawText(target, Qt.AlignmentFlag.AlignCenter, self._placeholder)
        else:
            painter.drawImage(target, image)
            if self._mode == "rectified":
                self._paint_board_overlay(painter, target)
            else:
                self._paint_raw_overlay(painter, target)

        painter.setPen(QPen(QColor(TOKENS.line_strong), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(target, 6, 6)

        if self._caption:
            self._paint_caption(painter, target)
        painter.end()

    def _paint_board_overlay(self, painter: QPainter, target: QRectF) -> None:
        cell = target.width() / 8
        for square in range(64):
            col, row = square_to_cell(square, self._a1)
            rect = QRectF(target.left() + col * cell, target.top() + row * cell, cell, cell)
            kind = self._highlights.get(square)
            if kind is not None:
                color = QColor(HIGHLIGHT_COLORS.get(kind, TOKENS.hl_error))
                color.setAlpha(170)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(color)
                painter.drawRect(rect)
            if self._grid is not None:
                value = self._grid[square]
                if value != Occupancy.EMPTY:
                    radius = cell * 0.3
                    center = rect.center()
                    if value == Occupancy.WHITE:
                        painter.setBrush(QColor("#FFFFFF"))
                        painter.setPen(QPen(QColor(TOKENS.line_strong), 1.5))
                    else:
                        painter.setBrush(QColor(TOKENS.ink))
                        painter.setPen(QPen(QColor(TOKENS.ink), 1.5))
                    painter.drawEllipse(center, radius, radius)
                if self._confidence is not None and self._confidence[square] < 0.25:
                    painter.setPen(QPen(QColor(TOKENS.err), 2))
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawRect(rect.adjusted(2, 2, -2, -2))
        self._paint_coordinates(painter, target, cell)

    def _paint_coordinates(self, painter: QPainter, target: QRectF, cell: float) -> None:
        font = QFont(TOKENS.font_mono, 8)
        painter.setFont(font)
        painter.setPen(QColor(TOKENS.muted))
        for file_index, letter in enumerate("abcdefgh"):
            # Label the column that holds rank-1 squares of this file.
            col, row = square_to_cell(file_index, self._a1)  # a1..h1 are squares 0..7
            x = target.left() + col * cell
            y = target.top() + row * cell
            painter.drawText(
                QRectF(x, y, cell, cell),
                Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight,
                letter,
            )
        for rank in range(8):
            col, row = square_to_cell(rank * 8, self._a1)  # a1, a2, … a8
            x = target.left() + col * cell
            y = target.top() + row * cell
            painter.drawText(
                QRectF(x, y, cell, cell),
                Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
                str(rank + 1),
            )

    def _paint_raw_overlay(self, painter: QPainter, target: QRectF) -> None:
        if self._guide:
            side = min(target.width(), target.height()) * 0.8
            guide = QRectF(
                target.center().x() - side / 2, target.center().y() - side / 2, side, side
            )
            pen = QPen(QColor(TOKENS.brand_light), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(guide)
        if self._corners:
            points = [self._to_widget(c, target) for c in self._corners]
            fill = QColor(TOKENS.brand_light)
            fill.setAlpha(50)
            painter.setPen(QPen(QColor(TOKENS.brand_light), 2))
            painter.setBrush(QBrush(fill))
            painter.drawPolygon(QPolygonF(points))
            labels = ("AI", "AD", "BD", "BI")
            for index, point in enumerate(points):
                active = index == self._drag_index
                painter.setBrush(QColor(TOKENS.turn if active else "#FFFFFF"))
                painter.setPen(QPen(QColor(TOKENS.turn), 2))
                painter.drawEllipse(point, HANDLE_RADIUS, HANDLE_RADIUS)
                painter.setPen(QColor("#FFFFFF" if active else TOKENS.turn))
                painter.setFont(QFont(TOKENS.font_sans, 7, QFont.Weight.Bold))
                painter.drawText(
                    QRectF(point.x() - 12, point.y() - 8, 24, 16),
                    Qt.AlignmentFlag.AlignCenter,
                    labels[index],
                )

    def _paint_caption(self, painter: QPainter, target: QRectF) -> None:
        painter.setFont(QFont(TOKENS.font_sans, 8))
        metrics = painter.fontMetrics()
        width = metrics.horizontalAdvance(self._caption) + 16
        rect = QRectF(target.left() + 8, target.top() + 8, width, metrics.height() + 6)
        bg = QColor(TOKENS.ink)
        bg.setAlpha(170)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg)
        painter.drawRoundedRect(rect, 6, 6)
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self._caption)

    # ---- corner dragging ------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt override
        if not (self._editable and self._corners and self._mode == "raw"):
            return
        target = self._target_rect()
        pos = event.position()
        best, best_d = None, GRAB_DISTANCE
        for index, corner in enumerate(self._corners):
            p = self._to_widget(corner, target)
            d = ((p.x() - pos.x()) ** 2 + (p.y() - pos.y()) ** 2) ** 0.5
            if d < best_d:
                best, best_d = index, d
        self._drag_index = best
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt override
        if self._drag_index is None or not self._corners:
            return
        self._corners[self._drag_index] = self._to_image(event.position(), self._target_rect())
        self.corners_changed.emit(tuple(self._corners))
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt override
        if self._drag_index is not None and self._corners:
            self._drag_index = None
            self.corner_drag_finished.emit(tuple(self._corners))
            self.update()
