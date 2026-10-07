# Motores locales Craft

Daguerre puede lanzar localmente los motores portátiles PhotoCraft y
LightCraft. Cada aplicación mantiene sus formatos nativos y sus propias
herramientas MCP. Daguerre aporta contexto de fototeca, descubrimiento local,
registro de actividad y ubicaciones seguras de salida; todavía no afirma
paridad completa con ninguno de los editores.

## Instalación y configuración

Mantén los paquetes oficiales fuera del repositorio. Daguerre busca
`photocraft-cli.exe` y `lightcraft-cli.exe` en `data/craft-apps/` o
`data/craft-bundles/`, también dentro de un directorio portátil de versión.
Puedes señalar una carpeta compartida con `DAGUERRE_CRAFT_BUNDLES`. Para
indicar rutas concretas, crea `data/craft-engines.json`:

```json
{
  "photocraft": "D:/Apps/photocraft-cli.exe",
  "lightcraft": "D:/Apps/lightcraft-cli.exe"
}
```

El JSON prevalece sobre `DAGUERRE_PHOTOCRAFT_CLI` y
`DAGUERRE_LIGHTCRAFT_CLI`; estas variables prevalecen sobre el descubrimiento
automático y `PATH`. `/api/craft/status` y la herramienta MCP `craft_engines`
muestran disponibilidad y rutas. Los datos, entornos aislados, biblioteca de
LightCraft y artefactos quedan bajo `data/`.

## Catálogo MCP completo

`craft_tools(engine)` inicia brevemente el motor sin interfaz y obtiene sus
nombres de herramientas, descripciones y esquemas JSON actuales. En los
paquetes Windows x64 inspeccionados, PhotoCraft v0.2.0 ofrecía 18 herramientas
MCP y LightCraft v0.2.1 ofrecía 243. Estos recuentos corresponden a esas
versiones. `craft_call(engine, calls)` envía de 1 a 32 llamadas MCP nativas
dentro de una misma sesión. Cada elemento tiene esta forma:
`{"tool":"nombre_original","arguments":{...}}`. Daguerre devuelve las
respuestas y errores reales del motor sin reimplementar ni congelar su
catálogo.

PhotoCraft se inicia con raíces de lectura y escritura en
`data/craft-workspace/`, por lo que sus herramientas de archivos no pueden
alcanzar las carpetas de fotos registradas. LightCraft no documenta una opción
equivalente: Daguerre rechaza rutas absolutas fuera del workspace y de la
carpeta de exportación, además de rutas relativas con `..`. Copia primero los
archivos a ese workspace; el flujo de edición de fotos lo hace por ti.

## Flujos integrados

### Revelar una foto indexada

`craft_develop_photo(photo_id, exposure, output_format="png", long_edge=0)`
acepta el ID obtenido en una búsqueda de Daguerre y una exposición de -5 a
+5 EV. Daguerre copia los bytes originales en su workspace, importa la copia
en la biblioteca local persistente de LightCraft, aplica `light.exposure` y
exporta un derivado en `data/craft-outputs/`. Devuelve las llamadas de
LightCraft, la ruta, la URL local de vista previa y `original_modified: false`.
El visor de fotos también ofrece esta operación con un control de exposición y
muestra el derivado exportado al terminar.

### Abrir una copia editable de una foto

`craft_create_layered_photo(photo_id)` copia la imagen seleccionada al área de
lectura de PhotoCraft, la abre con la herramienta MCP confinada `doc_open`,
añade una capa de píxeles editable, guarda un proyecto `.pcraft` y exporta una
vista previa PNG. El visor ofrece la misma acción y un enlace para descargar el
proyecto nativo. El flujo usa rutas relativas de documento y nunca entrega el
archivo original directamente a PhotoCraft.

### Crear un documento raster editable

`craft_create_layered_document(name, width=512, height=384,
background="#315c7e")` crea un documento nativo `.pcraft` con fondo y una capa
de píxeles editable, y exporta una vista previa PNG. Ambos archivos quedan en
`data/craft-workspace/exports/`. La vista previa se sirve en
`/api/craft/artifacts/<id-aleatorio>.png`.

La interfaz local usa `POST /api/craft/from-photo` y
`POST /api/craft/develop`. También están disponibles como endpoints
autenticados y auditados `/api/agent/*` y como herramientas MCP. Aún no se
importa ni exporta el formato `.comp` de Compositor: sus transformaciones de
capa, máscaras, ajustes y otras propiedades no se han mapeado al modelo nativo
de PhotoCraft.

## Alcance y verificación

Los flujos integrados ejecutan herramientas MCP nativas y conservan el
documento PhotoCraft o la biblioteca de revelado LightCraft. La imagen
exportada por LightCraft es un derivado renderizado, no una copia editable del
RAW original. A Daguerre aún le faltan pantallas propias para toda la interfaz
PhotoCraft, las matrices de importación/exportación PSD/PSB, lotes y droplets,
las operaciones completas de catálogo/revelado de LightCraft, máscaras,
combinación, gestión de presets y automatización de interfaz. El catálogo
nativo sigue accesible dentro de los límites de rutas aisladas. No se ha
demostrado paridad ni superioridad de funciones.

Las pruebas optativas `craft_integration` lanzan los ejecutables configurados
con datos desechables e imágenes sintéticas. Define `DAGUERRE_CRAFT_BUNDLES`
con la carpeta de paquetes y ejecuta `pytest -m craft_integration`. Verifican
capas editables, exportación, cambio de exposición y conservación exacta de
los bytes originales. No uses una fototeca personal en estas pruebas.

## Licencias

Los paquetes inspeccionados de PhotoCraft y LightCraft incluyen licencias MIT
y Apache para el código. Revisa aparte las licencias de fuentes, modelos,
presets, ejemplos y demás recursos antes de redistribuirlos. Esta integración
no copia los ejecutables ni sus recursos al repositorio de Daguerre.
