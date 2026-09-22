# El Tesoro de Argos

### ¿Tienes la foto del perro en la playa del verano pasado?

**Una biblioteca de fotos local y privada que entiende lo que hay en tus imágenes -- y se lo entrega a un modelo de IA local como datos sobre los que actuar, no como una carpeta que no puede ver.**

[English](README.md) · [Ejecutar en local](#ejecutar-en-local-en-windows) · [Conectar una IA](docs/MCP.md) · [Portfolio](https://luissalet.github.io/Portfolio/#projects)

![Biblioteca de El Tesoro de Argos, datos de demostración](docs/media/library.png)
*Aplicación real, datos de demostración sintéticos (degradados generados, no fotos reales).*

## Por qué

Un asistente local puede leer archivos de texto, pero no puede mirar una
carpeta con 20.000 fotos y decirte cuál tiene las notas de la pizarra de
marzo, ni si ya tienes tres copias de la misma foto del viaje ocupando
espacio. Argos indexa las carpetas de fotos del usuario en local --
embeddings CLIP vía ONNX Runtime, sin PyTorch, sin llamadas a la nube --,
extrae EXIF y geocodifica el GPS sin conexión, encuentra duplicados
exactos y aproximados, y entrega al modelo resultados compactos y
filtrados, además de una única imagen de contacto numerada para que un
modelo con visión pueda mirar diez candidatas por el precio de una. Argos
nunca modifica, mueve ni borra un archivo original; es un invariante
garantizado y probado con tests.

## Qué está implementado

| Área | Disponible ahora | Límite |
| --- | --- | --- |
| Indexado | Escaneo incremental, detección de cambios por tamaño+mtime, los archivos movidos/renombrados conservan su id, EXIF (fechas, GPS, cámara), miniaturas WebP, trabajo en segundo plano con progreso | Sin vigilancia de archivos en tiempo real (el reescaneo es manual/bajo demanda) |
| Búsqueda | Búsqueda texto->imagen con CLIP (con `FakeEmbedder` como reserva antes de descargar el modelo, ~350MB), filtros (fecha, lugar, carpeta, cámara, orientación, GPS), híbrida con descripciones cuando existen | Las consultas en inglés funcionan mejor con CLIP; las herramientas piden traducir primero |
| Duplicados | Agrupación exacta (hash de contenido) y aproximada (hash perceptual, índice de candidatos por bloques verificado contra fuerza bruta) con sugerencia de cuál conservar | Solo lectura por diseño -- Argos nunca borra; "Copiar rutas" es lo más cerca que llega a la limpieza |
| Lugares | Geocodificación inversa sin conexión (tabla de 10 ciudades incluida, o el conjunto completo de GeoNames `cities1000` bajo demanda) | Sin mapas con teselas (sin red externa para una vista); solo agrupación por país/ciudad |
| Descripciones | Modelo de visión local de Ollama, opcional, desactivado por defecto, indexado en FTS para búsqueda híbrida | Nunca se genera automáticamente; solo bajo petición por foto o en un lote |
| Álbumes | Colecciones creadas por el agente o por el usuario, no destructivas | Sin álbumes anidados |
| Integración con el asistente | `faustus-plugin.json`, 9 herramientas MCP por stdio, cada llamada del agente auditada en "Actividad del asistente" | `photos_add_folder` solo puede añadir una carpeta; quitarla es una acción humana en la interfaz |

## Conectarlo a Faustus

Argos se declara con `faustus-plugin.json`. Arranca la app y, en Faustus:
**Conectores -> Aplicaciones cercanas -> Añadir**.

También funciona con cualquier cliente MCP por stdio:

```json
{
  "mcpServers": {
    "argus": {
      "command": "C:/ruta/a/argus-hoard/.venv/Scripts/python.exe",
      "args": ["C:/ruta/a/argus-hoard/argus_hoard/mcp_server.py"],
      "env": { "ARGUS_URL": "http://127.0.0.1:8814" }
    }
  }
}
```

| Herramienta | Qué hace | ¿Solo lectura? |
| --- | --- | --- |
| `photos_search` | Texto -> fotos, con filtros y hoja de contacto | sí |
| `photos_similar` | Fotos visualmente parecidas | sí |
| `photos_show` | Hasta 4 imágenes completas para que el modelo las mire | sí |
| `photos_describe` | EXIF, lugar, ruta, descripción opcional | casi (solo escribe la descripción) |
| `photos_duplicates` | Grupos de duplicados exactos/aproximados + cuál conservar | sí |
| `photos_timeline` | Recuentos por año/mes, "un día como hoy" | sí |
| `photos_library` | Carpetas, recuentos, estado del modelo/trabajos | sí |
| `photos_add_folder` | Registra una carpeta nueva y la indexa | solo añade |
| `photos_album` | Crea o amplía un álbum | solo añade |

Referencia completa de argumentos y salidas: [docs/MCP.md](docs/MCP.md).

## Ejecutar en local en Windows

Doble clic en **`Iniciar Argus.cmd`**, o desde PowerShell:

```powershell
./scripts/start.ps1              # primera vez: crea .venv, instala, construye la interfaz
./scripts/start.ps1 -Demo        # lo mismo, con datos de demostración sintéticos
./scripts/stop.ps1
```

Pasos manuales:

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements-lock.txt
.venv\Scripts\pip install --no-deps -e .
cd frontend; npm ci; npm run build; cd ..
.venv\Scripts\python -m argus_hoard --demo
```

`--demo` usa `data-demo/` (fotos sintéticas generadas al momento) en vez
de `data/`, así que puedes probar Argos sin apuntarlo a archivos reales.

## Arquitectura

Núcleo FastAPI + SQLite (WAL), interfaz React 19 + Vite, adaptador MCP
por stdio independiente. Detalles, modelo de datos y pipeline de indexado
en [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Tests

```
pytest -q      # 37 tests, ~3.5s, sin red
```

Cubren: extracción de EXIF/GPS y orientación, generación de miniaturas,
agrupación de duplicados aproximados por hash perceptual (índice por
bloques verificado contra fuerza bruta), selección de cuál conservar en
duplicados exactos/aproximados, límites de tamaño de la hoja de contacto,
el ranking de búsqueda del `FakeEmbedder` determinista, el crecimiento y
persistencia del almacén de vectores, la geocodificación inversa sin
conexión, un cliente de descripciones de Ollama simulado, el manifiesto
`faustus-plugin.json`, el pipeline de indexado completo (los archivos
originales no se tocan, el reescaneo incremental omite lo que no ha
cambiado, los archivos movidos conservan su id), la API HTTP incluyendo
la protección contra ataques desde el navegador, y una prueba real del
protocolo MCP por stdio contra una instancia viva e indexada de la app.

## Privacidad y límites

Todo corre en `127.0.0.1`; sin telemetría, sin ninguna llamada de red que
la interfaz no anuncie explícitamente (la descarga del modelo CLIP y el
conjunto de datos GeoNames son las dos únicas, ambas opcionales y
visibles en Ajustes). La búsqueda vectorial es por fuerza bruta (coseno),
documentada como válida hasta unas 200.000 fotos en una sola máquina; una
biblioteca mayor necesitaría un índice ANN detrás de la misma interfaz
`VectorStore`.
