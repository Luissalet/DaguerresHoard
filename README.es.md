<img src="app-icon.png" width="96" alt="">

# El Tesoro de Argos

### ¿Sigues teniendo la foto del perro en la playa del verano pasado?

**Una fototeca privada que indexa tus carpetas en tu propio ordenador, entiende lo que aparece en cada imagen y le entrega a un modelo de IA local resultados compactos y una única hoja de contactos numerada que puede mirar de verdad.**

[English](README.md) · [Ejecutar en local](#ejecutar-en-local-en-windows) · [Conectar una IA](docs/MCP.md) · [Portfolio](https://luissalet.github.io/Portfolio/#projects)

![Cuadrícula de la biblioteca con datos de demostración](docs/media/library.png)
*Aplicación real con datos sintéticos: 87 imágenes generadas (degradados y formas simples, no fotos reales) con fechas EXIF, GPS de tres ciudades y duplicados colocados a propósito.*

## Por qué

Un modelo de lenguaje puede leer un archivo de texto, pero una carpeta
con 20.000 fotos es opaca para él: no sabe cuál es la de la pizarra de
marzo, dónde fue un viaje ni que hay tres copias de la misma foto
ocupando espacio. Pegar imágenes en un chat no escala, y describir fotos
a partir del nombre del archivo invita a inventar.

Argos indexa las carpetas del usuario en su propio equipo (embeddings de
imagen CLIP con ONNX Runtime, sin PyTorch y sin llamadas a la nube), lee
EXIF y GPS, geocodifica sin conexión y encuentra duplicados exactos y
aproximados. El modelo recibe resultados cortos, filtrados y numerados,
con identificadores estables, y una sola hoja de contactos con las
candidatas, de modo que un modelo con visión puede revisar diez fotos por
el precio de una imagen antes de afirmar nada. Argos nunca modifica,
mueve ni borra un archivo original; es un invariante con su test.

## Qué está implementado

| Área | Disponible ahora | Límite |
| --- | --- | --- |
| Indexado | Escaneos incrementales en segundo plano: un archivo sin cambios cuesta un `stat`; los modificados se vuelven a leer; los movidos o renombrados conservan su id, su vector, su descripción y sus álbumes. Hash y decodificación en paralelo, progreso con archivos/s y tiempo restante, y un archivo ilegible se anota sin parar el escaneo. JPEG, PNG, WebP, GIF, BMP, TIFF y HEIC/HEIF | Sin vigilancia del sistema de archivos: los reescaneos los lanza el usuario, el agente o una carpeta nueva |
| Metadatos | Fecha EXIF con zona horaria, cámara, objetivo, exposición, ISO, focal, orientación y GPS; si no hay fecha EXIF se usa la del archivo y se indica | Solo EXIF; no lee archivos XMP |
| Búsqueda | Texto a imagen con CLIP ViT-B/32 (en inglés funciona mejor; las herramientas piden al modelo que traduzca), fotos parecidas y filtros (rango de fechas, año, mes, lugar, carpeta, cámara, orientación, megapíxeles, GPS). Híbrida con las descripciones cuando existen | El modelo (unos 600 MB) solo se descarga cuando el usuario lo pide en Ajustes. Hasta entonces funciona un modo básico que solo entiende colores, y cada resultado lo avisa |
| Duplicados | Exactos (BLAKE2b) y aproximados (pHash, distancia de Hamming hasta 6, búsqueda exacta multiíndice, union-find), con la copia recomendada y el espacio que ocupan las copias sobrantes | Solo lectura por diseño: «Copiar rutas» y «Abrir carpeta»; borrar es cosa del usuario |
| Lugares y tiempo | Geocodificación inversa sin conexión (tabla integrada de 10 ciudades o GeoNames `cities1000` bajo petición), países y ciudades con recuentos, cronología por año y mes, «un día como hoy» | Sin mapas con teselas, para no hacer peticiones de red por una vista |
| Descripciones | Modelo de visión local de Ollama, opcional, por foto o en lote en segundo plano, guardado en un índice de texto completo para la búsqueda híbrida | Desactivado por defecto; nunca se genera durante el indexado |
| Álbumes | Los crea el usuario o el agente, desde el visor o con una herramienta; el agente solo puede añadir | Sin álbumes anidados |
| Interfaz | Interfaz React de escritorio: cuadrícula de miniaturas con carga continua, visor con zoom y desplazamiento sobre una vista previa grande (1600 px) del original, panel EXIF, fotos parecidas, inglés y español, tema claro y oscuro | Las secciones de la barra lateral no tienen URL propia |
| Integración con el asistente | `faustus-plugin.json`, 9 herramientas MCP por stdio y cada llamada del agente registrada en «Actividad del asistente» | El agente puede añadir una carpeta, pero no quitarla |
| Modelos compartidos | Las descripciones y la traducción de búsquedas usan el modelo que ya tenga en marcha Faustus, o un Ollama/llama.cpp/servidor local compatible con OpenAI (Ajustes -> Modelos compartidos muestra qué se resolvió y por qué, con un ajuste manual) | La búsqueda de imágenes (CLIP) siempre es local: no es un modelo de chat que cubra el backend compartido |

## Modelos compartidos

Argos nunca carga su propia copia de un modelo de lenguaje o de visión.
Dos funciones pasan por Hoard Link, un pequeño resolutor incluido que
comparte con las demás aplicaciones locales del propietario: las
**descripciones** de foto (capacidad `vision`) y la **traducción
automática** de la búsqueda (capacidad `llm`). El orden de resolución es
siempre el mismo: primero un ajuste manual guardado en Ajustes, luego un
Faustus en marcha, luego un servidor local Ollama / llama.cpp / compatible con OpenAI
que ya esté sirviendo un modelo adecuado -- así Argos nunca le pide a la
GPU que cargue una segunda copia. Si nada se resuelve, ambas funciones lo
dicen claramente y se quedan desactivadas; el resto de Argos (indexado,
búsqueda, duplicados, cronología, lugares, álbumes) funciona sin conexión
y sin ningún modelo. Más detalle en
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#shared-model-backend-hoard-link).

![Pantalla de Ajustes con el panel de Modelos compartidos](docs/media/settings.png)
*Aplicación real: en esta demostración no hay ni Faustus ni un Ollama/llama.cpp local en marcha, así que ambas capacidades informan honestamente «No disponible» junto con el motivo.*

## Conectarlo a Faustus

Argos se declara con `faustus-plugin.json`. Arranca la aplicación y, en
Faustus, abre **Conectores -> Aplicaciones cercanas -> Añadir**. Faustus
la encuentra en `127.0.0.1:8814`, lee el manifiesto del directorio de
trabajo de la aplicación y arranca él mismo el adaptador MCP.

| Herramienta | Qué hace | Solo lectura |
| --- | --- | --- |
| `photos_search` | Texto (en inglés) -> fotos, con filtros y hoja de contactos numerada | sí |
| `photos_similar` | Fotos que se parecen a una dada | sí |
| `photos_show` | Hasta 4 imágenes para verlas de cerca (200 KB como máximo cada una) | sí |
| `photos_describe` | EXIF, lugar y ruta; descripción local opcional | sí (la descripción pedida se guarda en la base de datos de Argos) |
| `photos_duplicates` | Grupos de duplicados exactos o aproximados con la copia recomendada | sí |
| `photos_timeline` | Recuentos por año y mes, «un día como hoy» | sí |
| `photos_library` | Carpetas, recuentos, modelo activo y trabajos en curso | sí |
| `photos_add_folder` | Registra una carpeta y la indexa | solo añade |
| `photos_album` | Crea o amplía un álbum | solo añade |

Funciona con cualquier cliente MCP por stdio:

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

Argumentos, formato de las respuestas, códigos de error y límites:
[docs/MCP.md](docs/MCP.md). La guía que le dice al modelo cuándo y cómo
usar las herramientas: [skills/find-photos/SKILL.md](skills/find-photos/SKILL.md).

![Búsqueda «sunset over the sea» con el modelo CLIP](docs/media/search.png)
*Aplicación real: «sunset over the sea» con el modelo CLIP de verdad sobre las imágenes sintéticas.*

![Visor con panel EXIF y fotos parecidas](docs/media/lightbox.png)
*El visor: vista previa del original, EXIF, lugar, descripción, álbumes y fotos parecidas.*

## Ejecutar en local en Windows

Requisitos: Python 3.11 o posterior (mejor 3.13 en `C:\Python313`) y
Node.js 22 para compilar la interfaz la primera vez.

Doble clic en **`Iniciar Argus.cmd`** (y **`Detener Argus.cmd`** para
pararlo), o desde PowerShell:

```powershell
.\scripts\start.ps1              # primera vez: crea .venv, instala el lock y compila la interfaz
.\scripts\start.ps1 -Demo        # igual, con la biblioteca sintética en data-demo\
.\scripts\start.ps1 -Port 8820 -NoBrowser
.\scripts\stop.ps1
```

`start.ps1` reinstala las dependencias cada vez que cambia
`requirements-lock.txt`, arranca la aplicación en segundo plano con el
repositorio como directorio de trabajo, espera a que responda
`/api/health` y abre el navegador. Los registros quedan en `data\logs\`.
`stop.ps1` detiene el proceso que escucha en el puerto tras comprobar que
es Argos.

Pasos manuales:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-lock.txt
cd frontend; npm ci; npm run build; cd ..
.venv\Scripts\python -m argus_hoard            # http://127.0.0.1:8814
.venv\Scripts\python -m argus_hoard --demo     # biblioteca sintética en data-demo\
```

Opciones: `--port`, `--data-dir` (o `ARGUS_DATA_DIR`), `--demo` y
`--no-browser`. Todo lo que escribe Argos vive en la carpeta de datos
(`data\` por defecto): base de datos, miniaturas, vectores, caché del
modelo y registros.

## Arquitectura

FastAPI y SQLite (WAL) alrededor de un motor en Python puro, una interfaz
React 19 + Vite y un adaptador MCP independiente que habla con la
aplicación por HTTP. Módulos, modelo de datos, pipeline de indexado,
hilos e índice de duplicados: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

![Duplicados aproximados con la copia recomendada](docs/media/duplicates.png)
*Duplicados aproximados en la biblioteca de demostración: cada copia reducida se agrupa con su original, la recomendada primero.*

![Cronología por año y mes](docs/media/timeline.png)
*Cronología: meses con miniaturas de muestra; cada mes abre sus fotos.*

## Tests

```powershell
.venv\Scripts\python -m pytest -q          # 106 tests, unos 15-20 s, sin red
.venv\Scripts\python -m pytest -q -m model # 1 test opcional con el modelo CLIP real (lo descarga si falta)
cd frontend; npm run build                 # TypeScript estricto
```

La batería por defecto comprueba: que los originales no cambian tras
indexar, buscar duplicados y crear álbumes; los reescaneos incrementales;
que un archivo movido conserva su id; que un archivo corrupto no para el
escaneo; que los escaneos simultáneos se ejecutan de uno en uno; que la
carpeta de datos nunca se indexa como fotos; que se vuelve a calcular el
embedding al cambiar de modelo; el EXIF tal como lo escriben las cámaras
(sub-IFD, tuplas, fechas a cero) y los signos del GPS; la orientación de
las miniaturas; todos los formatos admitidos, HEIC incluido; el índice de
duplicados aproximados frente a fuerza bruta con 8.000 hashes; union-find
y la regla de la copia recomendada; los límites de tamaño de la hoja de
contactos y de `photos_show`; el ranking del modo básico y que es
determinista entre procesos; el almacén de vectores; la geocodificación
con una tabla de prueba; el cliente de Ollama contra un servidor simulado,
búsqueda híbrida con descripciones incluida; la validación de filtros; la
protección HTTP, los intentos de salir de la carpeta de la interfaz y el
formato de los errores; el manifiesto; y el adaptador MCP lanzado por
stdio contra la aplicación en marcha (lista de herramientas, anotaciones,
palabras clave, imagen de la hoja de contactos, `photos_show`, álbumes,
errores y el mensaje cuando la aplicación está parada). Además: el
resolutor del backend compartido (los ajustes antiguos de Ollama solo se
convierten en el ajuste manual de la capacidad `vision` cuando el usuario
los ha guardado de verdad; los ajustes manuales se guardan sin devolver
nunca el token de Faustus); las descripciones a través de
`Link.chat(capability="vision")` contra un servidor simulado, resuelto o
no; la pausa de buen ciudadano `wait_idle("vision")` en un lote de
descripciones; el detector de idioma no inglés; y la separación entre
`/api/search` y `/api/agent/photos_search` (solo la ruta de la interfaz
traduce). El test del
modelo indexa las escenas de demostración con CLIP real y comprueba que
cuatro descripciones en inglés encuentran la escena correcta. El flujo de
CI está preparado para pasar la batería en Ubuntu y Windows con Python
3.11 y 3.13, compilar la interfaz y probar `start.ps1`/`stop.ps1` en
Windows.

## Privacidad y límites

- Solo escucha en `127.0.0.1`; rechaza las peticiones con otra cabecera
  `Host` y las escrituras desde otros sitios. Sin telemetría.
- Las únicas peticiones de red son las que el usuario lanza en Ajustes:
  el modelo CLIP desde Hugging Face y los datos de GeoNames. Solo se
  contacta con un Ollama local para las descripciones que pida el usuario
  o el agente.
- Los originales solo se leen. Quitar una carpeta en Ajustes borra los
  datos propios de Argos sobre ella (filas del índice, miniaturas,
  entradas de álbumes), nunca los archivos.
- La búsqueda vectorial es por fuerza bruta (coseno): válida hasta unas
  200.000 fotos en un solo equipo.
- Los nombres de lugares proceden de [GeoNames](https://www.geonames.org/)
  (CC BY 4.0) cuando se descarga el conjunto completo.
