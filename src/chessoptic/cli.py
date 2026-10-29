"""Command line entry point: `chessoptic`, `chessoptic doctor`."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from chessoptic import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="chessoptic",
        description="Driver de un tablero electrónico de ajedrez cuyo sensor es una webcam.",
    )
    parser.add_argument("--version", action="version", version=f"chessoptic {__version__}")
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="abre la ventana (offscreen si no hay pantalla), espera un segundo y sale",
    )
    sub = parser.add_subparsers(dest="command")
    doctor = sub.add_parser(
        "doctor", help="revisa Python, dependencias, cámaras, Stockfish y permisos del sistema"
    )
    doctor.add_argument("--json", action="store_true", help="salida en JSON")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "doctor":
        from chessoptic.doctor import run_doctor

        return run_doctor(as_json=bool(args.json))

    from chessoptic.ui.app import run_app

    return run_app(smoke=bool(args.smoke))
