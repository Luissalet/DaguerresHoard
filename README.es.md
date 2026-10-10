<img src="app-icon.png" width="96" alt="">

# Daguerre's Hoard

La importación editable de paquetes `.comp` dispone de un subconjunto raster
verificado: capas separadas en PhotoCraft `.pcraft`, nombres, visibilidad,
opacidad y desplazamientos enteros, con informe por capa, hashes de los
originales, reapertura nativa y vista PNG. El contenido no compatible detiene
la importación antes de escribir. Grupos, máscaras, ajustes, texto, efectos,
rotación y escalado siguen sin equivalencia verificada; no se afirma paridad
con Compositor. Véase [la guía de importación en español](docs/COMPOSITOR.es.md).

### ¿Sigues teniendo la foto del perro en la playa del verano pasado?

*Lleva el nombre de Louis Daguerre, cuyo daguerrotipo (1839) fue la primera fotografía práctica.*

**Una fototeca privada que indexa tus carpetas en tu propio ordenador, entiende lo que aparece en cada imagen y le entrega a un modelo de IA local resultados de texto compactos y ordenados con honestidad, y una hoja de contactos numerada solo cuando el modelo puede ver imágenes.**

[English](README.md) · [Inicio rápido](#inicio-rápido) · [Conectarlo a Faustus](#conectarlo-a-faustus) · [Referencia MCP](docs/MCP.md) · [Portfolio](https://luissalet.github.io/Portfolio/#projects)

![Cuadrícula de la biblioteca con datos de demostración](docs/media/library.png)
*Aplicación real con datos sintéticos: 87 imágenes generadas (degradados y formas simples, no fotos reales) con fechas EXIF, GPS de tres ciudades y duplicados colocados a propósito.*

## Por qué

Un modelo de lenguaje puede leer un archivo de texto, pero una carpeta
con 20.000 fotos es opaca para él: no sabe cuál es la de la pizarra de
marzo, dónde fue un viaje ni que hay tres copias de la misma foto
ocupando espacio. Pegar imágenes en un chat no escala, y describir fotos
a partir del nombre del archivo invita a inventar.

Daguerre indexa tus carpetas en tu propio equipo (embeddings de
imagen CLIP con ONNX Runtime, sin PyTorch y sin llamadas a la nube), lee
EXIF y GPS, geocodifica sin conexión y encuentra duplicados exactos y
aproximados. El modelo recibe resultados cortos, filtrados y numerados,
con identificadores estables y un grado de coincidencia (fuerte, media o
débil) en cada uno. Un modelo con visión puede pedir una sola hoja de
contactos con las candidatas y revisar diez fotos por el precio de una
imagen antes de afirmar nada; un modelo solo de texto nunca recibe una
imagen que no haya pedido. Daguerre nunca modifica,
mueve ni borra un archivo original; es un invariante con su test. El único
archivo que puede escribir junto a una foto es un `.xmp` opcional con tus
valoraciones y tu receta de retoque, desactivado por defecto (ver
[Valoraciones, recetas de retoque y archivos .xmp](#valoraciones-recetas-de-retoque-y-archivos-xmp)).

## Casos de uso

Ocho escenarios, recorridos en el navegador y, los del agente, por MCP
real con un script que hace de modelo local pequeño
([docs/USE_CASES.md](docs/USE_CASES.md); lo encontrado y lo corregido
está en [docs/USABILITY_REPORT.md](docs/USABILITY_REPORT.md)):

- **Primer arranque**: añadir `Imágenes` (sirve una ruta pegada con las
  comillas del Explorador), descargar el modelo de imagen en Ajustes
  mientras la barra cuenta los megas y buscar «sunset over the sea».
- **Una foto por contenido y fecha**: *«¿tienes la foto del perro en la
  playa del verano pasado?»*. El modelo busca «dog on the beach» con un
  rango de fechas, recibe solo texto y dice cuánta seguridad tiene.
- **Liberar espacio**: las copias exactas conservan el original del
  carrete, y «Copiar rutas de las copias extra» deja fuera la que se
  conserva; los duplicados aproximados se muestran como «hasta», para
  revisarlos grupo a grupo.
- **Álbumes desde el agente**: *«haz un álbum "Lisboa 2024" con todo el
  viaje»*: solo con filtros (`place="Lisbon"`, julio de 2024) y paginando
  con `next_offset` se cubre el viaje entero.
- **Con otras herramientas**: un retrato vertical para el CV que el
  asistente copia luego con sus propias herramientas de archivos, y las
  fotos de la claqueta y el croma del rodaje de un cortometraje reunidas en un
  álbum.
- **Recuerdos y lugares**: «un día como hoy» con lugares, y Lugares
  agrupado por país y ciudad.

## Qué está implementado

| Área | Disponible ahora | Límite |
| --- | --- | --- |
| Indexado | Escaneos incrementales en segundo plano: un archivo sin cambios cuesta un `stat`; los modificados se vuelven a leer; los movidos o renombrados conservan su id, su vector, su descripción y sus álbumes. Hash y decodificación en paralelo, progreso con archivos/s y tiempo restante, y un archivo ilegible se anota sin parar el escaneo. JPEG, PNG, WebP, GIF, BMP, TIFF y HEIC/HEIF | Sin vigilancia del sistema de archivos: los reescaneos los lanza el usuario, el agente o una carpeta nueva |
| Metadatos | Fecha EXIF con zona horaria, cámara, objetivo, exposición, ISO, focal, orientación y GPS; si no hay fecha EXIF se usa la del archivo y se indica | Solo EXIF; no lee archivos XMP |
| Vídeos | Los vídeos de las carpetas (MP4, MOV, MKV, AVI, WebM, M4V, WMV, MPG, 3GP) se indexan como **fotogramas clave**: uno en cada cambio de escena (puntuación `scene` de ffmpeg) más uno cada 30 s como respaldo para imágenes estáticas, hasta 48 por vídeo (ambos ajustables con `POST /api/video-settings`). Cada fotograma pasa por el mismo proceso que las fotos (miniatura, hash perceptual, embedding CLIP si el modelo está instalado, texto completo, álbumes) y queda enlazado a su vídeo con su marca de tiempo. Página Vídeos con tira de fotogramas y reproductor que salta al fotograma pulsado; los resultados de búsqueda muestran `video · 01:23`; herramientas `videos_list` y `videos_describe`. Incremental: un vídeo solo se vuelve a procesar si cambió su contenido (tamaño/fecha y luego un hash de principio y final), un archivo movido conserva sus fotogramas y uno borrado se oculta | Necesita `ffmpeg` en el PATH (o `DAGUERRE_FFMPEG`); sin él los vídeos se listan sin fotogramas y el siguiente escaneo lo reintenta. Los fotogramas son imágenes fijas: sin audio, sin transcripción ni descripción del clip, sin seguimiento de objetos. El reproductor depende de que el navegador soporte el códec (los fotogramas funcionan igual). Los fotogramas no aparecen en la cuadrícula normal, duplicados, cronología ni lugares |
| Búsqueda | Texto a imagen con CLIP ViT-B/32 (en inglés funciona mejor; las herramientas piden al modelo que traduzca), fotos parecidas y filtros (rango de fechas, año, mes, lugar, carpeta, cámara, orientación, megapíxeles, GPS). Híbrida con las descripciones cuando existen | El modelo (unos 600 MB) solo se descarga cuando el usuario lo pide en Ajustes. Hasta entonces funciona un modo básico que solo entiende colores, y cada resultado lo avisa |
| Duplicados | Exactos (BLAKE2b) y aproximados (pHash, distancia de Hamming hasta 6, búsqueda exacta multiíndice, union-find), con la copia recomendada (el original, no la copia de seguridad ni la del chat) y el espacio que ocupan las copias sobrantes | Solo lectura por diseño: «Copiar rutas de las copias extra» y «Abrir carpeta»; borrar es cosa tuya. Un grupo aproximado puede juntar fotos distintas que se parecen, así que su espacio se muestra como «hasta» |
| Lugares y tiempo | Geocodificación inversa sin conexión (tabla integrada de 10 ciudades o GeoNames `cities1000` bajo petición, donde cada barrio lleva la ciudad a la que pertenece: «Alfama, Lisbon, Portugal»), países y ciudades con recuentos, cronología por año y mes, «un día como hoy» | Sin mapas con teselas, para no hacer peticiones de red por una vista. La tabla integrada no ubica nada a más de 50 km de sus 10 ciudades |
| Descripciones | Opcionales, con un modelo de visión local que encuentra el backend compartido (ver más abajo), por foto o en lote en segundo plano, guardado en un índice de texto completo para la búsqueda híbrida | Desactivado por defecto; nunca se genera durante el indexado |
| Álbumes | Los creas tú o el agente, desde el visor o con una herramienta; el agente solo puede añadir | Sin álbumes anidados |
| Valoraciones, etiquetas, palabras clave y recetas de retoque | Por foto: de 0 a 5 estrellas (o descartada), una etiqueta, palabras clave y una pequeña receta de revelado no destructiva, guardadas en Daguerre y, si lo activas, también como un `.xmp` estándar junto a la foto; los `.xmp` que ya existan (y el XMP incrustado en JPEG/TIFF/PNG/WebP) se leen en cada escaneo. Detalles más abajo | Daguerre solo renderiza la exposición de una receta (con LightCraft); el resto son datos para los reveladores RAW. La escritura de `.xmp` está desactivada por defecto |
| Interfaz | Interfaz React de escritorio: cuadrícula de miniaturas con carga continua, visor con zoom y desplazamiento sobre una vista previa grande (1600 px) del original, panel EXIF, fotos parecidas, inglés y español, tema claro y oscuro | Las secciones de la barra lateral no tienen URL propia |
| Integración con el asistente | `faustus-plugin.json`, 22 herramientas MCP por stdio y cada llamada del agente registrada en «Actividad del asistente» | El agente puede añadir una carpeta, pero no quitarla |
| Modelos compartidos | Las descripciones y la traducción de búsquedas usan el modelo que ya tenga en marcha Faustus, o un Ollama/llama.cpp/servidor local compatible con OpenAI (Ajustes -> Modelos compartidos muestra qué se resolvió y por qué, con un ajuste manual) | La búsqueda de imágenes (CLIP) siempre es local: no es un modelo de chat que cubra el backend compartido |

## Modelos compartidos

Daguerre nunca carga su propia copia de un modelo de lenguaje o de visión.
Dos funciones pasan por [HoardLink](https://github.com/Luissalet/HoardLink),
un pequeño resolutor que llevan incluido las aplicaciones que comparten
modelos en el mismo equipo: las
**descripciones** de foto (capacidad `vision`) y la **traducción
automática** de la búsqueda (capacidad `llm`). El orden de resolución es
siempre el mismo: primero un ajuste manual guardado en Ajustes, luego un
Faustus en marcha, luego un servidor local Ollama / llama.cpp / compatible
con OpenAI que ya esté sirviendo un modelo adecuado -- así Daguerre nunca le
pide a la GPU que cargue una segunda copia. Si nada se resuelve, ambas funciones lo
dicen claramente y se quedan desactivadas (sus botones aparecen
deshabilitados con el motivo); el resto de Daguerre (indexado,
búsqueda, duplicados, cronología, lugares, álbumes) funciona sin conexión
y sin ningún modelo. Más detalle en
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#shared-model-backend-hoard-link).

![Pantalla de Ajustes con el panel de Modelos compartidos](docs/media/settings.png)
*Aplicación real: en esta demostración no hay ni Faustus ni un Ollama/llama.cpp local en marcha, así que ambas capacidades informan honestamente «No disponible» junto con el motivo.*

## Conectarlo a Faustus

Daguerre es un plugin de [Faustus](https://github.com/Luissalet/Faustus), un
espacio de trabajo de IA local, y se declara con `faustus-plugin.json`.
Arranca la aplicación y, en Faustus, abre **Conectores -> Aplicaciones cercanas -> Añadir**. Faustus
la encuentra en `127.0.0.1:8814`, lee el manifiesto del directorio de
trabajo de la aplicación y arranca él mismo el adaptador MCP.

| Herramienta | Qué hace | Solo lectura |
| --- | --- | --- |
| `photos_search` | Texto (en inglés) -> fotos con grado de coincidencia, filtros y paginación; hoja de contactos numerada solo si se pide | sí |
| `photos_similar` | Fotos que se parecen a una dada | sí |
| `photos_show` | Hasta 4 imágenes para verlas de cerca (200 KB como máximo cada una) | sí |
| `photos_describe` | EXIF, lugar y ruta; descripción local opcional | sí (la descripción pedida se guarda en la base de datos de Daguerre) |
| `photos_duplicates` | Grupos de duplicados exactos o aproximados con la copia recomendada | sí |
| `photos_timeline` | Recuentos por año y mes, «un día como hoy» | sí |
| `photos_library` | Carpetas, recuentos, modelo activo y trabajos en curso | sí |
| `videos_list` | Vídeos indexados con duración y número de fotogramas clave | sí |
| `videos_describe` | Un vídeo y sus fotogramas clave con marca de tiempo (`01:23`); los ids de fotograma sirven en `photos_show`, `photos_similar`, `photos_album` | sí |
| `photos_add_folder` | Registra una carpeta y la indexa | solo añade |
| `photos_album` | Crea o amplía un álbum | solo añade |
| `photos_export` | Galería HTML ordenada, hoja de contacto JPEG y manifiesto de fuentes | escribe archivos derivados |
| `photos_edits` | Valoración, etiqueta, palabras clave, receta de revelado y estado del `.xmp` de una foto (lee antes un `.xmp` que haya cambiado) | sí |
| `photos_set_edits` | Fija valoración, etiqueta, palabras clave o ajustes de la receta; mantiene el `.xmp` al día si el dueño activó los sidecars | escribe datos de Daguerre, y el `.xmp` solo si está activado |
| `photos_sidecar` | `read` o `write` del `.xmp` de la foto ahora | escribe datos de Daguerre, y el `.xmp` solo si está activado |

`photos_export(ids=[...], title="Selección de verano")` convierte hasta 20 fotos
elegidas en una galería HTML portátil con sus vistas previas incluidas, una hoja
de contacto numerada y `manifest.json`. Conserva el orden y las repeticiones
deliberadas; cada vista previa/celda se corresponde con un ID estable, ruta original
y huella de contenido. Los archivos quedan en `data/exports/`; los originales
se leen sin modificarlos. El mismo título, selección ordenada, contenido de las
fotos y metadatos exportados reutilizan la exportación.
Las fotos ausentes o ilegibles aparecen en `omitted`, con `complete=false`.
Devuelve texto y rutas, por lo que un modelo sin visión también puede prepararla.
Es una galería de vistas previas: no empaqueta originales a resolución completa
ni un lector flipbook.

Funciona con cualquier cliente MCP por stdio:

```json
{
  "mcpServers": {
    "daguerre": {
      "command": "C:/ruta/a/daguerres-hoard/.venv/Scripts/python.exe",
      "args": ["C:/ruta/a/daguerres-hoard/daguerre_hoard/mcp_server.py"],
      "env": { "DAGUERRE_URL": "http://127.0.0.1:8814" }
    }
  }
}
```

En Linux o macOS el intérprete es `daguerres-hoard/.venv/bin/python`.

Argumentos, formato de las respuestas, códigos de error y límites:
[docs/MCP.md](docs/MCP.md). La guía que le dice al modelo cuándo y cómo
usar las herramientas: [skills/find-photos/SKILL.md](skills/find-photos/SKILL.md).

![Búsqueda «sunset over the sea» con el modelo CLIP](docs/media/search.png)
*Aplicación real: «sunset over the sea» con el modelo CLIP de verdad sobre las imágenes sintéticas.*

![Visor con panel EXIF y fotos parecidas](docs/media/lightbox.png)
*El visor: vista previa del original, EXIF, lugar, descripción, álbumes y fotos parecidas.*

## Valoraciones, recetas de retoque y archivos .xmp

Cada foto puede llevar una valoración (-1 descartada, de 0 a 5 estrellas), una
etiqueta, palabras clave y una **receta de retoque**: una descripción pequeña y
no destructiva de un revelado. Todo vive en la base de datos de Daguerre y la
foto nunca se modifica. Se fija en el visor (**Valoración y retoque**), con
`PUT /api/photos/{id}/edits` o con la herramienta `photos_set_edits`;
`photos_describe` y `photos_edits` lo muestran.

| Campo de la receta | Rango | Propiedad XMP estándar |
| --- | --- | --- |
| `exposure` | de -5 a +5 EV | `crs:Exposure2012` |
| `contrast`, `highlights`, `shadows`, `whites`, `blacks`, `clarity` | de -100 a 100 | `crs:Contrast2012`, `Highlights2012`, `Shadows2012`, `Whites2012`, `Blacks2012`, `Clarity2012` |
| `vibrance`, `saturation`, `dehaze` | de -100 a 100 | `crs:Vibrance`, `Saturation`, `Dehaze` |
| `temperature` (K), `tint` | 2000-50000, de -150 a 150 | `crs:Temperature`, `crs:Tint` (+ `crs:WhiteBalance="Custom"`) |
| `crop` `{left, top, right, bottom, angle}` | bordes 0-1, ángulo de -45 a 45 | `crs:CropLeft/Top/Right/Bottom`, `CropAngle`, `HasCrop` |
| `orientation` | EXIF 1-8 | `tiff:Orientation` |
| valoración, etiqueta, palabras clave | -1/0-5, texto, lista | `xmp:Rating`, `xmp:Label`, `dc:subject` |
| la receta completa | | `daguerre:Recipe` (JSON) y `daguerre:Version`, en el espacio de nombres propio de Daguerre, para no perder nada en un viaje de ida y vuelta |

**Escribir es opcional.** Ajustes -> *Escribir archivos .xmp junto a las fotos
editadas* (desactivado por defecto; un asistente no puede activarlo). Con eso
activado, cada edición escribe también `IMG_0001.xmp` junto a `IMG_0001.jpg` (la
convención de los reveladores RAW; si ya tienes un `IMG_0001.jpg.xmp`, se usa
ese). La foto no se toca nunca. Un sidecar existente se **fusiona, no se
sustituye**: se analiza, solo se actualizan en su sitio las propiedades de
arriba, y todo lo demás (otros espacios de nombres, campos, listas y ajustes de
revelado sin equivalente) queda como estaba. La primera vez que Daguerre
modifica un sidecar que no escribió él, copia el original a `data/xmp-backups/`.
Un sidecar que no sea XMP válido se deja en paz y la edición se conserva en
Daguerre junto con el error. Las escrituras son atómicas (archivo temporal y
renombrado).

**Leer está siempre activado.** Cada escaneo lee un sidecar nuevo o cambiado (un
`stat` por foto si no ha cambiado nada) y, la primera vez que ve un archivo sin
sidecar, el XMP incrustado en el JPEG/TIFF/PNG/WebP. Mandan la valoración, la
etiqueta y las palabras clave del sidecar; sus ajustes de revelado se superponen
a la receta guardada como punto de partida (por ejemplo `crs:Exposure2012="+0.85"`
pasa a `exposure: 0.85`). Lo que Daguerre no sabe representar (curvas de tono,
HSL, nitidez, máscaras...) y cualquier valor fuera de sus rangos se muestra como
*importado, no aplicado* y permanece en el archivo. Los ajustes incrustados en un
JPEG ya terminado están horneados en sus píxeles, así que solo se listan y nunca
se convierten en receta. Si el sidecar cambió en el disco, una edición o
`photos_edits` lo lee antes, de modo que una edición a mano no se pisa. Si borras
el sidecar, las ediciones se conservan.

El XML de los archivos no es de fiar: los documentos con DOCTYPE o declaraciones
de entidades (expansión de entidades, entidades externas) se rechazan antes de
expandir nada, y el tamaño, la profundidad y el número de nodos están acotados.
No interviene la red.

Límites: Daguerre solo renderiza la exposición de la receta
(`craft_develop_photo`); el resto de ajustes son datos para los reveladores RAW.
Los formatos RAW (CR3, NEF, ARW, DNG...) aún no los indexa Daguerre, así que los
sidecars se usan con los formatos que sí indexa. `IMG_1.jpg` e `IMG_1.png` en una
carpeta comparten `IMG_1.xmp`, como en los reveladores RAW. Los comentarios de un
sidecar fusionado se pierden y se normalizan sus espacios en blanco. El XMP
extendido (más de 64 KB en un JPEG) no se lee. La temperatura va en Kelvin, como
en los RAW; la escala relativa de los JPEG se muestra como no aplicada.

## Inicio rápido

Requisitos: Python 3.11 o posterior y Node.js 22 (solo para compilar la
interfaz la primera vez). El modelo de imagen no viene incluido: se
descarga desde Ajustes -> Modelo de imagen (unos 600 MB) cuando lo pidas;
hasta entonces la búsqueda solo entiende colores y lo avisa.

### Windows (PowerShell)

```powershell
git clone https://github.com/Luissalet/DaguerresHoard.git
cd DaguerresHoard
.\scripts\start.ps1 -Demo      # primera vez: crea .venv, instala el lock, compila la interfaz y abre el navegador
```

O doble clic en **`Iniciar Daguerre.cmd`** (y **`Detener Daguerre.cmd`** para
pararlo). Más opciones del lanzador:

```powershell
.\scripts\start.ps1              # tu propia biblioteca en data\
.\scripts\start.ps1 -Port 8820 -NoBrowser
.\scripts\stop.ps1
```

`start.ps1` prefiere Python 3.13 si está instalado en `C:\Python313`,
reinstala las dependencias cada vez que cambia `requirements-lock.txt`,
arranca la aplicación en segundo plano con el repositorio como directorio
de trabajo, espera a que responda `/api/health` y abre el navegador. Los
registros quedan en `data\logs\`. `stop.ps1` detiene el proceso que
escucha en el puerto tras comprobar que es Daguerre.

Los mismos pasos a mano:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-lock.txt
cd frontend; npm ci; npm run build; cd ..
.venv\Scripts\python -m daguerre_hoard --demo     # biblioteca sintética en data-demo\
.venv\Scripts\python -m daguerre_hoard            # tu propia biblioteca, http://127.0.0.1:8814
```

### Linux / macOS

```bash
git clone https://github.com/Luissalet/DaguerresHoard.git
cd DaguerresHoard
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
(cd frontend && npm ci && npm run build)
.venv/bin/python -m daguerre_hoard --demo --no-browser   # biblioteca sintética en data-demo/
curl http://127.0.0.1:8814/api/health                 # {"service":"daguerres-hoard",...}
```

Después abre <http://127.0.0.1:8814>. Opciones: `--port`, `--data-dir` (o
`DAGUERRE_DATA_DIR`), `--demo` y `--no-browser`. Todo lo que escribe Daguerre
vive en la carpeta de datos (`data/` por defecto, `data-demo/` con
`--demo`): base de datos, miniaturas, vectores, caché del modelo y
registros.

## Arquitectura

FastAPI y SQLite (WAL) alrededor de un motor en Python puro, una interfaz
React 19 + Vite y un adaptador MCP independiente que habla con la
aplicación por HTTP. Módulos, modelo de datos, pipeline de indexado,
hilos e índice de duplicados: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

```mermaid
flowchart LR
    UI["Interfaz React"] -->|"HTTP (rutas de la interfaz)"| API["Aplicación FastAPI<br/>127.0.0.1:8814"]
    AI["Asistente de IA<br/>(Faustus o cualquier cliente MCP)"] -->|"MCP por stdio"| MCP["mcp_server.py"]
    MCP -->|"HTTP /api/agent/* (registrado)"| API
    API --> ENG["Motor de la biblioteca"]
    ENG --> DB[("SQLite (WAL)<br/>índice, álbumes, registro")]
    ENG --> CLIP["CLIP ViT-B/32<br/>ONNX Runtime"]
    ENG -->|"solo lectura"| PICS[/"Tus carpetas de fotos"/]
    ENG --> HL["HoardLink"] -->|"solo loopback"| LLM["Faustus / Ollama /<br/>llama.cpp"]
```

![Duplicados aproximados con la copia recomendada](docs/media/duplicates.png)
*Duplicados aproximados en la biblioteca de demostración: cada copia reducida se agrupa con su original, la recomendada primero.*

![Cronología por año y mes](docs/media/timeline.png)
*Cronología: meses con miniaturas de muestra; cada mes abre sus fotos.*

## Desarrollo

```bash
.venv/bin/python -m pytest -q            # pruebas locales, sin descargar modelos ni GPU
.venv/bin/python -m pytest -q -m model   # 1 test opcional con el modelo CLIP real (lo descarga si falta)
(cd frontend && npm ci && npm run build) # TypeScript estricto
```

(En Windows: `.venv\Scripts\python -m pytest -q`.)

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
con una tabla de prueba, incluida la ciudad a la que pertenece cada barrio
con filas reales de GeoNames; la validación de filtros, la paginación y
que un resultado vacío diga qué filtro relajar; la protección HTTP, los
intentos de salir de la carpeta de la interfaz y el formato de los
errores; el manifiesto; el adaptador MCP lanzado por stdio contra la
aplicación en marcha (lista de herramientas, anotaciones, imagen de la
hoja de contactos, `photos_show`, álbumes, errores y el mensaje cuando la
aplicación está parada); y el backend de modelos compartido (ajustes
manuales que nunca devuelven el token de Faustus, descripciones contra un
servidor simulado, un lote de descripciones que cede el paso y se aplaza
si el modelo está ocupado, un `backend.json` roto y la traducción de
búsquedas solo en la ruta de la interfaz). El test del modelo indexa las
escenas de demostración con CLIP real y comprueba que cuatro descripciones
en inglés encuentran la escena correcta.

La CI (`.github/workflows/ci.yml`) pasa la batería en Ubuntu y Windows con
Python 3.11, 3.12 y 3.13, compila la interfaz con Node 22 y prueba
`start.ps1`/`stop.ps1` en Windows.

## Privacidad y seguridad

- Solo escucha en `127.0.0.1`; el guard compartido de Hoard Link rechaza
  otra cabecera `Host` (DNS rebinding; `DAGUERRE_ALLOWED_HOSTS` abre un
  nombre de la LAN o una tailnet), las peticiones de otros sitios que no
  sean navegación de nivel superior y que la embeba un `iframe` ajeno; las
  rutas `/api/agent/<tool>` del asistente solo responden al token de
  `data/mcp-token`. Sin CORS y sin telemetría.
- Las únicas peticiones a internet son las que lanzas en Ajustes: el
  modelo CLIP desde Hugging Face y los datos de GeoNames. Las
  descripciones y la traducción de búsquedas solo hablan con servidores de
  modelos en loopback (Faustus, Ollama, llama.cpp u otro compatible con
  OpenAI).
- Cada llamada del asistente queda registrada en **Actividad del
  asistente** (herramienta, argumentos, duración, resultado o error); los
  clics de la propia interfaz van por otras rutas y no se mezclan.
- Los originales solo se leen. El único archivo que se escribe fuera de `data/`
  es el `.xmp` opcional de una foto editada, solo mientras *Escribir archivos
  .xmp* esté activado (desactivado por defecto), fusionado y con copia previa
  como se describe arriba. Quitar una carpeta en Ajustes borra los
  datos propios de Daguerre sobre ella (filas del índice, miniaturas,
  entradas de álbumes), nunca los archivos. El agente puede añadir
  carpetas y álbumes, pero no quitar nada.
- Los nombres de lugares proceden de [GeoNames](https://www.geonames.org/)
  (CC BY 4.0) cuando se descarga el conjunto completo.

## Límites conocidos y hoja de ruta

- Sin vigilancia del sistema de archivos: los reescaneos los lanzas tú, el
  agente o una carpeta nueva.
- La búsqueda vectorial es por fuerza bruta (coseno): válida hasta unas
  200.000 fotos en un solo equipo; más adelante puede ir un índice ANN
  detrás de la misma interfaz.
- Un grupo de duplicados aproximados puede encadenar fotos distintas que
  se parecen, por eso su espacio se muestra como «hasta»; agruparlos de
  forma más estricta (limitar el diámetro del grupo, confirmar con CLIP)
  exige validarlo antes con fotos reales.
- Las copias idénticas byte a byte todavía pueden salir juntas en los
  resultados y en los álbumes.
- Aún no hay una lista de primeros pasos: un aviso ámbar y la marca de
  Ajustes llevan a descargar el modelo de imagen.
- Algunos motivos y nombres de países siguen saliendo en inglés en la
  interfaz en español.
- Los grados de coincidencia de CLIP y los umbrales de duplicados se
  ajustaron con imágenes sintéticas; falta comprobarlos con bibliotecas
  reales grandes.

Notas de diseño de los recorridos por los casos de uso:
[docs/USE_CASES.md](docs/USE_CASES.md),
[docs/USABILITY_REPORT.md](docs/USABILITY_REPORT.md).

## Licencia

[MIT](LICENSE).

## Motores locales PhotoCraft y LightCraft

Daguerre descubre y expone los catálogos MCP completos de PhotoCraft y
LightCraft instalados localmente, con flujos no destructivos para revelar
fotos y crear documentos raster editables por capas. Consulta la
[guía de integración](docs/CRAFT-ENGINES.es.md) para configurar rutas,
conocer los límites y ejecutar pruebas reales aisladas.
