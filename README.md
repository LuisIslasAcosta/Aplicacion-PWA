# Consulta Académica PWA (Actividad 08)

PWA para consultar materias, horarios y docentes. Permite **registrar materias sin conexión**
(IndexedDB) y las **sincroniza con un servidor Flask** al recuperar internet, sin duplicar registros.

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
python3 tests/e2e.py           # genera docs/capturas/*.png y tests/resultados/
```

## Estructura
| Ruta | Contenido |
|---|---|
| `public/` | PWA: `index.html` (Splash + Home), `app.js`, `db.js` (IndexedDB), `sync.js` (cola/sincronización), `sw.js`, `manifest.json` |
| `server/app.py` | Servidor Flask: API REST idempotente + archivos estáticos |
| `tests/e2e.py` | Pruebas end-to-end con Playwright (servidor apagado = sin conexión real) |
| `docs/` | Documento técnico, capturas y diagrama de la versión 1 |

## API
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/health` | Sondeo de disponibilidad |
| GET | `/api/materias` | Catálogo base + materias registradas |
| POST | `/api/materias` | Registra una materia. Idempotente por `uid` (200 `duplicado:true` si ya existe, 201 si es nueva, 400 si es inválida) |

## Publicación
- **Completa (frontend + API):** cualquier hosting Python (p. ej. Render/Railway/PythonAnywhere) con `python3 server/app.py` (usar `PORT`).
- **Solo frontend (GitHub Pages, carpeta `public/`):** funciona offline y guarda en IndexedDB, pero no hay API;
  los registros quedan *pendientes* hasta que exista un servidor en la misma ruta `api/`.
# Aplicacion-PWA
