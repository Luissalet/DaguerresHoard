# Importación Compositor → PhotoCraft

Daguerre importa un subconjunto raster de paquetes `.comp` a proyectos
PhotoCraft `.pcraft` con capas de píxeles editables. La conversión usa el motor
local sin interfaz gráfica y conserva el manifiesto y los PNG referenciados
como copia de procedencia. No modifica la fuente ni aplana contenido no
compatible. Los archivos auxiliares como QuickLook no se copian.

## Uso

La herramienta MCP `craft_import_compositor(source_path, preflight_only=false)`
selecciona una carpeta `.comp` existente. También existen `POST
/api/agent/craft_import_compositor` (autenticado y auditado) y `POST
/api/craft/import-compositor` (flujo local), con el mismo cuerpo JSON:

```json
{"source_path":"D:/Proyectos/imagen.comp","preflight_only":true}
```

`preflight_only=true` devuelve el informe sin escribir ni iniciar PhotoCraft.
Con `false`, la importación valida igualmente todo el contenido antes de
crear la copia. Hay que leer `status`: `ready` significa validación completa;
`blocked`, contenido incompatible; `imported`, proyecto generado y reabierto;
`failed`, error del motor con recibo de diagnóstico. Un reintento usa un ID
nuevo. Véase [la configuración del motor](CRAFT-ENGINES.md#install-and-configure).

## Alcance y límites

Se aceptan versiones de manifiesto 1–11, espacio sRGB, entre 1 y 128 capas
raster sin grupos, PNG RGB/RGBA de 8 bits sin perfil ICC incrustado, modo
Normal, nombre, visibilidad, opacidad, tamaño nativo y posición entera.
La resolución admite 1–9600 ppp. Lados de lienzo/imagen: 1–8192 píxeles;
presupuesto total: 100 millones de píxeles, 512 MiB de PNG codificados y
4 MiB de manifiesto. Las rutas inseguras, UUID repetidos, JSON ambiguo,
activos ausentes/dañados y campos desconocidos impiden importar.

Grupos, máscaras, recortes vivos, ajustes, texto, formas, efectos, guías,
otros modos de fusión, escalado, giro, reflejos, posiciones fraccionarias y
versiones futuras quedan bloqueados. El informe identifica cada propiedad
afectada; no existe opción para descartarla silenciosamente.

PhotoCraft recorta los márgenes totalmente transparentes al pegar. El
informe declara esta transformación y verifica la posición de los píxeles
visibles; el PNG completo permanece en la copia. Los PNG totalmente
transparentes se rechazan; las capas vacías sin PNG se conservan como capas
vacías nativas, cuyo rectángulo original solo permanece en procedencia.
Los UUID se sustituyen por IDs nativos y el recibo conserva la relación.
La selección activa de origen, el historial y la vista no se importan.

## Resultado y evidencia

El resultado incluye proyecto nativo, vista PNG, informe JSON, hashes SHA-256
del motor/manifiesto/activos/resultados, IDs de cada capa y respuestas MCP
reales. Los archivos se sirven como `/api/craft/artifacts/<id>.pcraft`,
`.png` y `.json`. Antes de devolver `imported`, el motor reabre el proyecto,
comprueba dimensiones, orden, nombres, visibilidad, opacidad, tipo raster y
límites visibles; el PNG debe tener el mismo hash antes y después de reabrir.
Un fallo elimina las salidas nativa y PNG incompletas y conserva la copia de
entrada y el recibo para diagnosticarlo.

Las pruebas reales usan tres paquetes sintéticos propios: dos variantes con
tres capas, opacidad 0,5, desplazamientos positivos/negativos, capa RGBA oculta
y 144 ppp; otro con márgenes transparentes y capa vacía. Los píxeles se
comprueban en posiciones concretas, y revelar una capa importada oculta cambia
la exportación. Hay pruebas negativas de contenido incompatible, recursos
ausentes/dañados/rutas inseguras, valores no finitos y fallos del motor.
La API auditada y el MCP stdio también ejecutan la operación real.

No se ha comparado con el render de Compositor, que requiere macOS. La
equivalencia visual completa, el formato íntegro, la exportación `.comp`
inversa y la paridad de interfaz siguen pendientes. La especificación se fija
al commit [`11d8d7a`](https://github.com/robbietilton/Compositor/blob/11d8d7a50992b24fd9a760a1c13b1c01b70aaf30/docs/project-format.md);
no se copia su código. Esta es una ampliación de intercambio comprobada,
sin afirmación de reemplazo, paridad o superioridad general.
