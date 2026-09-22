# AGENTS.md

Reglas para cualquier agente de código que trabaje en este repositorio.

## No negociable

- **Nunca** modifiques, muevas ni borres un archivo bajo una carpeta
  registrada como root (fuera de `data/`). Es un invariante probado en
  `tests/test_library.py`; si lo rompes, el usuario pierde fotos reales.
- Todo lo que se escribe en disco por la app vive bajo `data/` (o
  `data-demo/` con `--demo`). Nunca rutas fuera del repo salvo que el
  usuario lo pida explícitamente (`--data-dir`).
- La API solo escucha en `127.0.0.1`. No añadas CORS. No añadas
  telemetría ni llamadas de red externa que el usuario no haya pedido
  explícitamente (la única excepción hoy es la descarga opcional de
  GeoNames y de un modelo CLIP, y ambas se anuncian en la UI). El sondeo
  de `hoard_link/` a Faustus y a servidores en loopback (Ollama,
  llama.cpp, u otro compatible con OpenAI) para las capacidades `vision` y `llm` es la
  excepción esperada: nunca sale de `127.0.0.1` y es justo lo que pide
  el backend de modelos compartido.
- **Nunca edites `daguerre_hoard/hoard_link/`** (es una copia vendorizada,
  ver `VENDORED.txt`). Compón sobre ella desde `backend.py`
  (`Library.backend`); para actualizarla, sustituye la carpeta entera.
- No uses `window.confirm` ni `alert` en el frontend: bloquean la
  pestaña si algo la controla por automatización. Usa una confirmación
  en dos pasos en línea (ver `SettingsPage.tsx`).

## Antes de tocar código

- Lee `docs/ARCHITECTURE.md` para entender dónde vive cada cosa.
- El núcleo (`daguerre_hoard/*.py` salvo `api.py` y `mcp_server.py`) no
  importa FastAPI. Si necesitas FastAPI en un módulo "core", es que la
  lógica pertenece a `api.py`, no al revés.
- `mcp_server.py` es un script standalone: solo stdlib, `httpx` y
  `mcp`. No lo hagas importar nada de `daguerre_hoard`.

## Al añadir una herramienta de agente

1. Añade el método en `Library` (sin FastAPI).
2. Expón `/api/agent/<tool>` en `api.py` con `run(..., tool="<tool>")`
   para que quede registrado en `agent_calls`. La interfaz usa rutas
   propias sin `tool=`: los clics del usuario no son actividad del
   asistente.
3. Añade el tool equivalente en `mcp_server.py`, con docstring (qué,
   cuándo, qué devuelve, límites) + `Keywords:` en inglés y español,
   `ToolAnnotations` honestos y salida con `_text(...)` (JSON compacto).
   Los errores de validación deben decir qué valores se aceptan.
4. Añade un test en `tests/test_api.py` como mínimo; si cambia el
   protocolo MCP, actualiza `tests/test_mcp_protocol.py`.
5. Actualiza `docs/MCP.md` y `skills/find-photos/SKILL.md` si cambia el
   comportamiento que un modelo necesita conocer.

## Tests

`pytest -q` debe tardar menos de 90s y no tocar la red. Si necesitas
probar el modelo CLIP real, márcalo `-m model` y no lo metas en la
suite por defecto. Antes de dar algo por terminado: `pytest -q`,
`npm run build` en `frontend/`, y arranca la app con `--demo` una vez
para comprobar que no hay una regresión visual obvia.

## Windows

- `scripts/*.ps1` solo en ASCII (PowerShell 5.1 lee sin BOM como ANSI).
- Rutas con `pathlib`, `encoding="utf-8"` en todo texto, nada de `/tmp`.
- No sustituyas un archivo mapeado en memoria (`vectors.f32`): en Windows
  falla. Crece en el sitio, como hace `VectorStore._grow`.

## Commits

Igual que el resto de plugins hermanos: identidad `Luissalet`, mensajes
en inglés, sin mencionar otros productos ni datos personales.
