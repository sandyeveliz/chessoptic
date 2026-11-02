# Plan v0.2 — De POC a tablero "de verdad"

Estado de partida (2026-11-02): v0.1.0 publicada y, encima, voz con notación es/en, pantalla de inicio, política de seguridad y contribución (PRs #6–#10). Este documento ordena los tres objetivos que pediste para la v0.2 y los convierte en PRs con alcance, orden y criterio de cierre.

Los tres objetivos:

1. README en inglés por defecto con versión en español siempre reflejada, pensado para presentar el proyecto afuera (en particular al autor de Chessconnect).
2. Conexión con Chessconnect "como tablero virtual": investigar cómo, qué pedir, y antes **estandarizar nuestras funcionalidades** a lo que las plataformas esperan de un tablero (estados, esperas, errores).
3. UI seria: design system, control de estados, UX.

## 0. Lo que cambia la estrategia: qué es Chessconnect por dentro

Lo que encontré (fuentes al final):

- Chessconnect es una **extensión de Chrome** (más apps iOS y Android) que habla con los tableros por **USB o Bluetooth LE** (DGT por Bluetooth clásico) y con los sitios por sus **APIs oficiales** (chess.com y lichess; en lichess, solo rápidas, clásicas y correspondencia; blitz contra la IA o por desafío directo). Soporta Certabo, Chessnut, ChessUp, DGT, Millennium, TabuTronic, iChessOne, House of Staunton y varios más. No publica API, protocolo ni GitHub; el contacto es el servidor de Discord del autor.
- Es decir: **Chessconnect no "conecta tableros virtuales", conecta protocolos de tablero**. Un tablero es, para Chessconnect, un dispositivo serie o BLE que habla el protocolo de un fabricante. Si ChessOptic habla uno de esos protocolos por un transporte que Chrome pueda abrir, Chessconnect lo trata como ese tablero sin que nadie tenga que darnos permiso.
- Hay precedentes exactos de esto: OpenChess (tablero casero) emula un tablero BLE conocido para usarlo con Chessconnect; DGTCentaurMods emula el protocolo Bluetooth de Millennium; el protocolo ChessLink de Millennium está documentado por terceros (python-mchess, `magic-board.md`); el protocolo serie de DGT está publicado por DGT ("Electronic Board Protocol Description") e implementado en varios drivers abiertos.
- Dato clave para nosotros: el **protocolo DGT reporta el tipo de pieza por casilla** (la cámara no lo distingue, pero la lógica de partida sí lo sabe), así que podemos emular un DGT con fidelidad total: volcados de tablero completos con códigos de pieza, y actualizaciones por casilla.
- chess.com tiene un canal oficial: formulario "OAuth & Connected Board Access" en su Developer Community. Anecdóticamente lo dan a fabricantes comerciales, pero pedirlo cuesta un mail.

Conclusión: el camino **no depende de que el autor de Chessconnect nos haga algo**. Depende de un experimento de pocos días:

> ¿Chessconnect en Chrome (Web Serial) abre un **puerto serie virtual** y acepta un emulador DGT del otro lado?

Si sí: ChessOptic = "tablero DGT" para Chessconnect y para cualquier otro software que hable DGT (LiveChess, PicoChess, Fritz…). Si no (por ejemplo si Chessconnect filtra por VID/PID USB o si Web Serial no ve el puerto virtual): plan B es emular un tablero **BLE** (Millennium ChessLink o Chessnut), que en Linux es directo (BlueZ) y en Windows es posible pero más trabajoso (WinRT `GattServiceProvider`). Y en paralelo, con el resultado del experimento en la mano, el pedido al autor cambia de "¿nos harías una API?" a "ya funcionamos como DGT por serie virtual; ¿te sirve un transporte nativo (socket local / WebSocket) para evitar el driver de puerto virtual?", que es mucho más fácil de aceptar.

Lichess queda como camino directo (Board API oficial, sin intermediarios) para la v0.3, pero **la misma estandarización de estados sirve para los dos**.

## 1. Estandarizar lo que un tablero tiene que saber hacer

Hoy el núcleo sabe: jugada mía → enviada; jugada del rival → reproducir y verificar; fin por mate/tablas; "Terminar". Un tablero conectado a chess.com o lichess necesita bastante más, y la UI tiene que tener un estado para cada cosa. La referencia más completa y abierta es la Board API de lichess (pensada justamente para tableros físicos); Chessconnect expone lo mismo con botones en la extensión. De ahí sale el **protocolo de partida neutro** que vamos a implementar en el núcleo y que cada proveedor traduce.

### 1.1 Comandos (del usuario hacia el proveedor)

| Comando | Local (Stockfish) | Seguimiento | Online (lichess / Chessconnect) |
|---|---|---|---|
| Rendirse | resultado inmediato | marca resultado | `resign` |
| Ofrecer tablas / aceptar / rechazar | el motor decide por evaluación (o nunca acepta) | — | `draw offer/accept/decline` |
| Pedir atrás (takeback) / aceptar / rechazar | siempre acepta: deshace mi jugada y la suya | deshace la última | `takeback propose/accept/decline` |
| Abortar (antes de la 2ª jugada) | reinicia | reinicia | `abort` |
| Reclamar victoria (rival desconectado) | — | — | `claim-victory` |
| Revancha | nueva partida con colores invertidos | — | `rematch` (si la plataforma lo expone) |

### 1.2 Eventos (del proveedor hacia el usuario)

Inicio de partida con color, rival, control de tiempo y posición inicial (puede no ser la inicial: partida en curso retomada); jugada del rival; mi jugada aceptada / rechazada (con motivo); relojes (tiempo restante de ambos, de quién corre); oferta de tablas recibida; pedido de atrás recibido; rival desconectado / volvió; fin de partida con motivo (mate, abandono, tiempo, tablas acordadas, ahogado, repetición, 50 jugadas, material, aborto, por decisión del sitio); enlace perdido / recuperado; y **resincronización**: al reconectar, la plataforma manda la partida completa y ChessOptic compara con el tablero físico y pide acomodar lo que falte.

### 1.3 Esperas y errores que el tablero tiene que manejar

- Jugada mía enviada pero sin confirmación (red lenta): estado "enviando…" con reintento y, pasado un límite, aviso; nunca dos envíos de la misma jugada.
- Jugada rechazada por el sitio (ilegal según el sitio, fuera de turno, partida terminada): la pieza vuelve, el panel lo dice, se resincroniza.
- Reloj: el tiempo propio corre aunque la cámara no vea nada; aviso a los 20 s y 10 s; pérdida por tiempo llega como evento del sitio, no la decide ChessOptic.
- Promoción: el sitio espera la pieza en la jugada (UCI `e7e8q`), así que la pregunta se hace **antes** de enviar.
- Partida retomada: ChessOptic abre, el sitio dice "hay una partida en curso en esta posición", el panel muestra la posición a armar y recién entonces sigue.
- Rival se fue: contador y botón "Reclamar victoria" cuando el sitio lo permita.
- Cámara perdida en medio de la partida: la partida online sigue viva; el panel lo dice y, al volver, resincroniza.

Todo esto se **implementa primero contra Stockfish y Seguimiento**, que son proveedores que controlamos, para que los estados, la UI y los textos existan y se prueben antes de tocar una API externa. Después, un proveedor online es "traducir", no "inventar".

## 2. PRs, en orden

### PR 1 — README en inglés + espejo en español (2 días)

- `README.md` en inglés, escrito para alguien de afuera: qué es, para quién, cómo funciona (un diagrama simple: cámara → ChessOptic → tablero virtual → Chessconnect / lichess / motor), qué hace hoy, qué no es (no automatiza sitios, no es anti-trampa, no reconoce piezas por imagen), estado y hoja de ruta, instalación, y una sección **"For platform and connector developers"** que apunte a `docs/INTEGRATION.md` (PR 2).
- `README.es.md` con el mismo contenido. Selector de idioma arriba de los dos.
- Regla de espejo: un chequeo en CI que falla si un PR toca `README.md` y no `README.es.md` (o al revés). Es la forma más barata de que el español "siempre esté reflejado" sin depender de la memoria.
- Capturas reales (las tuyas) reemplazan las sintéticas en `docs/screenshots/`.
- Los demás docs siguen en español por ahora (son para quien desarrolla); `docs/INTEGRATION.md` nace en inglés porque su lector es externo.

Criterio: una persona que no conoce el proyecto entiende en un minuto qué es y qué pedimos.

### PR 2 — Spike: ChessOptic como tablero DGT por puerto serie virtual (3–5 días, con fecha de corte)

Objetivo único: responder sí/no a la pregunta de §0 con evidencia, y dejar escrito el pedido.

1. Escribir `adapters/eboard/dgt.py`: emulador del protocolo serie DGT (reset, volcado de tablero con códigos de pieza, modo actualización por casilla, número de serie y versión) alimentado por la posición del `BoardModel`. Es pequeño y está bien documentado por drivers abiertos.
2. Transporte: en Windows `com0com` (par de puertos virtuales), en macOS/Linux `socat` (pty). `chessoptic doctor` detecta si está.
3. Probar con Chessconnect en Chrome: elegir DGT, elegir el puerto, ver si conecta y si una jugada hecha en ChessOptic aparece en una partida contra la IA de lichess (que no necesita rival humano).
4. Resultado en `docs/INTEGRATION.md` (inglés): cómo funciona hoy la integración, qué pedimos (transporte nativo, o en su defecto que no filtren por fabricante) y el "kit" para el Discord del autor y para el formulario de chess.com. Si el spike falla, el documento dice exactamente dónde y el plan B (BLE Millennium / Chessnut) pasa a ser la v0.3.

Criterio: un video de una jugada yendo de ChessOptic a lichess a través de Chessconnect, o una explicación precisa de por qué no se puede y qué pedir.

### PR 3 — Protocolo de partida en el núcleo (1–2 semanas)

Implementa §1 contra Stockfish y Seguimiento:

- `adapters/base.py`: `OutputAdapter` pasa a tener los comandos de §1.1 (con `capabilities` para que la UI muestre solo lo que el proveedor soporta) y los eventos de §1.2.
- `game/session.py`: estados nuevos (`sending`, `draw_offered`, `takeback_proposed`, `resyncing`, `opponent_gone`) y transiciones en `docs/STATES.md`; deshacer en el modelo (`BoardModel.pop` ya existe, falta el flujo "reponé las piezas" como una jugada del rival); promoción antes de enviar.
- `game/modes.py`: `TimedMode` con controles clásicos y reloj en el núcleo; pérdida por tiempo local.
- Stockfish: rendirse, atrás (deshace ambas), tablas por evaluación, revancha, Elo limitado con el Elo aproximado por nivel.
- Historial: PGN siempre al terminar con cabeceras completas; `game/history.py` con el balance por proveedor / nivel / color.
- UI mínima para cada comando y evento (botones y tarjetas con el estilo actual; el rediseño es el PR 4).

Criterio: partida contra Stockfish con reloj, un atrás, una oferta de tablas y una rendición; cada uno con su estado visible y su línea en el PGN. Las simulaciones sintéticas que ya usamos cubren cada flujo.

### PR 4 — Design system y UI (2 semanas, se puede solapar con el PR 3)

Pasar de "usable" a "serio" sin cambiar de stack:

- `docs/DESIGN.md`: el design system. Tokens (color con semántica: fondo, superficie, texto, acento, estados ok/alerta/error/turno; tipografía con escala; espaciado en múltiplos de 4; radios; sombras), **componentes** con sus variantes y estados (botón primario/secundario/peligro, deshabilitado, cargando; tarjeta de estado con sus variantes; chip; lista de jugadas; reloj; toast; diálogo de confirmación; barra de salud), y reglas de layout para el panel angosto (qué va fijo, qué se achica, qué scrollea).
- `ui/theme.py` crece a los tokens completos y a **modo oscuro**; la hoja del usuario sigue funcionando.
- `ui/widgets/`: los componentes del design system como widgets reutilizables (hoy hay botones y tarjetas armados a mano en cada vista). Una **galería** (`chessoptic --gallery`) que muestra cada componente en cada estado para revisar diseño sin jugar una partida, y que sirve para capturas de regresión offscreen.
- **Control de estados**: un `AppState` único (driver + detección + partida + salud + enlace) que las vistas renderizan; ninguna vista guarda estado propio. Es lo que ya hace el núcleo con eventos, formalizado del lado de la UI, y lo que hace posible los estados nuevos del PR 3 sin que cada pantalla invente los suyos.
- UX: confirmación en acciones destructivas (rendirse, terminar), toasts para "enviada / aceptada / error", atajos de teclado, y tiempos de respuesta visibles ("enviando…" con spinner). Textos en **inglés y español** desde el núcleo de UI (`ui/i18n.py`; `config.language` ya existe) para que el panel acompañe al README.
- Se revisan las pantallas existentes con el sistema nuevo: Inicio, asistente, En vivo, Ajustes, Log.

Criterio: la galería muestra todos los componentes en los dos idiomas y en claro/oscuro; las pantallas usan solo componentes y tokens (no hay colores ni tamaños sueltos en las vistas).

### PR 5 — Proveedor online (depende del PR 2)

- Si el spike fue positivo: `adapters/online/chessconnect.py` sobre el emulador DGT, con el protocolo de partida completo (los botones de Chessconnect y los eventos del sitio llegan por el propio protocolo DGT y por lo que el usuario haga en la extensión). Relojes y resultado vienen del sitio.
- Si no: `adapters/online/lichess.py` con la Board API, que es la ruta cierta, y el plan B de BLE para Chessconnect en la v0.3.

## 3. Qué pedir, y a quién, ya mismo

Sin esperar a los PRs:

- **Discord de Chessconnect** (único canal público del autor): presentarse, el repo, y una pregunta técnica concreta: "¿La extensión abre cualquier puerto serie con Web Serial o filtra por VID/PID? ¿Un emulador DGT por puerto virtual sería aceptable para ustedes?". La respuesta ahorra o confirma el spike.
- **Formulario de chess.com** ("OAuth & Connected Board Access" en el Developer Community): cuesta un mail y abre la puerta oficial si alguna vez quieren un tablero conectado sin intermediarios.
- Nada que pedir a lichess: la Board API es pública.

## 4. Orden y tiempo

| Semana | PRs |
|---|---|
| 1 | PR 1 (README) y arranque del spike (PR 2) |
| 2 | Cierre del spike; mensaje al Discord con evidencia; arranque del PR 3 |
| 3–4 | PR 3 (protocolo de partida) y PR 4 (design system) en paralelo |
| 5 | PR 5 según el resultado del spike; corte de la v0.2 |

Lo que no entra en la v0.2: calibración automática, arrancar desde cualquier posición, instaladores, tests automáticos sobre grabaciones (siguen en `docs/ROADMAP.md` para la v0.4).

## Fuentes

- Chessconnect: sitio y lista de tableros soportados — https://chessconnect.de/ y https://chessconnect.de/supported-chess-boards/ ; extensión de Chrome — https://chromewebstore.google.com/detail/chessconnect/dmkkcjpbclkkhbdnjgcciohfbnpoaiam ; app iOS — https://apps.apple.com/us/app/chessconnect/id6747821027 ; historia del proyecto — https://www.chess.com/blog/Sawbonez/a-connection-that-transcends-the-board-the-story-of-chessconnect ; hilo original (pasó de clics simulados a la API oficial) — https://www.chess.com/forum/view/chess-equipment/chessconnect-a-chrome-extension-for-chessnut-air-and-chessnut-pro-smartboards?page=62
- Emulación de tableros existentes: OpenChess — https://github.com/joojoooo/OpenChess ; DGTCentaurMods (emula Millennium por Bluetooth) — https://github.com/DGTCentaurMods/DGTCentaurMods ; protocolo ChessLink de Millennium — https://github.com/domschl/python-mchess y https://domschl.github.io/python-mchess/doc/build/html/chess_link_protocol.html ; tablero casero que habla Millennium con Chessconnect — https://github.com/chikaskas/smart_chess_board
- Protocolo DGT: driver abierto basado en la especificación oficial — https://github.com/fnogatz/dgtchess ; códigos de comando en `dgtdrv.c` — https://sources.debian.org/src/crafty/17.6-1/dgtdrv.c/ ; dgtdrv — https://dgtdrv.sourceforge.net/dgtdrv-3.html ; protocolo Pegasus (BLE, no oficial) — https://dgtcentaurmods.github.io/pegasus-protocol
- chess.com: soporte oficial de tableros — https://support.chess.com/en/articles/8598590-can-i-play-with-a-smart-board-on-chess-com ; comunidad de desarrolladores y formulario de Connected Board — https://www.chess.com/club/chess-com-developer-community ; anuncio OAuth / Connected Board — https://www.chess.com/blog/CHESScom/chess-com-oauth-login-connected-board-application ; "¿hay API de juego?" — https://www.chess.com/clubs/forum/view/does-chess-com-have-a-game-play-api-who-should-i-talk-to ; ChessUp 2 como integración oficial — https://www.chess.com/news/view/chessup-2-now-you-can-play-chess-com-games-directly-on-a-board
- Lichess: Board API — https://lichess.org/api#tag/Board ; cliente Python berserk (tablas, atrás) — https://lichess-org.github.io/berserk/_modules/berserk/clients/board.html ; conector DGT de la comunidad — https://lichess.org/forum/general-chess-discussion/playing-online-with-a-dgt-electronic-board-using-the-board-api?page=8
