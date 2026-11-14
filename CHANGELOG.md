# Registro de cambios (CHANGELOG)

Todos los cambios importantes de **Consulta Académica PWA** se documentan en este archivo.
El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto usa
[Versionado Semántico](https://semver.org/lang/es/): `MAYOR.MENOR.PARCHE`.

- **MAYOR**: cambios que rompen la compatibilidad (por ejemplo, una API o datos locales incompatibles).
- **MENOR**: funciones nuevas que siguen siendo compatibles con la versión anterior.
- **PARCHE**: correcciones de errores sin funciones nuevas.

## [Sin publicar]

## [1.1.0] - 2026-11-14
Versión candidata validada: `v1.1.0-rc.1` (14/14 pruebas en `tests/validacion_v1_1_0.py`).

### Agregado
- Campo **prioridad** (alta, media o baja) en el formulario para crear y editar tareas.
- Etiqueta de color con la prioridad en cada tarjeta de tarea; las de prioridad alta llevan un borde rojo.
- **Buscador de tareas** por título o descripción. No distingue mayúsculas ni acentos, se combina con el
  filtro Todas/Pendientes/Completadas y funciona sin conexión.
- Mensaje «No hay tareas que coincidan con…» cuando la búsqueda no encuentra resultados.
- La API `POST /api/tareas` acepta y guarda el campo `prioridad`.
- Prueba automatizada de liberación `tests/validacion_v1_1_0.py`: simula a un usuario con la v1.0.0
  instalada que recibe la v1.1.0. Las evidencias quedan en `docs/capturas16/`.

### Cambiado
- La lista de tareas pendientes se ordena primero por prioridad y después por fecha límite.
- El pie de página muestra la versión semántica de la app (`v1.1.0`) en lugar del número interno de caché.
- `VERSION` del Service Worker: `v6` → `v1.1.0`. Las cachés quedan como `consulta-shell-v1.1.0` y
  `consulta-datos-v1.1.0`, y las de la versión anterior se eliminan al activarse.

### Corregido
- Prueba de sincronización con falso positivo: `wait_for_function` daba por cumplida una Promesa
  antes de que terminara el envío. Se cambió por una espera que evalúa el resultado (`esperar()`).

### Compatibilidad y datos
- **No cambia la versión de IndexedDB** (`DB_VERSION = 6`). Las tareas guardadas con v1.0.0 se conservan
  tal cual y se muestran como prioridad «media» hasta que el usuario las edite.
- Los clientes que todavía tengan la v1.0.0 pueden seguir enviando tareas sin prioridad: el servidor
  les asigna «media».
- **Publicación:** la PWA y la API se publican juntas en Render (`https://aplicacion-pwa.onrender.com/`) con
  `python3 server/app.py`, así que el frontend nuevo nunca queda con una API anterior. Si en el futuro se
  separan (por ejemplo, con `netlify.toml`), hay que desplegar primero la API: el servidor v1.0.0 descarta la
  prioridad sin marcar error.
- **Datos del servidor en Render:** el disco del servicio no es persistente, así que `tareas.json` y `db.json`
  se reinician en cada despliegue. Los datos de los usuarios no se pierden porque viven en su IndexedDB.

## [1.0.0] - 2026-11-07
Primera versión publicada en Render: es la línea base de las Actividades 08 a 14.

### Agregado
- Consulta de materias, horarios y docentes, y registro de materias sin conexión con IndexedDB.
- Sincronización con el servidor Flask sin duplicados (`uid`) y Background Sync en Chromium.
- Ciclo de vida del Service Worker con aviso «Hay una nueva versión» y botón **Actualizar**.
- Notificaciones locales y geolocalización en materias y tareas.
- Módulo de tareas con fecha límite, estado, ubicación opcional y avisos de vencimiento.
- `sw.js` se sirve con `Cache-Control: no-cache` para detectar versiones nuevas de inmediato.

[Sin publicar]: https://github.com/LuisIslasAcosta/Aplicacion-PWA/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/LuisIslasAcosta/Aplicacion-PWA/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/LuisIslasAcosta/Aplicacion-PWA/releases/tag/v1.0.0
