# ChessOptic — Especificación de UI (v1)

Fuente del diseño: canvas https://claude.ai/artifact/AF5QgG3z8ddDoGfvkNUbUS (privado del autor).
Copia de referencia en este repo: [`docs/design/`](design/), un `.dc.html` por pantalla. Son mockups HTML: **no** se usan como código; sirven para ver medidas, textos y colores. La implementación es PySide6 (ver `PLAN.md`).

---

## 1. Ventana

- Panel lateral angosto: **380 px** de ancho de diseño (mínimo usable ~300 px), alto completo de pantalla. Redimensionable; el contenido se apila en una columna.
- Opción "Siempre arriba".
- **Modo compacto**: 380 × 260 px aprox. (ver `Compacto.dc.html`).
- Navegación inferior con 4 pestañas: **En vivo · Cámara · Log · Ajustes**. Durante el asistente de primer uso no se muestra.

## 2. Tokens visuales

Derivados del logo (`assets/logo.png`).

| Token | Valor | Uso |
|---|---|---|
| `bg` | `#F2F4F7` | Fondo de la ventana |
| `surface` | `#FFFFFF` | Tarjetas, header, nav |
| `line` | `#DCE1E8` | Bordes finos |
| `line-strong` | `#C3CBD6` | Bordes de botones/inputs, borde "turno del rival" |
| `ink` | `#1D2330` | Texto principal, piezas negras |
| `muted` | `#5B6474` | Texto secundario |
| `turn` | `#1172B3` | **Tu turno** (fondo del bloque), acentos, botón primario |
| `brand-light` | `#1E96D7` | Marca, borde de "reproducí la jugada" |
| `ok` / `ok-bg` | `#17663A` / `#E3F4EA` | Salud OK |
| `warn` / `warn-bg` | `#8A5A0B` / `#FDF1DC` | Salud degradada |
| `err` / `err-bg` | `#A12A23` / `#FBE4E2` | Salud rota |
| `idle` / `idle-bg` | `#4A5262` / `#E8EBF0` | Sin configurar / pausado |
| casillas cámara | `#EAEEF3` claras, `#C7D1DD` oscuras | Overlay de ocupación |
| resaltado origen | `#F3D3A1` | Casilla de origen / pieza fuera de lugar |
| resaltado destino | `#8EC4EA` | Casilla de destino / última jugada |
| resaltado error | `#F0AFA9` | Casilla que no coincide |

Tipografía: **Sora** (títulos y marca, 600/700), **IBM Plex Sans** (texto, 400/600), **IBM Plex Mono** (jugadas, relojes, log). Si no están instaladas, empaquetarlas (licencia OFL) o caer a la sans/mono del sistema.

Reglas: siempre color **+** ícono/texto (accesible para daltonismo); objetivos táctiles/clic ≥ 40 px.

## 3. Estructura común de la vista "En vivo"

De arriba hacia abajo:

1. **Header**: marca (ícono + "ChessOptic") y **pill de salud** (el "semáforo"): `Driver OK` / `Revisar tablero` / `Esperando cliente` / `Enlace perdido` / `Iniciando` / `Sin calibrar`.
2. **Tira de salud**: 3 tarjetas: **Cámara** (fps) · **Tablero** (confianza o detalle) · **Enlace** (cliente o estado). Cada una con punto de color.
3. **Bloque de estado** (cambia según el estado; ver §4).
4. **Cámara**: vista rectificada 8×8 con overlay de ocupación (círculo blanco con borde = pieza blanca; círculo oscuro = pieza negra) y casillas resaltadas. Encima, etiqueta con la confianza o el resumen.
5. **Últimas jugadas**: 3–4 líneas en mono con hora.
6. **Nav inferior**.

> Regla clave: **el semáforo es solo salud del driver** (cámara, tablero, enlace). **El turno** se comunica en el bloque de estado: **azul relleno = tu turno**, **sin color con borde = turno del rival**.

## 4. Pantallas y estados

### Partida

| Pantalla | Archivo | Pill | Bloque de estado | Cámara |
|---|---|---|---|---|
| Tu turno | `Main.dc.html` | Driver OK | Fondo `turn`, "Tu turno", color propio y plataforma, relojes Vos (destacado) / Rival, última jugada del rival | Última jugada resaltada en `destino` |
| Turno del rival | `TurnoRival.dc.html` | Driver OK | Fondo blanco, borde `line-strong` 2 px, "Turno del rival · Esperando…", reloj del rival destacado, "Tu jugada: X · enviada y aceptada" | Tu última jugada en gris |
| Reproducí la jugada | `Reproducir.dc.html` | Driver OK | Borde `brand-light` 3 px, etiqueta "Rival jugó · reproducila", jugada grande en mono (ej. `4… Ae7`), frase "Mové el alfil de f8 a e7", "Esperando que la cámara vea la jugada · tu reloj corre" | Origen `#F3D3A1`, destino `#8EC4EA` |
| Posición no coincide | `NoCoincide.dc.html` | Revisar tablero (warn) | Borde `err`, ícono alerta, lista de casillas con problema, botones **Resincronizar** y **Ver frame** | Casillas en `#F0AFA9` |
| Enlace perdido | `EnlacePerdido.dc.html` | Enlace perdido (err) | Tarjeta `err-bg`: "Chessconnect se desconectó", reloj corriendo, instrucción, botones **Reconectar** y **Ver detalle**; debajo, fila compacta de turno | Normal |

