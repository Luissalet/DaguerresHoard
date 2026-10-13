# Motores de imagen de Daguerre

Daguerre incorpora los motores completos de capas y revelado y sus editores de escritorio como fuente Rust detached. Los ejecutables, formatos, APIs y recursos MCP son propios; las licencias y procedencia histórica se conservan. No necesita aplicaciones, repositorios ni ejecutables externos.

## Compilar y usar

`python scripts/build_engines.py` construye ambos motores y editores; `--debug` elige el perfil de desarrollo. Sólo se ejecutan los binarios propios bajo `native/bin`. Las rutas externas guardadas y las variables antiguas se conservan como datos y no seleccionan el motor. Véase [el detalle de incorporación](OWNED-ENGINES.md).

`image_engines` muestra el estado, `image_tools` descubre el catálogo completo de `layers` o `develop`, e `image_call` ejecuta sus operaciones. Los nombres anteriores `craft_*` y las claves `photocraft`/`lightcraft` siguen siendo alias. Las 22 herramientas anteriores permanecen y se añaden ocho nombres propios:30 en total. Enumerar el catálogo no certifica todas las operaciones.

## Flujos de fotografía y editores

`image_create_layered_photo` crea una copia por capas de una foto indexada; `image_create_layered_document` crea un documento editable nuevo. Se guardan `.dglayers` y una vista previa PNG. `image_develop_photo` revela una copia y exporta una imagen derivada. `image_open_editor` abre el editor completo propio del resultado. Las herramientas nativas utilizan la sesión del editor mientras esté abierto y vuelven al modo sin ventana al cerrarlo.

La vista de detalle ofrece creación por capas, control de exposición, revelado, descarga del proyecto editable y apertura del editor completo. Los originales permanecen intactos. Se admiten históricos `.pcraft`, PSD/PSB e imágenes raster; bibliotecas y preferencias antiguas se copian hacia ubicaciones propias sin reescribirlas. El revelado conserva su catálogo y recetas; una imagen plana exportada no sustituye el original ni su documento editable.

La importación de paquetes `.comp` mantiene sus capas raster, informes de propiedades no representadas, vistas previas y comprobación por reapertura. No aplana contenido incompatible ni oculta errores. La [matriz detallada existente](CRAFT-ENGINES.md#import-a-compositor-package) conserva su alcance.

API preferida `/api/image-engine/` y `/api/agent/image_*`; las rutas anteriores permanecen. Fototeca, metadatos, álbumes, búsquedas, recetas XMP y reglas de originales se conservan. Todas las salidas y preferencias viven en los datos configurados de Daguerre.

## Verificación y licencias

Los motores y editores completos están incorporados; las pruebas focales reales se realizan con datos sintéticos privados. No se afirma certificación de todos los formatos RAW, comandos ni combinaciones de exportación. Después de compilar, `DAGUERRE_NATIVE_TESTS=1` habilita las pruebas `pytest -m craft_integration`. La suite normal no carga el modelo CLIP real.

Cada motor conserva LICENSE-MIT, LICENSE-APACHE, NOTICE, ASSETS y PROVENANCE con revisión fija y hashes. Las fuentes tipográficas y el diccionario conservan sus licencias individuales. Los iconos son los existentes de Daguerre. No se copiaron modelos de texto ni se depende operativamente del origen.
