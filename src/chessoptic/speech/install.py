"""Installs what a voice needs: Python packages (uv or pip) and model files (HTTPS).

Runs in a worker thread; reports progress through a callback and stops when `cancel`
is set. Model files are written as `<name>.part` and renamed once complete, so an
interrupted download never looks installed.
"""

from __future__ import annotations

import importlib
import logging
import shutil
import subprocess
import sys
import threading
import urllib.request
from collections.abc import Callable
from pathlib import Path

from chessoptic.speech.base import Download

log = logging.getLogger(__name__)

Progress = Callable[[str, float], None]  # (what is happening, 0..1 or -1 when unknown)

_CHUNK = 256 * 1024


class InstallError(RuntimeError):
    pass


class InstallCancelledError(InstallError):
    pass


def package_command(packages: tuple[str, ...]) -> list[str]:
    """How to install packages into the running interpreter (uv venvs ship without pip)."""
    uv = shutil.which("uv")
    if uv is not None:
        return [uv, "pip", "install", "--python", sys.executable, *packages]
    return [sys.executable, "-m", "pip", "install", *packages]


def install(download: Download, folder: Path, progress: Progress, cancel: threading.Event) -> None:
    if download.packages:
        _install_packages(download.packages, progress)
    folder.mkdir(parents=True, exist_ok=True)
    total = len(download.assets)
    for index, asset in enumerate(download.assets, start=1):
        if cancel.is_set():
            raise InstallCancelledError("Descarga cancelada.")
        label = f"Descargando {asset.filename} ({index}/{total})"
        _fetch(asset.url, folder / asset.filename, label, progress, cancel)


def _install_packages(packages: tuple[str, ...], progress: Progress) -> None:
    command = package_command(packages)
    progress(f"Instalando {', '.join(packages)}…", -1.0)
    log.info("installing packages: %s", " ".join(command))
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    result = subprocess.run(
        command, capture_output=True, text=True, creationflags=flags, check=False
    )
    if result.returncode != 0:
        log.error("package install failed: %s", result.stderr)
        tail = (result.stderr or result.stdout).strip().splitlines()[-1:] or ["sin detalle"]
        raise InstallError(f"No se pudo instalar {', '.join(packages)}: {tail[0]}")
    importlib.invalidate_caches()


def _fetch(url: str, target: Path, label: str, progress: Progress, cancel: threading.Event) -> None:
    part = target.with_name(target.name + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": "ChessOptic"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response, part.open("wb") as out:
            size = int(response.headers.get("Content-Length") or 0)
            done = 0
            while chunk := response.read(_CHUNK):
                if cancel.is_set():
                    raise InstallCancelledError("Descarga cancelada.")
                out.write(chunk)
                done += len(chunk)
                progress(label, done / size if size else -1.0)
        if size and part.stat().st_size != size:
            raise InstallError(f"{target.name} quedó incompleto; probá de nuevo.")
        part.replace(target)
    except OSError as exc:
        raise InstallError(f"No se pudo descargar {target.name}: {exc}") from exc
    finally:
        part.unlink(missing_ok=True)
