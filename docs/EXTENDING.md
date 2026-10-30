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

## Tema

`theme.qss` en la carpeta de configuración se carga después del tema por defecto y gana. Los widgets tienen `objectName` estables (`header`, `healthPill`, `navBar`, `navButton`, `card`, `stateBlock`, `sectionLabel`, `muted`) y propiedades dinámicas (`level`, `primary`).
