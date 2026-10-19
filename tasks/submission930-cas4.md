# Entrega930 CAS4 — contraste del formulario vectorial

Base CAS3 aprobada5731d8761ba351adffe01cc524781a1cdc6398d5. Se inspeccionó la captura
real de raíz `web-qa-runs/930-cas3-cua02/vector-native-form.png`: el modal y sus campos
tenían fondo blanco con texto del tema oscuro. El cambio de producto es únicamente
`daguerre_hoard/studio_ui/studio.css`,28 líneas añadidas.

Las reglas del dueño tienen mayor especificidad que el CSS nativo que carga después.
Se acotan a Vector con `body:has(#inputForm)`; Fotos y el propietario no coinciden.
Modal, campos/input/select/option/textarea, catálogo y paneles con el mismo fondo
blanco usan `--panel`, `--ink`, `--line` y `--muted`. El tema claro conserva los valores
del dueño; color-scheme adapta los controles nativos. Los iconos/textos del rail normal
usan muted al pasar su panel a oscuro, manteniendo hover/selección existentes.
No cambian JS/HTML, eventos, validación, tamaños, canvas/artboard, fuentes, iconos,
endpoints, motores ni cierres aprobados.

Verificación focal: PostCSS parse PASS33 reglas (`theme930-cas4-final-parse.txt`).
Contraste calculado de la paleta, no DOM renderizado: oscuro texto13.047:1/etiquetas
8.270:1; claro texto15.589:1/etiquetas5.432:1, `theme930-cas4-contrast.json`.
El paquete instalado sirve el CSS final exacto por ASGI HTTP200;95 herramientas frías,
OFF/OFF, sin crear perfil/importar Library/modelos ni arrancar hijos. Producto importado
sólo del TARGET, `theme930-cas4-installed.txt`; Python externo con `-I` y cwd TARGET.

TARGET nuevo `D:/LocalAI/installed-qa/daguerre-fisiones930-cas4`: instalación completa
y actualización final del payload propio registradas en `target-install930-cas4.txt`
y `target-payload930-cas4-final.txt`. Wheel134030171 bytes/234 miembros, SHA256
`7bda1880194024e8bf17cdac0da5e1d6498273e74595d29355f0eebc6d508a0b`.
`wheel-inventory930-cas4.json` confirma que **sólo studio.css cambia en todo el payload
respecto al TARGET CAS3 aprobado**, que todo el payload propio coincide con TARGET4
y que143 Python y seis binarios siguen exactos. El inventario previo de63 recursos
no incluía studio.css: se conservan los63 intactos y se añade ese CSS como recurso64
en `native-assets930-cas4-final.json`. No Rust, cliente nativo ni suite general.

Raíz hará CUA real de oscuro/claro y botones Cancelar sobre esta revisión exacta;
el autor no afirma contraste DOM ni interacción visual probados. No se han abierto
navegadores/servidores/ventanas, cambiado el TARGET CAS3 de raíz ni tocado datos reales,
SDK, modelos/GPU, integración o publicación. Sin autovoto;930 y926 permanecen abiertas.
