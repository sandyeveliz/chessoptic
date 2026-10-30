"""OutputAdapter: the interface every provider (local engine, online platform) implements.

POC note: adapters are synchronous and report back through an `emit` callback, which may be
invoked from any thread. The session serialises everything behind its own lock. An asyncio
runner can wrap this later for streaming providers (Lichess) without changing the interface.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

import chess

EmitFn = Callable[[object], None]


@dataclass(frozen=True)
class AdapterInfo:
    name: str
    label: str
    kind: str  # "local" | "online"
    both_sides: bool = False  # True when the user plays both colours (tracking)


class OutputAdapter(Protocol):
    @property
    def info(self) -> AdapterInfo: ...

    def start(self, emit: EmitFn) -> None:
        """Connect / announce. Emits LinkStatus."""

    def stop(self) -> None: ...

    def start_game(self, board: chess.Board) -> None:
        """Begin a game from `board`. Emits GameStarted (and OpponentMove if it moves first)."""

    def on_move(self, move: chess.Move, board_after: chess.Board) -> None:
        """A move was detected on the physical board. Emits MoveAccepted / MoveRejected, then
        OpponentMove when the provider replies, or GameOver."""

    def end_game(self, result: str, reason: str) -> None:
        """The user ended the game from the UI."""
