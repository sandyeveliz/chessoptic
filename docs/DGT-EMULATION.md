# ChessOptic como tablero compatible con DGT — relevamiento

Objetivo: que Chessconnect (y cualquier software que hable con tableros DGT: LiveChess, PicoChess, Fritz…) vea a ChessOptic como un tablero electrónico. Este documento revisa qué pide el protocolo, qué ya tenemos, qué falta, y qué queda de nuestro lado, que es lo importante: **el protocolo DGT describe un tablero que nunca se equivoca; la cámara sí. Todo lo que la cámara pueda errar lo tenemos que resolver nosotros antes de que llegue al protocolo.**

Las constantes del protocolo salen de drivers abiertos basados en la especificación oficial de DGT (dgtchess, dgtdrv, picochess); se confirman byte a byte en el spike.

## 1. Qué es un tablero DGT para el software

Un DGT es un **sensor pasivo de un solo sentido**: el tablero le cuenta al PC qué pieza hay en cada casilla, y nada más. No sabe de partidas, turnos, legalidad ni rival. Toda la inteligencia está del lado del PC (Chessconnect, LiveChess), que mira la secuencia de cambios y deduce las jugadas.

Conexión: puerto serie (USB o Bluetooth clásico), 9600 baudios. El PC manda comandos de un byte; el tablero responde con mensajes `[id | 0x80] [largo alto] [largo bajo] [datos…]` (largo de 7 bits por byte, incluye la cabecera).

| El PC pide | Byte | El tablero responde | Contenido |
|---|---|---|---|
| Reset | `0x40` | nada | vuelve a modo inactivo |
| Volcado del tablero | `0x42` | `DGT_BOARD_DUMP` (`0x06`) | 64 bytes, una pieza por casilla, de a8 a h1 |
| Modo "actualizar por casilla" | `0x43` / `0x44` (`UPDATE` / `UPDATE_BRD`) | `DGT_FIELD_UPDATE` (`0x0e`) cada vez que cambia una casilla | `[casilla][pieza]` |
| Modo "actualizar amable" | `0x4b` (`UPDATE_NICE`) | igual que arriba, más mensajes de reloj | — |
| Número de serie | `0x45` | `DGT_SERIALNR` (`0x11`) | texto, ej. `12345` |
| Serie largo | `0x55` | `DGT_LONG_SERIALNR` (`0x22`) | texto |
| Versión | `0x4d` | `DGT_VERSION` (`0x13`) | `[mayor][menor]` |
| Marca | `0x47` | `DGT_TRADEMARK` (`0x12`) | texto "Digital Game Technology…" |
| Reloj | `0x41` | `DGT_BWTIME` (`0x0d`) | tiempos blancas/negras y banderas; "sin reloj" es un estado válido |
| Batería (tableros Bluetooth) | `0x4c` | `DGT_BATTERY_STATUS` (`0x20`) | nivel |
| Mensaje al reloj DGT 3000 | `0x2b` + datos | ack por `BWTIME` | texto/tiempos a mostrar en el reloj |

Códigos de pieza: vacío `0`; blancas peón `1`, torre `2`, caballo `3`, alfil `4`, rey `5`, dama `6`; negras peón `7`, torre `8`, caballo `9`, alfil `10`, rey `11`, dama `12`. Casilla `0` = a8, `63` = h1.

Cómo ve una jugada el software: una secuencia de `FIELD_UPDATE`. Para e2–e4: `e2 → vacío`, `e4 → peón blanco`. Captura exd5: `d5 → vacío` (sacan la pieza comida), `e4 → vacío`, `d5 → peón blanco` (en cualquier orden razonable). Enroque corto: rey e1→g1 y torre h1→f1, cuatro actualizaciones. Al paso: tres. Promoción: el peón sale y entra la dama. El software compara contra las jugadas legales de la partida en curso y tolera estados intermedios (pieza en el aire) un rato; si la secuencia no cierra, avisa "posición incorrecta".

Lo que **no** viaja por el protocolo: la jugada del rival (el software la muestra en pantalla y espera que el humano la reproduzca en el tablero), los botones (rendirse, tablas, atrás: se hacen en la extensión o en el sitio), y cualquier noción de error de detección.

## 2. Lo que ya tenemos y cómo mapea

