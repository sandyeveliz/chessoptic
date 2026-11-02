# Cómo extender ChessOptic

Cuatro puntos de extensión, cada uno detrás de una interfaz chica. En el POC se registran a mano; cuando haya un segundo proveedor externo se agrega un registro con entry points.

## Un proveedor (contra quién / dónde se juega)

Implementá `OutputAdapter` (`src/chessoptic/adapters/base.py`):

```python
from chessoptic.adapters.base import AdapterInfo, EmitFn
from chessoptic.core.events import GameStarted, LinkState, LinkStatus, MoveAccepted, OpponentMove

INFO = AdapterInfo(name="mi_proveedor", label="Mi proveedor", kind="online", both_sides=False)


class MiAdapter:
    @property
    def info(self) -> AdapterInfo:
        return INFO

    def start(self, emit: EmitFn) -> None:
        self._emit = emit
        emit(LinkStatus(LinkState.CONNECTED, "Mi proveedor"))

    def stop(self) -> None: ...

    def start_game(self, board):  # emití GameStarted(game_id, my_color, platform, fen)
        self._emit(GameStarted("id", True, "Mi proveedor", board.fen()))

    def on_move(self, move, board_after):  # la cámara vio una jugada mía
        self._emit(MoveAccepted(move))  # o MoveRejected(move, "motivo")
        ...  # cuando el rival responda: OpponentMove(move, san)

    def end_game(self, result, reason): ...
```

Reglas:

- `emit` puede llamarse desde cualquier hilo; la sesión serializa.
- No emitas `GameOver` por mate/tablas: la sesión lo detecta sola a partir de la posición. Emitilo solo por finales externos (abandono, aborto, tiempo).
- Si el usuario juega ambos bandos (anotación), `both_sides=True` y nunca emitís `OpponentMove`.

Registralo en `src/chessoptic/adapters/__init__.py` (`AVAILABLE` y `create_adapter`). La UI lista `AVAILABLE` sola.

## Un motor local

Implementá `EngineProtocol` (`adapters/local/engine.py`): `name`, `start()`, `play(board) -> Move`, `stop()`. Cualquier motor UCI ya funciona con `UciEngine(path)`; `RandomEngine` y `ScriptedEngine` sirven para probar sin Stockfish. `StockfishAdapter` acepta cualquier `EngineProtocol`, así que un modelo propio o un servicio remoto se enchufa ahí sin tocar la sesión.

## Una fuente de cámara

Implementá `FrameSource` (`capture/source.py`): `name`, `read() -> Frame | None`, `close()`. El pipeline no sabe si los frames vienen de una webcam, un archivo o un celular. Ejemplos: `WebcamSource`, `VideoFileSource`, `ListSource`.

## Un modo de juego

`game/modes.py`: una instancia de `GameMode` (nombre, etiqueta, `has_clock`) registrada en `MODES`. Los modos con reloj van a necesitar hooks en la sesión (inicio/fin de turno, bandera); se agregan cuando llegue el primer modo con tiempo.

## Un motor de voz

La voz tiene dos capas (`ui/voice.py`):

- **`Speaker`** (Strategy): cómo se habla. `SystemSpeaker` usa las voces del sistema
  operativo (Qt TextToSpeech, sin descargas) y es el default; `NeuralSpeaker` reproduce
  audio que genera un `Synthesizer`.
- **`Synthesizer`** (Adapter, `src/chessoptic/speech/base.py`): envuelve una librería de
  TTS con una sola operación, `synthesize(texto, voz) -> Audio` (muestras mono float32).

Para sumar un motor neuronal:

1. Crear `src/chessoptic/speech/<motor>.py` con un `EngineInfo` (nombre, descripción,
   nota de licencia, paquetes pip, módulos a importar, archivos compartidos), el catálogo de
   `VoiceOption` (cada una con sus `Asset` descargables) y la subclase de `Synthesizer`.
   Importar la librería dentro de `synthesize`, no arriba del módulo: es opcional.
2. Registrarlo en `SYNTHESIZERS` (`speech/__init__.py`).
3. Agregar el extra en `pyproject.toml` y el módulo en el override de mypy.

Ajustes lo muestra solo: aparece en **Motor**, el botón **Descargar** instala los paquetes
(`uv pip` o `pip` en el intérprete actual) y baja los modelos a `<datos>/voices/<motor>/`.
Mientras falte algo, se habla con la voz del sistema.

Los paquetes de voz no se incluyen en ChessOptic: el usuario los descarga. Piper y la
fonetización de Kokoro (espeak-ng) son GPL-3.0; por eso quedan como extras opcionales.

## Tema

`theme.qss` en la carpeta de configuración se carga después del tema por defecto y gana. Los widgets tienen `objectName` estables (`header`, `healthPill`, `navBar`, `navButton`, `card`, `stateBlock`, `sectionLabel`, `muted`) y propiedades dinámicas (`level`, `primary`).
