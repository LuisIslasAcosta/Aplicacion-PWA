# Documento técnico — Consulta Académica PWA
**Actividad 08: Renderizado y sincronización de datos en una PWA**
Equipo: _(nombres de los integrantes)_ · Repositorio: _(URL de GitHub)_ · URL publicada: _(URL, si aplica)_

## 1. Descripción del proyecto
Sistema de consulta académica (materias, horarios, docentes y temas). Resuelve la necesidad de consultar y
aportar información de materias aun sin internet. Parte del prototipo v1 (Service Worker, notificaciones,
`localStorage`) y en esta actividad se agregó: splash, almacenamiento estructurado en IndexedDB, API en servidor,
cola de registros sin conexión y sincronización sin duplicados.

## 2. Herramientas
| Herramienta | Uso |
|---|---|
| HTML, CSS y JavaScript (sin framework) | Interfaz y lógica de la PWA |
| IndexedDB | Datos estructurados: materias y cola de envío |
| localStorage | Solo la migración de datos de la v1 (se lee una vez y se borra) |
| Service Worker + Cache API | App shell y respaldo de la API sin conexión |
| Background Sync API | Reenvío de la cola aunque la app esté cerrada (Chromium) |
| Python 3 + Flask | Servidor y API REST |
| Playwright + Chromium | Pruebas end-to-end automatizadas y capturas |

## 3. Diseño de pantallas
- **Splash Screen:** pantalla completa con logotipo, nombre y estados de carga ("Abriendo almacenamiento local…",
  "Cargando catálogo…"). Dura mientras se abre IndexedDB y se obtiene el catálogo (mínimo 1.4 s para no parpadear) y
  se desvanece. *Justificación:* informa que la app está preparando datos y evita mostrar una Home vacía; usa los colores
  del `manifest.json` (`theme_color`/`background_color`) para que la transición desde la pantalla de inicio del sistema
  sea continua.
- **Home Screen:** bienvenida, tablero de estado (total de materias, pendientes de envío, conexión, fuente de datos),
  fecha de la última sincronización y acciones (Ver materias, Agregar materia, Sincronizar ahora). Navegación por menú
  superior y barra inferior; una insignia ámbar en el encabezado muestra cuántos registros esperan envío.

Capturas (en `docs/capturas/`): `01-splash.png`, `02-home-online.png`, `04-home-offline.png`.

## 4. Qué se procesa en el cliente y qué en el servidor
| Cliente (navegador) | Servidor (Flask) |
|---|---|
| Generar `uid` (UUID) y fecha de creación | Servir el catálogo base (`data/materias.json`) |
| Validación del formulario | Validar de nuevo cada campo (no se confía en el cliente) |
| Guardar en IndexedDB y marcar `pendiente` | Persistir en `db.json` con escritura atómica y candado |
| Búsqueda y filtro por semestre, renderizado | **Deduplicar por `uid`** (idempotencia) |
| Cola de salida, reintentos con espera creciente | Responder 201 (nuevo), 200 `duplicado` o 400 |

## 5. APIs utilizadas
**Del servidor:** `GET /api/health`, `GET /api/materias`, `POST /api/materias` (consumidas con `fetch()`).
**Del navegador:** IndexedDB, Service Worker, Cache API, Background Sync, Notification API, `navigator.onLine` y eventos `online`/`offline`, `crypto.randomUUID()`.

## 6. Configuración
- **Service Worker (v3):** el app shell se precachea al instalar (`cache.addAll`). Estrategias: *cache-first* para recursos
  estáticos; *network-first* con respaldo en caché para `/api/` y `data/*.json`; los POST nunca pasan por la caché. Al
  activarse borra cachés de versiones anteriores. Las respuestas servidas desde caché llevan la cabecera `X-Desde-Cache`
  para que la interfaz indique "Caché local".
- **Almacenamiento:** base `consulta-academica`; store `materias` (clave `uid`, índice `estado`) y store `meta`.
  Estados: `pendiente` → `sincronizado` (o `error` si el servidor rechaza con 4xx).
- **Sincronización:** al guardar (si hay red), al evento `online`, al abrir la app, con el botón "Sincronizar ahora", con
  reintento de espera creciente (5 s → 60 s) y mediante Background Sync si el navegador lo soporta. Un candado evita dos
  sincronizaciones simultáneas.
- **No duplicar:** (1) `uid` generado en el cliente, (2) servidor idempotente, (3) el registro solo se marca como
  sincronizado al recibir respuesta; si se pierde la respuesta, el reintento reenvía el mismo `uid`.