| Necesidad | Lo que hay | Estado |
|---|---|---|
| Saber qué **pieza** hay en cada casilla (la cámara no lo ve) | `BoardModel` lleva la posición completa con python-chess; `piece_letters()` ya lo usa el overlay. | ✅ Alcanza: el volcado DGT sale de `board.piece_map()`. |
| Jugadas de **ambos bandos** desde la cámara | Modo "Solo seguimiento" (`both_sides=True`): acepta cualquier jugada legal de cualquier color. | ✅ Es exactamente el modo que necesita DGT, porque la jugada del rival también la hace el humano en el tablero. |
| Jugada **confirmada**, no lectura cruda | Cambio de imagen contra el último frame aceptado, tolerancia a sombras, dos frames estables, fases de detección (`docs/STATES.md`). | ✅ Es la pieza clave (§3). |
| Interfaz para "a dónde van las jugadas" | `OutputAdapter`: `start(emit)`, `start_game`, `on_move(move, board_after)`, `end_game`; eventos `LinkStatus`, `GameStarted`, `GameOver`… | ✅ Un `DgtBoardAdapter` entra como proveedor "Chessconnect / DGT" sin tocar la sesión. |
| Deshacer en el modelo | `BoardModel.pop()` existe. | ⚠️ Falta el flujo de usuario (§4). |
| Estado de enlace y salud en la UI | `LinkStatus`, chip "Enlace", tarjeta "Enlace perdido". | ✅ Se reutiliza para "puerto abierto / Chessconnect conectado / desconectado". |
| Diagnóstico | `chessoptic doctor`. | ⚠️ Falta detectar el puerto virtual (§4). |

## 3. La frontera: qué es del tablero y qué es nuestro

Decisión de diseño central: **el emulador DGT solo emite jugadas confirmadas**, nunca la ocupación cruda de la cámara.

Un DGT real manda cada cambio físico al instante, incluido el ruido (una pieza que se desplaza un milímetro no cambia nada, pero una mano que tapa una casilla no existe para los sensores). Nosotros tenemos sombras, manos, reflejos y bordes de encuadre. Si mandáramos la lectura cruda, Chessconnect vería piezas que aparecen y desaparecen y declararía posición incorrecta todo el tiempo. En cambio:

1. La cámara lee; el tracker pasa por `hand → lifted → seen → accepted` como hoy.
2. Solo en `accepted` el emulador genera la secuencia de `FIELD_UPDATE` que un DGT habría mandado para esa jugada (origen vacío, destino con la pieza; más los movimientos de torre, pieza capturada o promoción), con unos milisegundos entre mensajes para parecer un tablero.
3. Entre jugadas, el tablero emulado está "quieto": no se emite nada aunque la cámara dude.

Consecuencia feliz: **para Chessconnect somos un tablero que nunca produce estados intermedios raros**, mejor que un DGT real. Consecuencia a vigilar: la latencia de una jugada es la nuestra (quietud de 750 ms más confirmación), y el software del otro lado no sabe que estamos "pensando"; con reloj corriendo, cada segundo cuenta (§4, relojes).

Lo que queda **de nuestro lado**, y cómo lo controlamos y mostramos:

| Situación | Quién la ve | Qué hacemos | Qué muestra el panel |
|---|---|---|---|
| Sombra, mano, reflejo (`unexplained`) | Solo nosotros | No se emite nada. Cuenta regresiva de 3 s como hoy. | Línea de detección en ámbar; casillas en rojo. Nada llega al sitio. |
| Posición no coincide (`mismatch`) | Solo nosotros | No se emite nada hasta que el tablero vuelva a cuadrar. | Tarjeta roja con las casillas. Si el reloj corre, mostrarlo **grande**: el sitio no se entera de que estamos trabados. |
| Jugada ilegal hecha físicamente | Nosotros (el modelo no la acepta) | No se emite. | "Esa jugada no es legal: volvé la pieza." Un DGT real la mandaría y el sitio se quejaría; nosotros la frenamos antes. |
| Jugada legal pero **no era la del rival** (el humano reproduce mal la jugada del rival) | Chessconnect (compara con el sitio); nosotros no, si no leemos el sitio | La emitimos (es legal para nuestro modelo). Chessconnect marca posición incorrecta. El usuario corrige en el tablero; nosotros detectamos la vuelta atrás como jugada y **tenemos que deshacer** en el modelo, no registrar "otra jugada". | Botón **Deshacer** y, mejor, detección automática: si la jugada observada es exactamente la inversa de la última emitida, es un deshacer (§4). |
| El sitio rechaza mi jugada (no era mi turno, partida terminada, premove) | Chessconnect | Igual que arriba: deshacer. | Igual. |
| Cámara perdida en plena partida | Nosotros | Mantener el puerto abierto (un DGT desconectado cortaría el serie y Chessconnect reconectaría); no emitir nada. | Tarjeta "Cámara perdida" con el tiempo que lleva; al volver, verificar que el tablero sigue en la posición del modelo. |
| Chessconnect cierra o reabre el puerto | Nosotros (el serie) | Responder reset, versión y serie; al `SEND_BRD` responder el volcado de **la posición del modelo**. | Chip "Enlace: Chessconnect conectado / esperando conexión". |
| Partida retomada (ya hay jugadas en el sitio) | Chessconnect espera ver esa posición en el tablero | Hoy no podemos: el modelo solo arranca desde la inicial. Para el spike: solo partidas nuevas. | — (gap §4) |
| Fin de partida | Chessconnect / sitio | No nos enteramos por el protocolo. El usuario termina en el panel o reordena el tablero. | Al detectar posición inicial de nuevo, ofrecer "nueva partida". |

