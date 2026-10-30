"""Immutable events and snapshots shared by the core, the adapters and the UI."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class HealthLevel(StrEnum):
    """Driver health 'traffic light'. Never reflects whose turn it is."""

    OK = "ok"
    WARN = "warn"
    ERR = "err"
    IDLE = "idle"


@dataclass(frozen=True)
class ComponentHealth:
    level: HealthLevel
    label: str
    detail: str = ""


@dataclass(frozen=True)
class HealthState:
    level: HealthLevel
    pill_text: str
    camera: ComponentHealth
    board: ComponentHealth
    link: ComponentHealth

    @staticmethod
    def starting() -> HealthState:
        idle = HealthLevel.IDLE
        return HealthState(
            level=idle,
            pill_text="Iniciando",
            camera=ComponentHealth(idle, "Cámara", "buscando"),
            board=ComponentHealth(idle, "Tablero", "sin calibrar"),
            link=ComponentHealth(idle, "Enlace", "inactivo"),
        )