## 7. Resultados de las pruebas
Ejecutadas con `python3 tests/e2e.py` (Chromium, vista móvil 390×844). Las fases sin conexión usan
`set_offline` **y apagan el servidor**, porque las peticiones del Service Worker no obedecen a la emulación offline de Playwright.

| ID | Prueba | Resultado | Evidencia |
|---|---|---|---|
| P1 | Se presenta la Splash Screen y luego la Home Screen | PASA | — |
| P2 | Los datos (catálogo del servidor) se muestran en la interfaz | PASA | 4 tarjetas; fuente=Servidor |
| P3 | Con la caché la app abre sin conexión y muestra los datos guardados | PASA | 4 tarjetas offline; red='Sin conexión'; fuente='Caché local' |
| P4 | El registro hecho sin conexión queda como pendiente y persiste tras recargar | PASA | badge=1; servidor apagado, aún sin registros |
| P5 | Los pendientes se envían al servidor al recuperar la conectividad | PASA | automática (evento online/Background Sync); servidor=1 |
| P6 | No se duplican registros durante los reintentos de sincronización | PASA | respuesta perdida -> cliente pendiente=1, servidor=1; tras reintento servidor=1; 5 POST paralelos [200, 200, 200, 200, 200] -> servidor=1 |
| P7 | El servidor rechaza datos inválidos (HTTP 400) sin crear registros | PASA | HTTP 400: uid requerido (8-64 caracteres alfanuméricos, - o _) |
| P8 | Datos sincronizados y locales disponibles sin conexión tras recargar | PASA | 6 tarjetas |
| P9 | Sin errores de JavaScript no controlados durante las pruebas | PASA | — |
| P10 | En un servidor sin API (404/405/501) el registro sigue pendiente y no se marca como rechazado | PASA | estados=['pendiente'] |

Capturas con y sin conexión: `02-home-online.png`, `03-materias-online.png`, `04-home-offline.png`,
`05-registro-offline-pendiente.png`, `06-sincronizado.png`.

## 8. Errores encontrados y corregidos
| # | Error | Causa | Corrección |
|---|---|---|---|
| 1 | Sin conexión, Home decía "Fuente de datos: Servidor" | La respuesta venía de la caché del Service Worker y la app no podía distinguirlo | El SW marca esas respuestas con `X-Desde-Cache` y la app muestra "Caché local" |
| 2 | La prueba "sin conexión" no era realmente offline | `set_offline` de Playwright no afecta a las peticiones del Service Worker | Las pruebas también apagan el servidor durante las fases offline |
| 3 | Al abrir la app con un servidor estático (Live Server) el registro quedaba como «Rechazada: HTTP 405» | Se trataba cualquier 4xx como rechazo del registro, pero 404/405/501 significan que no existe la API | 404/405/501 mantienen el registro como pendiente (y devuelven a pendiente los que ya estaban marcados con error); el aviso explica que falta ejecutar `server/app.py` |
| 4 | El aviso (toast) tapaba tarjetas y el título del encabezado se partía en dos líneas con la insignia | Posición inferior del aviso y falta de `nowrap` | Aviso bajo el encabezado; título con `nowrap` y puntos suspensivos |

## 9. Limitaciones
- La migración de datos de la v1 (localStorage → IndexedDB) está implementada pero no tiene prueba automática.
- Background Sync solo existe en navegadores Chromium; en los demás se sincroniza al reconectar, al abrir la app o con el botón.
- `navigator.onLine` solo indica que hay red, no que el servidor responda; por eso un fallo de `fetch` también deja el registro pendiente y programa reintento.
- No hay autenticación ni edición/eliminación de materias; los registros enviados no se pueden modificar.
- La persistencia del servidor es un archivo JSON (suficiente para la práctica, no para producción ni para concurrencia en varios procesos).
- Estrategia *cache-first* del app shell: al cambiar archivos hay que incrementar `VERSION` en `sw.js`.
- Alojado solo como sitio estático (p. ej. GitHub Pages) no hay API: la app funciona, pero los registros quedan pendientes.
- Las pruebas automáticas cubren Chromium; no se probó en Safari/iOS ni Firefox.

## 10. Conclusiones
Separar *guardar* de *enviar* hace que la app funcione igual con o sin red: el usuario siempre escribe en IndexedDB y
la sincronización es un proceso aparte que puede fallar y reintentarse. La idempotencia en el servidor (un `uid` por registro) fue
la pieza clave para reintentar sin miedo a duplicar, incluso cuando se pierde la respuesta. Las pruebas automáticas
también mostraron que simular "sin conexión" requiere cuidado, ya que el Service Worker tiene su propio camino de red.
