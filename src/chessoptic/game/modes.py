"""Game modes (Strategy). The POC ships FreePlay only; timed modes plug in here later."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GameMode:
    name: str
    label: str
    has_clock: bool = False

    def describe(self) -> str:
        return self.label


FREE_PLAY = GameMode(name="free", label="Sin reloj")

MODES: dict[str, GameMode] = {FREE_PLAY.name: FREE_PLAY}


def get_mode(name: str) -> GameMode:
    return MODES.get(name, FREE_PLAY)
