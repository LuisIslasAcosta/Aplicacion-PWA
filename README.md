# Consulta Académica PWA (Actividades 08 y 10)

PWA para consultar materias, horarios y docentes. Permite **registrar materias sin conexión**
(IndexedDB) y las **sincroniza con un servidor Flask** al recuperar internet, sin duplicar registros.

## Novedades de la Actividad 10 (v3)
| Función | Dónde | Notas |
|---|---|---|
| Ciclo de vida del Service Worker (install / activate / update) | `public/sw.js`, `public/app.js` | La versión nueva queda en espera y se muestra el aviso «Hay una nueva versión» con botón **Actualizar** (`SKIP_WAITING`). Al cambiar archivos, subir `VERSION` en `sw.js`. |
| Modo sin conexión | `public/sw.js` | App shell precacheado (incluye `ubicacion.js`); datos con *network-first* + respaldo en caché. |
| Aviso de funciones que requieren internet | `public/app.js` | «Sincronizar ahora» y «Ver en mapa» se atenúan sin red y explican por qué no funcionan. |
| Notificaciones | `public/app.js`, `public/sw.js` | Notificación local con `registration.showNotification()` (botón de prueba, recordatorio de clase, materia guardada) y notificación desde el SW al terminar una sincronización en segundo plano. Pide permiso al usuario. |
| Geolocalización | `public/ubicacion.js` | Botón «📍 Usar mi ubicación» en *Agregar materia*; guarda `lat/lon/precisión` y la envía al servidor (se valida en `server/app.py`). Requiere HTTPS o `localhost`. |
| Diagrama | `docs/diagrama-arquitectura-v3.png` | Componentes implementados. |

## Ejecutar
```bash
pip install -r server/requirements.txt
python3 server/app.py          # http://localhost:5000  (sirve la PWA y la API)
```
Abrir `http://localhost:5000` (localhost cuenta como origen seguro, necesario para Service Worker).
Para probar sin conexión: DevTools → Application → Service Workers → *Offline*, o Network → *Offline*.

> **No abrir `public/` con Live Server** u otro servidor estático: no tiene la API y los registros quedarán pendientes.
> Usar siempre `python3 server/app.py`.

## Pruebas automatizadas
```bash
pip install playwright && playwright install chromium
python3 tests/e2e.py           # genera docs/capturas/*.png y tests/resultados/ (pruebas P1-P10 y A1-A8)
```

## Estructura
| Ruta | Contenido |
|---|---|
| `public/` | PWA: `index.html` (Splash + Home), `app.js`, `db.js` (IndexedDB), `sync.js` (cola/sincronización), `ubicacion.js` (geolocalización), `sw.js`, `manifest.json` |
| `server/app.py` | Servidor Flask: API REST idempotente + archivos estáticos |
| `tests/e2e.py` | Pruebas end-to-end con Playwright (servidor apagado = sin conexión real) |
| `docs/` | Documento técnico, capturas y diagrama de la versión 1 |

## API
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/health` | Sondeo de disponibilidad |
| GET | `/api/materias` | Catálogo base + materias registradas |
| POST | `/api/materias` | Registra una materia. Idempotente por `uid` (200 `duplicado:true` si ya existe, 201 si es nueva, 400 si es inválida) |

## Compatibilidad y limitaciones conocidas
- **HTTPS obligatorio** para Service Worker, notificaciones y geolocalización (excepto `localhost`).
- **Background Sync**: solo Chromium (Chrome/Edge/Opera Android y escritorio). En Firefox/Safari se sincroniza al reconectar o con el botón.
- **iOS/Safari**: las notificaciones web solo funcionan si la PWA está instalada en la pantalla de inicio (iOS 16.4+).
- **Notificaciones**: son locales (no *push* reales). El recordatorio de clase usa `setTimeout`, por lo que solo se dispara si la app sigue abierta o en segundo plano.
- **Geolocalización**: la precisión depende del dispositivo (GPS móvil ±5–30 m; escritorio por Wi-Fi/IP puede ser de cientos de metros). «Ver en mapa» abre OpenStreetMap y requiere internet.

## Publicación
- **Completa (frontend + API):** cualquier hosting Python (p. ej. Render/Railway/PythonAnywhere) con `python3 server/app.py` (usar `PORT`).
- **Solo frontend (GitHub Pages, carpeta `public/`):** funciona offline y guarda en IndexedDB, pero no hay API;
  los registros quedan *pendientes* hasta que exista un servidor en la misma ruta `api/`.
# Aplicacion-PWA
