"""Occupancy grids: for each of the 64 squares, empty / white piece / black piece.

Grids are tuples of 64 ints indexed like `chess.SQUARES` (a1 = 0 … h8 = 63).
"""

from __future__ import annotations

from enum import IntEnum

import chess


class Occupancy(IntEnum):
    EMPTY = 0
    WHITE = 1
    BLACK = 2


Grid = tuple[int, ...]


def from_board(board: chess.Board) -> Grid:
    cells = []
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece is None:
            cells.append(int(Occupancy.EMPTY))
        elif piece.color == chess.WHITE:
            cells.append(int(Occupancy.WHITE))
        else:
            cells.append(int(Occupancy.BLACK))
    return tuple(cells)


STARTPOS: Grid = from_board(chess.Board())


def diff(a: Grid, b: Grid) -> tuple[int, ...]:
    """Squares whose occupancy differs."""
    return tuple(sq for sq in chess.SQUARES if a[sq] != b[sq])


def counts(grid: Grid) -> tuple[int, int, int]:
    """(white, black, empty)."""
    white = sum(1 for v in grid if v == Occupancy.WHITE)
    black = sum(1 for v in grid if v == Occupancy.BLACK)
    return white, black, 64 - white - black


def square_is_dark(square: int) -> bool:
    return (chess.square_file(square) + chess.square_rank(square)) % 2 == 0
