# Entrega930 — estudio visual nativo

Autor codex-fisiones-producto. Candidato de fuente en el worktree aislado
`D:/LocalAI/worktrees/daguerre-fisiones930`, rama `fisiones-daguerre930`.
Base fotográfica pública c769427, conservando la igualación a referencia aprobada;
incorporación pública vectorial ff98eb259e0ddd06ee7ca642b6908245f48b14e3 en b3cc3074.
Ningún voto propio, integración, publicación, traslado de datos, reinicio original,
activación de GUI ni inferencia real forma parte de esta entrega.

## Resultado

Propietario ASGI frío con Fotos (incluye Layers/Develop íntegros) y Vector, ambos
OFF al iniciar. Conserva interfaces completas y motores propios incorporados, sin
repositorios retirados, servidores antiguos, iframe o enlaces como implementación.
Catálogo95 estático:31 herramientas fotográficas,57 aliases vectoriales y siete
operaciones comunes. Vector conserva25 herramientas nativas y659 comandos; Layers18
y Develop243 esquemas. Consultar catálogos no arranca binarios, tiendas ni modelos.

Proyectos persistentes con IDs reales de fotos/documentos, snapshots y revisiones:
foto→copia derivada→documento vectorial editable guardado→PNG exportado→foto nativa
indexada, con recibos y originales intactos. Selector paginado, enlaces a visor/editor
real y resultados descargables por ID/SHA incluso con módulos apagados.

Activación manual sin escaneos, recuperación de trabajos ni PID antiguos. Trabajos
históricos running aparecen held sin modificar filas. OFF conserva admisión cerrada
y espera escrituras, finally, trabajos, sesiones, ejecutores y ventanas propias.
Cancelación repetida no abandona limpieza. Un cierre fallido conserva app/stopping;
reintenta el callback nativo, impide ON prematuro y no reutiliza un asyncgen agotado
para declarar OFF falso. Las ventanas respetan su cierre normal/diálogo de guardado.

Texto/visión usan el contrato autenticado938 exacto con endpoint/model/revisión
fijados por trabajo, sin fallback/carga local, claves de proveedor ni cambios del SDK.
Errores HTTP, selección obsoleta y truncación mantienen BackendError/caption_error;
una respuesta parcial no se guarda ni reintenta. Configuración anterior permanece
guardada/legible. UI común conserva tema, icono propietario, Cinzel/SourceSans locales
y Faustus; el editor vectorial mantiene toda su interfaz bajo el propietario.

## Pruebas propias y recibos

- `suite930-submission.txt/xml`: **265PASS,15SKIP,1model deselect**,92.10s.
  Omisiones son opt-ins nativos/modelos; los motores se prueban aparte abajo.
- `photo-native-final930.txt`: **30PASS8.70s**, casos originales de Layers/Develop y
  Compositor: documentos editables, copias fotográficas, exposición/exportación,
  readback de capas, transparencia, guardado/reapertura y hashes de originales.
- `vector-native-submission930.txt`: **6PASS1.54s**, binario de producción propio:
  paridad25/659 completa, histórico intacto, edición/undo/redo/reapertura, SVG/PNG/PDF
  y transferencia real foto/vector/foto. No worker simulado en la variante nativa.
- `stdio-native-transfer930.txt`: **1PASS7.75s**, protocolo MCP real→HTTP propietario:
  catálogo frío/OFF, activación explícita, errores nativos, IDs reabiertos, demo/scan
  explícitos, transferencia/export reales, fotoID y descarga Range206 PNG tras OFF.
- `real-factory-retry930.txt`: **7PASS0.69s**, cierre fallido/reintentado con fábricas
  reales Fotos/Vector, BD retenida hasta éxito, dos fallos y tercer OFF; también
  timeout de guardado reconciliado y cancelación doble. Sin ventana real.
- `global-error-contract930.txt`: **23PASS5.52s**, consumidor real con HTTP inerte,
  auth/pin exacto, siguiente trabajo renueva, ningún retry ante409/truncación y
  Captioner real conserva su contrato de error. No llamada de modelo.
- `native-catalog-final930-corrected.txt` y `freeze-owned-catalog930.txt`: esquemas
  completos18/243 iguales a descubrimiento explícito de los binarios recién
  compilados; catálogos fríos ahora fijan sus SHA propios. El primer probe del autor
  pasó por error un string en vez de la lista esperada a `_request`; su fallo de
  invocación se conserva en `native-catalog-final930.txt`, sin reparar producto/oráculo.
- Cliente fotográfico TypeScript/Vite y sintaxis de los clientes JS pasan. Los seis
  binarios release se construyeron aquí con cargo1.95.0, locks y CARGO_BUILD_JOBS=2;
  `native-assets930.json` conserva63 fingerprints de artefactos/clientes/fonts.

Los recuentos se solapan; no deben sumarse. Se conservan también la primera suite
250PASS/5FAIL y las posteriores258/263PASS: los cinco fallos iniciales corrigieron
contrato backend/selección global y expectativas del catálogo ampliado. Ningún
umbral se relajó. La última suite cubre el guard de reactivación y las dos fábricas
reales. Después solo se actualizan metadatos SHA congelados, documentos y recibos;
el helper de congelación se prueba directamente con una ruta relativa propia.

## Límites concretos y revisión

Entrega de **fuente y builds nativos propios**, no certificación de paquete instalado.
Faltan CUA de los clientes completos, diálogos reales de guardar/cancelar/cerrar y
ensamblado/instalación independiente. El cierre automático de ventana está implementado
en Windows; otros sistemas necesitan cerrar la ventana manualmente antes de reintentar
OFF. No se certifica global938 desplegado ni inferencia efectiva por estas pruebas.

Datos/perfiles/token/config/aliases/Hub originales no se han tocado. El antiguo almacén
vectorial no se ha migrado automáticamente; tarea934 conserva esa aceptación y la
continuidad real. Tampoco se certifica reconciliación de perfiles individuales entre
productos: el dispatch MCP común usa el token maestro existente. El inventario
`docs/MIGRATION930.json` declara lo preservado/pendiente; `docs/STUDIO930.md` es el manual.
Theseus sigue incompleto/pausado y no pertenece a930.

El revisor debe leer la submission_revision antes de probar, fijar commit/tree y
votar sobre ese CAS. No aprobar únicamente por este informe. Fuente sin revisión
independiente aún; tarea930 sigue abierta junto a supervisión926.
