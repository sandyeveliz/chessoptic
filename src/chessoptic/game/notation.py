"""Move notation per language: localized SAN for display and a phrase for text-to-speech.

The core keeps standard (English) SAN everywhere, including PGN export. These helpers only
translate at the edges, so they work from the SAN string alone (no board needed).
"""

from __future__ import annotations

import random
import re

import chess

LANGUAGES: tuple[tuple[str, str], ...] = (
    ("es", "Español (R D T A C)"),
    ("en", "English (K Q R B N)"),
)

# SAN piece letter -> letter shown for that language.
_LETTERS: dict[str, dict[str, str]] = {
    "es": {"K": "R", "Q": "D", "R": "T", "B": "A", "N": "C"},
    "en": {"K": "K", "Q": "Q", "R": "R", "B": "B", "N": "N"},
}

_PIECE_WORDS: dict[str, dict[str, str]] = {
    "es": {"K": "Rey", "Q": "Dama", "R": "Torre", "B": "Alfil", "N": "Caballo", "P": "Peón"},
    "en": {"K": "King", "Q": "Queen", "R": "Rook", "B": "Bishop", "N": "Knight", "P": "Pawn"},
}

# Files spelled out so the voice says "efe 3" instead of guessing how to read "f3".
_FILE_WORDS: dict[str, dict[str, str]] = {
    "es": {
        "a": "a",
        "b": "be",
        "c": "ce",
        "d": "de",
        "e": "e",
        "f": "efe",
        "g": "ge",
        "h": "hache",
    },
    "en": {f: f.upper() for f in "abcdefgh"},
}

_WORDS: dict[str, dict[str, str]] = {
    "es": {
        "takes": "toma",
        "to": "a",
        "from": "de",
        "promotes": "corona",
        "check": "jaque",
        "mate": "jaque mate",
        "short": "Enroque corto",
        "long": "Enroque largo",
    },
    "en": {
        "takes": "takes",
        "to": "to",
        "from": "",
        "promotes": "promotes to",
        "check": "check",
        "mate": "checkmate",
        "short": "Short castle",
        "long": "Long castle",
    },
}

_SAN_RE = re.compile(
    r"^(?P<piece>[KQRBN])?(?P<origin>[a-h]?[1-8]?)(?P<capture>x)?(?P<to>[a-h][1-8])"
    r"(?:=(?P<promo>[QRBN]))?(?P<suffix>[+#])?$"
)
_CASTLE_RE = re.compile(r"^(?P<side>O-O(?:-O)?)(?P<suffix>[+#])?$")

_display_language = "es"


def normalize_language(language: str) -> str:
    return language if language in _LETTERS else "en"


def set_display_language(language: str) -> None:
    """Language used by `display_san` (the UI sets it from the config)."""
    global _display_language
    _display_language = normalize_language(language)


def localize_san(san: str, language: str) -> str:
    """'Nxe5' -> 'Cxe5' in Spanish. Castling, squares and suffixes are language-neutral."""
    letters = _LETTERS[normalize_language(language)]
    match = _SAN_RE.match(san)
    if match is None:
        return san
    out = san
    if match.group("piece"):
        out = letters[match.group("piece")] + out[1:]
    if match.group("promo"):
        out = out.replace("=" + match.group("promo"), "=" + letters[match.group("promo")])
    return out


def display_san(san: str) -> str:
    return localize_san(san, _display_language)


def _square_words(square: str, language: str) -> str:
    return f"{_FILE_WORDS[language][square[0]]} {square[1]}"


def spoken_san(san: str, language: str) -> str:
    """A phrase a TTS voice can read: 'Nxe5+' -> 'Caballo toma e 5, jaque'."""
    lang = normalize_language(language)
    words = _WORDS[lang]
    castle = _CASTLE_RE.match(san)
    if castle is not None:
        text = words["long"] if castle.group("side") == "O-O-O" else words["short"]
        suffix = castle.group("suffix")
    else:
        match = _SAN_RE.match(san)
        if match is None:
            return san
        parts: list[str] = []
        piece = match.group("piece")
        origin = match.group("origin")
        if piece:
            parts.append(_PIECE_WORDS[lang][piece])
        if origin:
            # Disambiguation ("Nbd7") or the pawn file of a capture ("exd5").
            spelled = " ".join(_FILE_WORDS[lang][c] if c.isalpha() else c for c in origin)
            parts.append(f"{words['from']} {spelled}".strip() if piece else spelled)
        if match.group("capture"):
            parts.append(words["takes"])
        elif piece:
            parts.append(words["to"])
        parts.append(_square_words(match.group("to"), lang))
        if match.group("promo"):
            parts.append(f"{words['promotes']} {_PIECE_WORDS[lang][match.group('promo')].lower()}")
        text = " ".join(parts)
        text = text[0].upper() + text[1:]
        suffix = match.group("suffix")
    if suffix == "#":
        text += f", {words['mate']}"
    elif suffix == "+":
        text += f", {words['check']}"
    return text


def random_example_san(rng: random.Random | None = None) -> str:
    """A legal move from a random position, to try the voice in the settings.

    Prefers captures, checks, castling and promotions half the time so the less common
    phrases get heard too.
    """
    rng = rng or random.Random()
    board = chess.Board()
    for _ in range(rng.randint(4, 40)):
        moves = list(board.legal_moves)
        if not moves or board.is_game_over():
            break
        board.push(rng.choice(moves))
    if board.is_game_over():
        board = chess.Board()
    moves = list(board.legal_moves)
    special = [
        m
        for m in moves
        if board.is_capture(m) or board.gives_check(m) or board.is_castling(m) or m.promotion
    ]
    pool = special if special and rng.random() < 0.5 else moves
    return board.san(rng.choice(pool))
