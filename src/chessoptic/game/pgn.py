"""PGN export of a tracked game."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import chess
import chess.pgn

from chessoptic.core.config import data_dir
from chessoptic.core.events import GameInfo


def build_pgn(info: GameInfo, initial_fen: str | None = None) -> str:
    game = chess.pgn.Game()
    game.headers["Event"] = "ChessOptic"
    game.headers["Site"] = info.platform
    game.headers["Date"] = datetime.now().strftime("%Y.%m.%d")
    game.headers["Round"] = "-"
    if info.my_color is None:
        game.headers["White"] = "Blancas"
        game.headers["Black"] = "Negras"
    else:
        me, other = "Vos", info.platform
        game.headers["White"] = me if info.my_color == chess.WHITE else other
        game.headers["Black"] = me if info.my_color == chess.BLACK else other
    game.headers["Result"] = info.result or "*"
    if initial_fen and initial_fen != chess.STARTING_FEN:
        game.headers["SetUp"] = "1"
        game.headers["FEN"] = initial_fen
        game.setup(chess.Board(initial_fen))

    node: chess.pgn.GameNode = game
    for record in info.moves:
        node = node.add_variation(chess.Move.from_uci(record.uci))
        node.comment = record.wall_time
    return str(game)


def save_pgn(info: GameInfo, initial_fen: str | None = None, directory: Path | None = None) -> Path:
    directory = directory or (data_dir() / "games")
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}.pgn"
    path.write_text(build_pgn(info, initial_fen), encoding="utf-8")
    return path
