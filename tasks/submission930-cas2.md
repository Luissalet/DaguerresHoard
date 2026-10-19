# Entrega930 CAS2 — paquete Windows instalado y cierre interno

Sustituye como candidato a CAS1 d0daaba84196e2c6e993d49928d87d25dfcf9e11;
conserva sus fuentes públicas, funcionalidades y recibos. La tarea sigue abierta,
sin integración, publicación, revisión propia, modelos, GPU, GUI ni datos reales.

## Cambios concretos

- Wheel Windows x64 con143 fuentes Python exactas, los seis ejecutables propios ya
  compilados, las tres interfaces, SDK `_data`, catálogos, iconos, fonts y licencias.
  No se reconstruye Rust. `build_support.py` ensambla recursos existentes; falla si
  faltan binarios/clientes/fonts. Excluye árboles Rust/target, node_modules y perfiles.
- `install_studio.py` instala dependencias bloqueadas y payload en TARGET nuevo,
  con Python externo y launchers aislados. Entrypoints app/MCP propios. Perfil fuera
  del payload, `.env` sin sobrescribir entorno del llamador, defaults de lanzamiento
  y selección explícita de directorio también para demo. Ningún escaneo ni recuperación.
- Se corrige un fallo real de CAS1: el dispatcher recortaba `/photos` pero fijaba
  también root_path, provocando404 del CSS en StaticFiles anidado. El hijo recibe
  path nativo sin root_path duplicado; reescritura finita de URLs públicas y OpenAPI.
- `GlobalSync.close` propio ya no usa el cierre SDK que silenciaba `aclose` y
  descartaba los dueños. Propaga errores, retiene inner/loop/thread hasta éxito,
  drena ejecutor/generadores y une/cierra el loop. Backend conserva además cada Link
  retirando hasta cerrar de verdad. No se ha editado el SDK.

## Evidencia instalada

TARGET externo: `D:/LocalAI/installed-qa/daguerre-fisiones930-cas2c`.
Python externo: `C:/Python313/python.exe -I`; cwd de las pruebas es ese TARGET.
Los scripts del checkout son sólo harness, no ruta de imports de producto.

`installed-probe930-final-payload.txt` e `installed930-cas2.json`: PASS,95 herramientas,
OFF/OFF inicial, catálogo sin imports de librería/modelos ni procesos hijos. MCP stdio
real y HTTP instalado: tres interfaces completas y sus recursos (4/8/7 enlaces),
fonts/licencias,63 fingerprints incluidos seis binarios, proyecto persistente,
demo/scan explícitos, foto→documento vectorial→PNG→photoID real, reapertura y Range206
después de ambos OFF.74 módulos propios importados exclusivamente de TARGET.
`.env`, token válido y backend.json sintéticos conservan SHA; caller dev prevalece.
No se depende de repos retirados ni de la venv del checkout.

`installed-close930-cas2.txt`: PASS en fábricas Fotos reales instaladas, Link/twin/
httpx reales, requests HTTP prohibidos. Dos fallos de aclose, mismos recursos retenidos,
ON rechazado y tercer OFF exitoso, cliente cerrado, loop cerrado e hilo unido. Casos
del Link actual y Link en retirada.58 módulos propios exclusivamente de TARGET.
`global-shutdown930.txt/xml`:10PASS/1SKIP,1.86s; cierres causales y contrato/flujo fuente.
No se han repetido suites generales sin cambio. Los recuentos se solapan.

`wheel-inventory930-cas2.json`: SHA/bytes/miembros del wheel, hashes de los seis
binarios,143 fuentes Python exactas al WT, entrypoints y ausencia de perfiles/env/DBs,
árboles target/node_modules y PDB. `native-assets930-cas2.json` conserva63 SHA.
Los logs de builds/install previos permanecen; ningún fallo se presenta como PASS.

Wheel final:134029084 bytes,234 miembros,
SHA256 `b39ceab51b6be1cf456a9772f980689cbed3dcde6ee8d54453a676b63896460f`.
Después de instalar completo el TARGET nuevo (`target-install930-cas2-final.txt`),
se actualizó sólo su payload propio con el wheel final (`target-payload930-final.txt`),
conservando dependencias y launch/profile externos. Todos los miembros propios del
wheel son byte a byte iguales al TARGET, además de los143 Python iguales al WT.
La última corrección selecciona el `.env` del perfil CLI explícito después de parsear
argumentos. `installed-entrypoint930.txt` pasa el entrypoint real con `uvicorn.run`
sustituido por una aserción: CLI gana al perfil del entorno, carga su `.env`, conserva
dev del llamador y ambos módulos OFF, sin abrir listener ni importar la biblioteca.
Tras esa corrección se repitió únicamente el flujo del paquete final, no una suite general.

Primera prueba instalada encontró CSS404 y se corrigió el producto. La siguiente
asumió erróneamente401 en una ruta vectorial de lectura histórica; la ruta contractual
`/api/agent/call` sí exige token y se comprueba sin cambiar el protocolo. Otra pasó
todo el flujo y falló al comparar un token de fixture de24 caracteres: el código
original requiere32 y lo regeneró. Se repitió con token válido, conservando los logs
originales y usando un perfil nuevo, sin relajar un umbral del producto.

## Límites y revisión

El paquete está instalado y probado por CPU/API/MCP en un TARGET QA. No es despliegue
en la instalación personal. Raíz conserva CUA web y aceptación independiente; no
se han abierto ventanas nativas ni certificado diálogos guardar/cancelar. La herramienta
CUA nativa está deshabilitada. Global938 real, inferencia efectiva, perfiles individuales,
aliases/Hub y migración de datos antiguos siguen pendientes de aceptación934. Theseus
continúa incompleto/pausado y no pertenece a930.

Leer y fijar submission_revision antes de probar. Revisar fuente y recibos; no votar
sólo sobre este informe. No hay aprobación del autor.926 y930 permanecen abiertas.
