"""Mapping between chess squares and cells of the rectified image, for any a1 orientation."""

from __future__ import annotations

import chess

from chessoptic.vision.calibration import CELL, RECTIFIED_SIZE

# Number of 90° clockwise rotations from the standard view (a1 bottom-left).
_ROTATIONS: dict[str, int] = {
    "bottom-left": 0,
    "top-left": 1,
    "top-right": 2,
    "bottom-right": 3,
}

Cell = tuple[int, int]  # (col, row) in the rectified image; row 0 is the top


def square_to_cell(square: int, a1_corner: str) -> Cell:
    col = chess.square_file(square)
    row = 7 - chess.square_rank(square)
    for _ in range(_ROTATIONS.get(a1_corner, 0)):
        col, row = 7 - row, col
    return col, row


def cell_to_square(cell: Cell, a1_corner: str) -> int:
    col, row = cell
    for _ in range(_ROTATIONS.get(a1_corner, 0)):
        col, row = row, 7 - col  # inverse rotation
    return chess.square(col, 7 - row)


def cell_rect(cell: Cell, size: int = RECTIFIED_SIZE) -> tuple[int, int, int, int]:
    """(x, y, w, h) of a cell in the rectified image."""
    cell_px = size // 8
    col, row = cell
    return col * cell_px, row * cell_px, cell_px, cell_px


def sample_region(
    cell: Cell, inner: float = 0.5, size: int = RECTIFIED_SIZE
) -> tuple[int, int, int, int]:
    """Central part of the cell used for features (POC: fixed center; later perspective-aware)."""
    x, y, w, h = cell_rect(cell, size)
    margin_x = int(w * (1 - inner) / 2)
    margin_y = int(h * (1 - inner) / 2)
    return x + margin_x, y + margin_y, w - 2 * margin_x, h - 2 * margin_y


def square_cells(a1_corner: str) -> list[Cell]:
    """Cells in `chess.SQUARES` order."""
    return [square_to_cell(sq, a1_corner) for sq in chess.SQUARES]


__all__ = [
    "CELL",
    "Cell",
    "cell_rect",
    "cell_to_square",
    "sample_region",
    "square_cells",
    "square_to_cell",
]
