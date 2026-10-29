"""BoardModel: full position (piece types included) maintained from occupancy changes.

The camera only tells us empty / white / black per square. Given the current position, the
legal moves are enumerated and the one whose resulting occupancy matches the observed grid is
the move that was played. Castling, en passant and captures fall out of this comparison for
free; promotion is the only ambiguous case (same squares, four possible pieces).
"""

from __future__ import annotations

from dataclasses import dataclass

import chess

from chessoptic.board.occupancy import Grid, diff, from_board
from chessoptic.core.events import SquareIssue


@dataclass(frozen=True)
class NoChange:
    pass


@dataclass(frozen=True)
class Move:
    move: chess.Move


@dataclass(frozen=True)
class Ambiguous:
    candidates: tuple[chess.Move, ...]


@dataclass(frozen=True)
class Transient:
    """Changed squares are a subset of some legal move's change set: a move in progress."""

    candidates: tuple[chess.Move, ...]


@dataclass(frozen=True)
class Mismatch:
    issues: tuple[SquareIssue, ...]


Resolution = NoChange | Move | Ambiguous | Transient | Mismatch


class BoardModel:
    def __init__(self, board: chess.Board | None = None, both_sides: bool = False) -> None:
        self.board = board if board is not None else chess.Board()
        self.both_sides = both_sides

    # ---- queries ---------------------------------------------------------

    @property
    def fen(self) -> str:
        return self.board.fen()

    def expected_occupancy(self) -> Grid:
        return from_board(self.board)

    def candidate_moves(self) -> list[chess.Move]:
        moves = list(self.board.legal_moves)
        if self.both_sides:
            other = self.board.copy(stack=False)
            other.turn = not other.turn
            # Clear en passant for the "wrong" side: it never applies after a null turn swap.
            other.ep_square = None
            moves.extend(other.legal_moves)
        return moves

    def occupancy_after(self, move: chess.Move) -> Grid:
        board = self.board.copy(stack=False)
        if not board.is_legal(move):
            board.turn = not board.turn
            board.ep_square = None
        board.push(move)
        return from_board(board)

    def resolve(self, grid: Grid) -> Resolution:
        current = self.expected_occupancy()
        changed = set(diff(current, grid))
        if not changed:
            return NoChange()

        exact: list[chess.Move] = []
        partial: list[chess.Move] = []
        for move in self.candidate_moves():
            after = self.occupancy_after(move)
            move_changes = set(diff(current, after))
            if after == grid:
                exact.append(move)
            elif changed <= move_changes:
                partial.append(move)

        if len(exact) == 1:
            return Move(exact[0])
        if len(exact) > 1:
            # Same from/to squares: only promotions differ.
            return Ambiguous(tuple(exact))
        if partial:
            return Transient(tuple(partial))
        issues = tuple(SquareIssue(sq, current[sq], grid[sq]) for sq in sorted(changed))
        return Mismatch(issues)

    def issues_against(self, grid: Grid, target: Grid) -> tuple[SquareIssue, ...]:
        return tuple(SquareIssue(sq, target[sq], grid[sq]) for sq in diff(target, grid))

    # ---- mutations -------------------------------------------------------

    def san(self, move: chess.Move) -> str:
        board = self.board
        if not board.is_legal(move):
            board = board.copy(stack=False)
            board.turn = not board.turn
            board.ep_square = None
        return board.san(move)

    def push(self, move: chess.Move) -> str:
        """Apply the move (swapping the turn first if it belongs to the other side)."""
        if not self.board.is_legal(move):
            self.board.turn = not self.board.turn
            self.board.ep_square = None
        san = self.board.san(move)
        self.board.push(move)
        return san

    def set_fen(self, fen: str) -> None:
        self.board = chess.Board(fen)

    def reset(self) -> None:
        self.board = chess.Board()
