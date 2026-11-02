"""Speech synthesis contracts, independent of Qt.

A `Synthesizer` adapts a third-party TTS library (Piper, Kokoro, ...) to one interface:
text in, audio samples out. Each one declares what it needs on disk (`Asset`) and which
Python packages it imports, so the app can offer them as optional downloads.
"""

from __future__ import annotations

import importlib.util
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import numpy.typing as npt


@dataclass(frozen=True)
class Asset:
    """A model file downloaded on demand into the engine's folder."""

    url: str
    filename: str
    size_mb: int  # approximate, for the UI


@dataclass(frozen=True)
class VoiceOption:
    id: str
    label: str
    language: str  # "es" | "en"
    assets: tuple[Asset, ...] = ()  # files only this voice needs


@dataclass(frozen=True)
class EngineInfo:
    name: str
    label: str
    description: str
    license_note: str
    packages: tuple[str, ...]  # pip requirement specifiers
    modules: tuple[str, ...]  # import names that prove the packages are installed
    shared_assets: tuple[Asset, ...] = ()  # files every voice needs


@dataclass(frozen=True)
class Audio:
    samples: npt.NDArray[np.float32]  # mono, -1..1
    sample_rate: int


@dataclass(frozen=True)
class Download:
    """What's missing before a voice can speak."""

    packages: tuple[str, ...]
    assets: tuple[Asset, ...]

    @property
    def size_mb(self) -> int:
        # Packages (onnxruntime + the engine) weigh roughly 60-110 MB once installed.
        return sum(a.size_mb for a in self.assets) + (80 if self.packages else 0)

    @property
    def empty(self) -> bool:
        return not self.packages and not self.assets


class Synthesizer(ABC):
    """Adapter over one TTS library. Methods may block; call them off the GUI thread."""

    info: EngineInfo

    def __init__(self, folder: Path) -> None:
        self.folder = folder

    @abstractmethod
    def voices(self) -> list[VoiceOption]: ...

    @abstractmethod
    def synthesize(self, text: str, voice: VoiceOption) -> Audio: ...

    # ---- availability (shared) ------------------------------------------------

    def voices_for(self, language: str) -> list[VoiceOption]:
        return [v for v in self.voices() if v.language == language]

    def find_voice(self, voice_id: str | None, language: str) -> VoiceOption | None:
        options = self.voices_for(language)
        chosen = next((v for v in options if v.id == voice_id), None)
        if chosen is None:
            # Prefer a voice that is already downloaded over the catalogue's first entry.
            chosen = next((v for v in options if self.missing(v).empty), None)
        return chosen or (options[0] if options else None)

    def missing_packages(self) -> tuple[str, ...]:
        installed = all(importlib.util.find_spec(m) is not None for m in self.info.modules)
        return () if installed else self.info.packages

    def missing(self, voice: VoiceOption) -> Download:
        assets = tuple(
            a for a in (*self.info.shared_assets, *voice.assets) if not self.path(a).exists()
        )
        return Download(self.missing_packages(), assets)

    def path(self, asset: Asset) -> Path:
        return self.folder / asset.filename
