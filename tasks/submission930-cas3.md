# Entrega930 CAS3 — transporte HTTPX y clientes padre

Corrección acotada del CHANGES independiente CAS2 sobre c8be1fac. Informe y testigo
fijos leídos antes de editar: `review930-data-cas2/REPORT.md`, `close_transport.py`
y `transport-1dd2f92044/receipt.json`, bajo el research-inbox común. No se reinterpreta
como PASS ningún resultado previo. CAS2 probaba excepciones anteriores a entrar en
HTTPX; no probaba el fallo interior del transporte que la revisión reprodujo.

## Corrección

`global_model.py` compone el SDK intacto con OwnedAsyncClient. HTTPX0.28.1 marca
CLOSED antes de cerrar transportes y httpcore1.0.9 vacía sus conexiones antes del
cierre; por eso se conserva un inventario propio de conexiones/transportes/mounts,
únicos por identidad. Cada recurso sale del inventario sólo después del await
exitoso. Una conexión ya cerrada sale también del pool bajo su lock para que el
cierre posterior del transporte no vuelva a cerrarla. El estado CLOSED del cliente
no se usa como prueba de liberación ni para saltarse pendientes.

GlobalSync cierra tanto el twin como el cliente padre creados por el producto,
conservando ambos y el loop/hilo si falla cualquiera. Los clientes inyectados siguen
siendo propiedad del llamador. El padre registra el loop de sus envíos y su cierre
se enruta al dueño vivo; `GlobalLink.aclose` libera el loop llamador mientras espera
el join. No se modifica SDK, HTTPX ni httpcore. Se usan los internals de las versiones
ya fijadas; una actualización de esas dependencias necesita repetir estas pruebas.

## Pruebas causales propias

`scripts/probe_close_transport930.py` usa fábricas Fotos, Library, Backend,
GlobalLink/Sync y HTTPX reales. ASGI inerte permite una petición real en memoria;
el envío de red síncrono o a otro transporte está prohibido. Falla DENTRO del
transporte, sin sustituir AsyncClient.aclose. Cuatro casos: padre/twin × actual/
retirado. Después de OFF1 y OFF2: CLOSED de HTTPX, transporte abierto, error,
misma app/Link/inner/loop/hilo retenidos y ON rechazado. Tercer intento real cierra
transporte, padre y twin; OFF/appNone sólo entonces, loop cerrado e hilo unido.
Otro OFF no repite el recurso. En padre retirado, se cancela dos veces el consumidor
del tercer OFF mientras el transporte está retenido: espera su liberación y el
cierre termina antes de devolver la cancelación.

El mismo probe ejercita AsyncHTTPTransport, AsyncConnectionPool, AsyncHTTPConnection
y HTTP11 reales con streams sintéticos: el primero cierra una vez, el segundo falla
dos veces y cierra al tercero, sin consumir prematuramente el pool ni repetir éxito.
Recibos fuente: `transport930-cas3-source-pool.txt` PASS. El primer recibo de fuente
sin el caso de pool sigue conservado. Focales anteriores de contrato y fallo exterior:
`global-shutdown930-cas3-outer.txt`,7PASS/1.28s. Ninguna suite general ni Rust rebuild.
El mismo grupo sobre la implementación final vuelve a pasar7 en1.36s,
`global-shutdown930-cas3-final.txt`; el recibo anterior se conserva.

## Paquete y límites

El wheel se vuelve a ensamblar usando los seis binarios previos sin recompilar.
TARGET QA nuevo: `D:/LocalAI/installed-qa/daguerre-fisiones930-cas3`, con Python
externo `C:/Python313/python.exe -I`. `target-install930-cas3.txt` registra instalación
completa; `target-payload930-cas3-final.txt` actualiza sólo el payload final tras añadir
el caso de conexiones del pool. Perfil externo de lanzamiento sin activar/migrar.
`transport930-cas3-installed.txt` ejecuta el mismo probe desde fuera del WT, importando
producto exclusivamente del TARGET. `wheel-inventory930-cas3.json` fija SHA/bytes,
143 fuentes Python iguales al WT y payload propio entero igual al TARGET, seis
binarios con hashes anteriores y ausencia de DB/env/target/node_modules en el wheel.
El catálogo95 y OFF/OFF frío y los63 assets previos se verifican de nuevo sin arrancar
motor alguno. El flujo nativo completo ya tiene evidencia independiente favorable
CAS2 y no se repite por este cambio de cierre.

Resultado instalado: PASS cuatro casos y pool real,58 módulos propios exclusivamente
del TARGET. Frío95/OFF-OFF sin Library/onnxruntime/fastembed, sin Popen ni perfil creado.
Wheel final134029799 bytes/234 miembros, SHA256
`7d1eb1c5f02b09b1334c1e893a5c39f3b1059d20c8f5665fcef0ff77847e0d42`.
Los143 Python coinciden con la fuente y todo el payload propio con el TARGET;
los63 fingerprints anteriores, incluidos seis binarios, permanecen exactos.

Sin sockets/listeners, modelos/GPU, ventanas/GUI, perfiles personales, integración,
publicación ni traslado934. CUA web y diálogos nativos siguen en raíz, CUA nativa
deshabilitada; no se certifica inferencia global938 ni continuidad real de datos.
Theseus permanece incompleto/pausado y fuera de930. Leer/fijar submission_revision
antes de revisar/votar; no hay autovoto.926 y930 quedan abiertas.
