# Máquina de estados del driver

Implementada en `src/chessoptic/game/session.py` (`GameSession`). La UI solo refleja `DriverState`; no decide nada.

## Estados

| Fase | Estado | Qué significa | Bloque de estado (UI.md) |
|---|---|---|---|
| Standby | `verifying_board` | Falta armar la posición inicial. | Tarjeta "Armá la posición inicial" con contadores/casillas marcadas. |
| Standby | `ready` | Posición inicial completa. Con rival: botón **Empezar partida**. En solo seguimiento: la primera jugada legal arranca la partida. | Tarjeta "Listo para jugar". |
| Standby | `paused` | Detección pausada por el usuario. (Pendiente en la UI.) | — |
| Partida | `my_turn` | Me toca mover (en solo seguimiento: le toca al bando que mueve). | Azul relleno. |
| Partida | `moving` | Hay movimiento sobre el tablero; se espera estabilidad. | Azul + "Detectando…". |
| Partida | `opponent_turn` | Mi jugada fue aceptada; espero la del rival. | Borde gris. |
| Partida | `replay` | El rival jugó; hay que reproducirla en el tablero físico. | Borde celeste + SAN grande + origen/destino en la cámara. |
| Partida | `promotion` | La ocupación es compatible con 4 jugadas (promoción). | "¿Qué pieza pusiste?" con 4 botones (o default de Ajustes). |
| Partida | `mismatch` | La posición física no coincide con la esperada desde hace más de 2 s. | Borde rojo + casillas en rojo + **Resincronizar**. |
| Partida | `link_lost` | El proveedor se desconectó durante la partida. | Tarjeta roja. |
| Partida | `game_over` | Fin de partida (mate, tablas, abandono, terminada desde la UI). | Resultado + **Exportar PGN** / **Nueva partida**. |

## Transiciones

| Desde | Evento | A |
|---|---|---|
| `verifying_board` | `InitialPositionCheck.complete` | `ready` (reinicia el modelo) |
| `ready` (con rival) | `InitialPositionCheck` incompleta | `verifying_board` |
| `ready` (con rival) | acción **Empezar partida** → `GameStarted` | `my_turn` si me toca, si no `opponent_turn` |
| `ready` (seguimiento) | `MoveDetected` (jugada legal de cualquier bando) | arranca la partida → `my_turn` |
| `ready` (seguimiento) | `PositionMismatch` | `verifying_board` |
| `my_turn` | ocupación inestable | `moving` |
| `moving` | ocupación estable sin cambio | `my_turn` |
| `my_turn` / `moving` | `MoveDetected` → proveedor → `MoveAccepted` | `opponent_turn` (con rival) · `my_turn` (seguimiento) |
| `my_turn` | `MoveDetected` → `MoveRejected` | `mismatch` (se deshace la jugada en el modelo) |
| `my_turn` | `MoveAmbiguous` | `promotion` (o se resuelve con el default) |
| `promotion` | acción **pieza elegida** | como `MoveDetected` |
| `my_turn` / `replay` | `PositionMismatch` (sostenido > 2 s) | `mismatch` (recuerda el estado previo) |
| `mismatch` | `PositionMatched` o acción **Resincronizar** | estado previo |
| `opponent_turn` | `OpponentMove` | `replay` (el tracker espera esa jugada) |
| `replay` | `PositionMatched` | `my_turn` (registra la jugada del rival) |
| cualquiera en partida | `LinkStatus(lost)` | `link_lost` |
| `link_lost` | `LinkStatus(connected)` | estado previo |
| cualquiera en partida | `GameOver` / acción **Terminar** | `game_over` |
| `game_over` | acción **Nueva partida** | `verifying_board` |

## Estados de detección (dentro de un turno)

`DetectionState` (`core/events.py`), publicado por la sesión a partir de lo que resuelve el
tracker frame a frame. Es la segunda línea del bloque de estado y lo que decide qué casillas se
resaltan. Cubre tanto mi jugada como la reproducción de la del rival.

| Fase | Cuándo | Qué muestra la UI | Sale cuando |
|---|---|---|---|
| `waiting` | Tablero quieto e igual a la posición esperada. | "Esperando tu jugada" / "Esperando que reproduzcas c5". | Aparece movimiento. |
| `hand` | La imagen se mueve (mano, pieza en el aire). | "Movimiento sobre el tablero…". No se interpreta nada. | La imagen queda quieta `stability_ms`. |
| `reading` | Primer frame quieto tras el movimiento. | (implícito; dura un frame) | Se resuelve en una de las siguientes. |
| `lifted` | Las casillas que cambiaron son parte de una jugada legal pero no la completan (pieza levantada, enroque a medias). | "Levantaste el peón de e2; esperando que la apoyes." Origen resaltado. | Se apoya la pieza (→ `seen`) o vuelve a su lugar (→ `waiting`). |
| `seen` | Una única jugada legal explica el cambio. Se exige verla en 2 frames quietos seguidos. | "Vi e4, confirmando…" Origen y destino resaltados. | Segundo frame igual → `accepted`. Distinto → se vuelve a resolver. |
| `accepted` | La jugada se aceptó: en seguimiento se anota; con proveedor se envía (`opponent_turn`) o, si era la del rival, queda verificada (`my_turn`). | "Jugada aceptada: e4" / "c5 verificada en el tablero". | Cambia el estado del driver. |
| `unexplained` | Tablero quieto que no coincide con ninguna jugada legal ni con un cambio parcial. Corre la cuenta de `mismatch_grace_ms` (3 s). | "No cuadra con ninguna jugada (d4, e5) · 2 s" en ámbar; casillas en rojo. | Movimiento (se reinicia) o el tablero vuelve a cuadrar (→ `waiting`), o vence (→ `mismatch`). |
| `mismatch` | Venció la cuenta. El driver pasa a `mismatch`. | Tarjeta roja + **Resincronizar**; nombra la jugada pendiente si la hay. | El tablero vuelve a cuadrar (→ estado previo) o **Resincronizar**. |
| `thinking` | `opponent_turn`: el rival o el motor piensan. | "El rival piensa…" | Llega `OpponentMove` (→ `replay`, fase `waiting`). |
| `idle` | Standby, fin de partida, promoción (se resuelve con botones). | (sin línea) | — |

Reglas que hacen a la robustez (ver `board/model.py`):

- Una jugada necesita que **origen y destino hayan cambiado en la imagen** respecto al último frame aceptado y que el destino muestre el color correcto. Un cambio de etiqueta sobre una imagen que no cambió es ruido y no cuenta.
- Lecturas "negras" en casillas que deberían estar vacías se tratan como sombras: se toleran y nunca generan `unexplained` por sí solas.
- Casillas fuera de la jugada no la bloquean salvo que su imagen haya cambiado y además contradigan la posición.
- Entre varias jugadas que encajan gana la que explica más casillas (enroque sobre mover la torre).

## Reglas

- El semáforo (`HealthState`) es independiente: solo cámara, tablero y enlace.
- El tracker solo mira frames **estables** (quietos durante `stability_ms`).
- Un cambio parcial compatible con alguna jugada legal (pieza levantada, enroque a medio hacer) no genera eventos: se espera.
- En solo seguimiento el modelo acepta jugadas legales de ambos bandos.
- Los eventos del proveedor pueden llegar desde cualquier hilo; la sesión los serializa con un lock.
