# Cómo contribuir

Gracias por querer sumar. Ideas, issues y PRs son bienvenidos.

## Flujo

Nadie, ni siquiera quien mantiene el proyecto, pushea directo a `main`: todo entra por pull request.

1. Hacé un **fork** del repositorio y cloná tu fork.
2. Creá una rama desde `main`: `git switch -c fix/descripcion-corta`.
3. Hacé tus cambios y verificá localmente:

   ```bash
   uv sync --all-groups
   uv run ruff check . && uv run ruff format --check .
   uv run mypy
   uv run chessoptic
   ```

4. Pusheá a tu fork y abrí un PR contra `main` de este repositorio.
5. El CI corre en Windows, macOS y Linux. Si es tu primer PR, un mantenedor tiene que aprobar la ejecución del CI antes de que corra: es normal, no hace falta que hagas nada.
6. Para mergear, el CI tiene que pasar en los tres sistemas y todas las conversaciones del PR tienen que estar resueltas.

## Convenciones

- Docs y textos de interfaz en **español**; código, identificadores, comentarios y commits en **inglés**.
- Commits con [Conventional Commits](https://www.conventionalcommits.org/): `feat(ui): ...`, `fix(vision): ...`.
- `ruff` y `mypy --strict` en verde. Type hints en todo.
- La lógica de visión y del modelo del tablero tiene que poder probarse sin cámara.
- Antes de proponer algo grande, leé [`docs/PLAN.md`](docs/PLAN.md) y abrí un issue para charlarlo: hay decisiones cerradas (por ejemplo, no automatizar el DOM de sitios web).

## Seguridad

Si encontrás una vulnerabilidad, **no abras un issue público**: seguí [`SECURITY.md`](SECURITY.md).

## Licencia

Al contribuir aceptás que tu aporte se publique bajo la licencia [Apache-2.0](LICENSE) del proyecto.
