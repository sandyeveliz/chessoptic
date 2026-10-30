"""BoardModel: full position (piece types included) maintained from occupancy changes.

The camera only tells us empty / white / black per square, and it is not perfect: a square a
piece just left may read as "black" because of a neighbour's shadow. So a move is recognised by
its **change set** against the last grid we accepted as showing the current position (the
*reference*), not by an exact comparison with the ideal occupancy:

- every square outside the move must look like it did in the reference;
- every square the move leaves empty must have changed (the camera sees *something* else);
- every square the move occupies must show the right colour.

Castling, en passant and captures fall out of this for free; promotion is the only ambiguous
case (same squares, four possible pieces).
"""

from __future__ import annotations

from dataclasses import dataclass

import chess

from chessoptic.board.occupancy import Grid, Occupancy, diff, from_board
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


def wrong_squares(
    grid: Grid,
    reference: Grid,
    current: Grid,
    target: Grid,
    moved: set[int] | None = None,
) -> tuple[int, ...]:
    """Squares that keep `grid` from showing `target`, reached from `current` (module docstring).

    `moved` are squares whose *image* changed since the reference (from the vision layer).
    Squares the transition occupies must show the right colour and have changed (a persistent
    shadow is not an arriving piece). Squares it vacates must have changed (a black piece's
    shadow still reads black, but the image did change). Untouched empty squares may look as
    before or truly empty.
    """
    known = moved is not None  # the vision layer told us which squares' images changed
    moved = moved or set()
    wrong = []
    for sq in chess.SQUARES:
        in_move = current[sq] != target[sq]
        changed = grid[sq] != reference[sq] or sq in moved
        # A label that flips while the image stays the same is classifier noise (a borderline
        # square at the edge of the frame), never evidence that something happened there.
        stale = known and sq not in moved
        if in_move:
            if target[sq] != Occupancy.EMPTY:
                ok = grid[sq] == target[sq] and changed
            else:
                ok = changed and grid[sq] != Occupancy.WHITE  # vacated: empty or a dark shadow
        elif target[sq] != Occupancy.EMPTY:
            ok = grid[sq] == target[sq] or grid[sq] == reference[sq] or stale
        else:
            # Untouched empty square: as before, truly empty, or a dark phantom (a shadow reads
            # "black"); only a bright reading on a changed image is a real foreign piece.
            ok = grid[sq] != Occupancy.WHITE or reference[sq] == Occupancy.WHITE or stale
        if not ok:
            wrong.append(sq)
    return tuple(wrong)


def changed_squares(
    grid: Grid, reference: Grid, current: Grid, moved: set[int] | None = None
) -> set[int]:
    """Squares that look neither like the reference nor like the ideal current position (by
    label, or by image change on a square that disagrees with the position). Dark phantoms on
    empty squares (shadows) are not counted."""
    known = moved is not None
    moved = moved or set()
    out = set()
    for sq in chess.SQUARES:
        if grid[sq] == current[sq]:
            continue
        if grid[sq] == reference[sq] and sq not in moved:
            continue
        if known and sq not in moved:
            continue  # label noise on an unchanged image
        out.add(sq)
    return out


def is_phantom(sq: int, grid: Grid, current: Grid) -> bool:
    """A dark reading on a square that should be empty: most likely a shadow."""
    return current[sq] == Occupancy.EMPTY and grid[sq] == Occupancy.BLACK


class BoardModel:
    def __init__(self, board: chess.Board | None = None, both_sides: bool = False) -> None:
        self.board = board if board is not None else chess.Board()
        self.both_sides = both_sides
        self.reference: Grid | None = None  # last observed grid accepted for `board`

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

    def reference_grid(self) -> Grid:
        return self.reference if self.reference is not None else self.expected_occupancy()

    def accept(self, grid: Grid) -> None:
        """Remember how the camera sees the current position."""
        self.reference = grid

    def resolve(self, grid: Grid, moved: set[int] | None = None) -> Resolution:
        current = self.expected_occupancy()
        if grid == current:
            self.reference = grid
            return NoChange()
        reference = self.reference_grid()
        changed = changed_squares(grid, reference, current, moved)
        if not changed:
            self.reference = grid
            return NoChange()

        hard = {sq for sq in changed if not is_phantom(sq, grid, current)}
        exact: list[tuple[int, chess.Move]] = []  # (changed squares explained, move)
        partial: list[chess.Move] = []
        for move in self.candidate_moves():
            after = self.occupancy_after(move)
            move_changes = set(diff(current, after))
            if not wrong_squares(grid, reference, current, after, moved):
                exact.append((len(changed & move_changes), move))
            elif hard <= move_changes:
                partial.append(move)

        if exact:
            # Prefer the move that explains the most changed squares (O-O over Rg8 when both
            # fit because a shadow is tolerated on the rook's square).
            best = max(score for score, _ in exact)
            top = [move for score, move in exact if score == best]
            if len({(m.from_square, m.to_square) for m in top}) == 1:
                return Move(top[0]) if len(top) == 1 else Ambiguous(tuple(top))
            partial = top + partial
        if partial:
            return Transient(tuple(partial))
        if not hard:
            self.reference = grid  # only shadows appeared: remember them, nothing happened
            return NoChange()
        issues = tuple(SquareIssue(sq, current[sq], grid[sq]) for sq in sorted(hard))
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

    def push(self, move: chess.Move, observed: Grid | None = None) -> str:
        """Apply the move (swapping the turn first if it belongs to the other side).

        `observed` is the grid that showed the move; it becomes the new reference.
        """
        if not self.board.is_legal(move):
            self.board.turn = not self.board.turn
            self.board.ep_square = None
        san = self.board.san(move)
        self.board.push(move)
        self.reference = observed
        return san

    def pop(self) -> chess.Move:
        """Take back the last move; the camera reference is unknown again."""
        self.reference = None
        return self.board.pop()

    def set_fen(self, fen: str) -> None:
        self.board = chess.Board(fen)
        self.reference = None

    def reset(self) -> None:
        self.board = chess.Board()
        self.reference = None