## 4. Lo que falta construir

Ordenado por lo que bloquea el spike primero.

**Para el spike (PR 2):**

1. `adapters/eboard/dgt.py`: codificador y decodificador del protocolo (mensajes, largos de 7 bits, códigos de pieza, volcado, actualización por casilla, serie, versión, marca, reloj "no conectado", batería). Puro Python, sin hilo, testeable con bytes en memoria.
2. `adapters/eboard/transport.py`: puerto serie con `pyserial` (dependencia nueva) en un hilo que lee comandos y escribe respuestas; abstracto para poder enchufar un par de pipes en memoria en las pruebas. Puerto en Ajustes.
3. `adapters/eboard/adapter.py` (`DgtBoardAdapter`, proveedor "Chessconnect / tablero DGT"): `both_sides`; `start_game` responde volcados desde el modelo; `on_move` traduce la jugada confirmada a la secuencia de `FIELD_UPDATE`; `LinkStatus` según el puerto esté abierto y haya tráfico del otro lado.
4. `doctor`: detectar com0com (Windows) o un pty de `socat`; explicar cómo crearlo.
5. Guía `docs/INTEGRATION.md` (inglés) con el paso a paso: crear el par de puertos, elegir el puerto en ChessOptic, elegir DGT y el otro puerto en Chessconnect, jugar contra la IA de lichess.

**Para que sea usable de verdad (PR 3, protocolo de partida):**

6. **Deshacer**, en dos formas: botón, y automático cuando la jugada observada es la inversa exacta de la última emitida (cubre "reproduje mal la jugada del rival" y "el sitio la rechazó"). En el emulador, deshacer es emitir las actualizaciones inversas.
7. **Reloj visible aunque no lo tengamos**: no sabemos los tiempos del sitio por el protocolo, pero sí cuándo emitimos cada jugada; mostrar "tu jugada lleva N segundos sin confirmarse" y avisar fuerte cuando una detección se traba, porque el reloj del sitio sigue.
8. **Jugada del rival en el panel.** El protocolo no la trae. Opciones, de más simple a más completa: (a) nada, el usuario la mira en Chessconnect como cualquier dueño de un DGT sin LEDs; (b) para lichess, leerla del stream de la Board API con un token de solo lectura y mostrarla y decirla por voz como hoy (`expect` del tracker vuelve a funcionar); (c) emular además un **reloj DGT 3000**: Chessconnect puede mandar texto al reloj (la jugada del rival, los tiempos) y nuestro panel lo mostraría, y el reloj tiene botones (que servirían para rendirse / tablas si Chessconnect los mapea). La (c) es la que convierte el panel en un tablero completo y es lo que hay que verificar en el spike mirando qué le manda Chessconnect a un DGT 3000.
9. **Arrancar desde una posición dada**: para retomar partidas; el modelo acepta un FEN y el panel pide armar esa posición (el chequeo de posición inicial generalizado a cualquier posición).
10. Latencia: medir de verdad cuánto tardamos de "pieza soltada" a "actualización emitida"; bajar la ventana de quietud a 500 ms si la cámara lo permite, y confirmar con un frame en vez de dos cuando la confianza es alta.

## 5. Preguntas que responde el spike

1. ¿Chessconnect lista puertos serie virtuales (Web Serial sin filtro de VID/PID)? Si no, plan B BLE.
2. ¿Qué secuencia manda al conectar (reset, versión, serie, volcado, modo de actualización)? Nuestro emulador tiene que contestarla toda.
3. ¿Acepta una jugada emitida como dos actualizaciones seguidas o necesita tiempos entre mensajes?
4. ¿Qué le manda a un reloj DGT 3000, y lo requiere o es opcional? Decide la opción 8(c).
5. ¿Cómo se comporta si el tablero reporta una posición distinta a la de la partida (partida retomada)? Decide la prioridad del punto 9.
6. ¿Pide el volcado solo al conectar o periódicamente? Decide si "deshacer" necesita un volcado completo o alcanza con actualizaciones inversas.

Con eso respondido, el PR 5 (proveedor online) deja de ser investigación y es solo trabajo.