Estado no dibujado: **Moviendo** (mano sobre el tablero): bloque azul con indicador de actividad; la detección espera estabilidad.

### Standby (sin partida)

| Pantalla | Archivo | Pill | Contenido |
|---|---|---|---|
| Inicio | `Inicio.dc.html` | Iniciando (idle) | Checklist de 4 pasos (Cámara, Calibración, Tablero, Salida) con estado; selector de cámara + vista previa; botón **Usar esta cámara**; ayuda con `chessoptic doctor` |
| Calibración | `Calibrar.dc.html` | Sin calibrar (idle) | Barra de 6 pasos del asistente; imagen cruda con el cuadrilátero y 4 manijas arrastrables; estado de cada esquina; elección de dónde está a1; **Atrás** / **Confirmar esquinas** |
| Verificar tablero | `VerificarTablero.dc.html` | Tablero incompleto (warn) | Contadores Blancas/Negras x/16; aviso de casillas faltantes; cámara con faltantes en `#F3D3A1`; **Recalibrar** / **Empezar desde otra posición** (v2) |
| Esperando cliente | `EsperandoCliente.dc.html` | Esperando cliente (warn) | Selector de salida; nombre con el que se anuncia (ej. `ChessOptic-4F2A`); pasos numerados para conectar en chess.com/Chessconnect y nota para celular |
| Conectado sin partida | `Conectado.dc.html` | Driver OK | "Listo para jugar", instrucción de abrir/iniciar partida, desde cuándo está conectado; cámara con posición inicial |
| Fin de partida | `FinPartida.dc.html` | Driver OK | Resultado (ej. `1–0 · ganaste por abandono`), resumen, **Exportar PGN** / **Ver log**; "Reordená el tablero" con progreso x/32 y casillas fuera de lugar marcadas |

Pasos del asistente de primer uso (**7**, implementados en `ui/views/wizard.py`): cámara → encuadre → 4 esquinas + a1 (4 posiciones posibles) → posición inicial (autoentrena) → **chequeo de detección** ("¿Coincide con tu tablero?" + hallazgos con acción) → **prueba de jugada** (e2–e4 y vuelta) → proveedor. Las pantallas Encuadre, Chequeo de detección y Prueba de jugada no tienen mockup todavía; siguen la estructura de `Calibrar` y `VerificarTablero`.

### Otras vistas

| Pantalla | Archivo | Contenido |
|---|---|---|
| Modo compacto | `Compacto.dc.html` | Marca + pill + botón expandir; bloque de turno con relojes y última jugada; miniatura de cámara |
| Log | `Log.dc.html` | Filtros (Todo / Jugadas / Eventos / Errores); lista con hora, punto de color por tipo y detalle; **Exportar PGN** / **Exportar log** |
| Ajustes | `Ajustes.dc.html` | Salida (plataforma, promoción); Detección (estabilidad en ms, guardar frames de errores); Ventana (siempre arriba, compacto en partida, sonido en errores, idioma); Diagnóstico (fps de análisis, latencia, tráfico del protocolo) |

Pestaña **Cámara** (no dibujada como pantalla aparte): dispositivo, exposición/enfoque, recalibrar, vista cruda/rectificada, confianza por casilla.

## 5. Datos que la UI consume del núcleo

La UI no calcula nada; se suscribe a eventos/estado:

- `HealthState`: cámara (ok/sin permiso/desconectada/fps bajos + fps), tablero (ok/tapado/baja confianza/no coincide + detalle), enlace (inactivo/anunciando/conectado/perdido + nombre del cliente).
- `DriverState`: estado de la máquina (standby: inicio/sin calibrar/verificando/esperando cliente/conectado; partida: mi turno/moviendo/turno rival/reproducir/no coincide/fin).
- `GameInfo`: color propio, plataforma, relojes (si los hay), jugadas en SAN con hora, resultado.
- `Occupancy`: matriz 8×8 + confianza por casilla + casillas a resaltar con su tipo (origen/destino/error/faltante).
- `PendingOpponentMove`: SAN, pieza, origen, destino, especial (enroque/al paso/promoción).
- Log de eventos.
