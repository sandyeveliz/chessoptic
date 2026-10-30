"""`chessoptic doctor`: explain what is missing on this machine, per OS."""

from __future__ import annotations

import importlib
import json
import platform
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass

from chessoptic.core.config import load_config


@dataclass
class CheckResult:
    name: str
    ok: bool | None  # None = not evaluated
    detail: str
    hint: str = ""

    @property
    def symbol(self) -> str:
        return {True: "✓", False: "✗", None: "-"}[self.ok]


def check_python() -> CheckResult:
    version = ".".join(str(v) for v in sys.version_info[:3])
    ok = sys.version_info >= (3, 12)
    return CheckResult(
        "Python",
        ok,
        f"{version} ({platform.system()} {platform.machine()})",
        "" if ok else "Se necesita Python 3.12 o superior: `uv python install 3.12`.",
    )


def check_dependency(module: str, label: str, pip_name: str) -> CheckResult:
    try:
        mod = importlib.import_module(module)
    except ImportError as exc:
        return CheckResult(label, False, str(exc), f"Instalá la dependencia `{pip_name}`.")
    version = getattr(mod, "__version__", None) or getattr(mod, "__file__", "")
    return CheckResult(label, True, str(version))


def check_cameras() -> CheckResult:
    from chessoptic.capture.webcam import list_cameras

    try:
        cameras = list_cameras()
    except Exception as exc:
        return CheckResult("Cámaras", False, f"error al enumerar: {exc}", _camera_hint())
    if not cameras:
        return CheckResult("Cámaras", False, "ninguna cámara responde", _camera_hint())
    detail = ", ".join(f"#{c.index} {c.label}" for c in cameras)
    return CheckResult("Cámaras", True, detail)


def _camera_hint() -> str:
    system = platform.system()
    if system == "Windows":
        return (
            "Configuración → Privacidad y seguridad → Cámara: permitir que las apps de "
            "escritorio accedan a la cámara. Cerrá otras apps que la estén usando."
        )
    if system == "Darwin":
        return (
            "macOS pide permiso de cámara a la app que lanza el proceso (Terminal, VS Code). "
            "Revisá Ajustes → Privacidad y seguridad → Cámara."
        )
    return (
        "Verificá que exista /dev/video* y que tu usuario esté en el grupo `video` "
        "(`sudo usermod -aG video $USER`, luego cerrá sesión). `v4l2-ctl --list-devices` ayuda."
    )


def stockfish_executable() -> str | None:
    configured = load_config().stockfish_path
    if configured and shutil.which(configured):
        return configured
    return shutil.which("stockfish")


def check_stockfish() -> CheckResult:
    exe = stockfish_executable()
    if not exe:
        return CheckResult(
            "Stockfish",
            False,
            "no está en el PATH ni configurado",
            _stockfish_hint(),
        )
    try:
        proc = subprocess.run(
            [exe],
            input="uci\nquit\n",
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return CheckResult("Stockfish", False, f"{exe}: {exc}", _stockfish_hint())
    name = next((ln for ln in proc.stdout.splitlines() if ln.startswith("id name")), "")
    if "uciok" not in proc.stdout:
        return CheckResult("Stockfish", False, f"{exe} no respondió `uciok`", _stockfish_hint())
    return CheckResult("Stockfish", True, f"{name.removeprefix('id name ').strip()} ({exe})")


def _stockfish_hint() -> str:
    system = platform.system()
    if system == "Windows":
        return (
            "Bajá el zip de https://stockfishchess.org/download/ y agregá la carpeta al PATH, "
            "o indicá la ruta del .exe en Ajustes."
        )
    if system == "Darwin":
        return "`brew install stockfish`"
    return "`sudo apt install stockfish` (o el paquete de tu distro)"


def check_bluetooth() -> CheckResult:
    return CheckResult(
        "Bluetooth",
        None,
        "no evaluado",
        "Solo hace falta para proveedores online por BLE (más adelante).",
    )


def run_checks() -> list[CheckResult]:
    return [
        check_python(),
        check_dependency("numpy", "numpy", "numpy"),
        check_dependency("cv2", "OpenCV", "opencv-python-headless"),
        check_dependency("chess", "python-chess", "chess"),
        check_dependency("PySide6", "PySide6", "PySide6"),
        check_cameras(),
        check_stockfish(),
        check_bluetooth(),
    ]


def _force_utf8_stdout() -> None:
    """Windows consoles default to a legacy code page that cannot print ✓ / ✗."""
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(encoding="utf-8", errors="replace")


def run_doctor(as_json: bool = False) -> int:
    _force_utf8_stdout()
    results = run_checks()
    if as_json:
        print(json.dumps([asdict(r) for r in results], ensure_ascii=False, indent=2))
    else:
        width = max(len(r.name) for r in results)
        for r in results:
            print(f"{r.symbol} {r.name.ljust(width)}  {r.detail}")
            if r.hint and r.ok is not True:
                print(f"  {' ' * width}  → {r.hint}")
    failed = [r for r in results if r.ok is False]
    return 1 if failed else 0
