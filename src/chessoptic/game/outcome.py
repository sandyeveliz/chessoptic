"""Game-over detection shared by the session and the providers."""

from __future__ import annotations

import chess

REASONS: dict[chess.Termination, str] = {
    chess.Termination.CHECKMATE: "jaque mate",
    chess.Termination.STALEMATE: "rey ahogado",
    chess.Termination.INSUFFICIENT_MATERIAL: "material insuficiente",
    chess.Termination.SEVENTYFIVE_MOVES: "regla de 75 jugadas",
    chess.Termination.FIVEFOLD_REPETITION: "quíntuple repetición",
    chess.Termination.FIFTY_MOVES: "regla de 50 jugadas",
    chess.Termination.THREEFOLD_REPETITION: "triple repetición",
}


def result_and_reason(board: chess.Board) -> tuple[str, str] | None:
    """("1-0", "jaque mate") when the position is final, else None."""
    outcome = board.outcome(claim_draw=True)
    if outcome is None:
        return None
    return outcome.result(), REASONS.get(outcome.termination, str(outcome.termination).lower())
