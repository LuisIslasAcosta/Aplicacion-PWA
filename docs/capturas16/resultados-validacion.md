# Resultados de validación v1.1.0-rc.1

| ID | Tipo | Prueba | Resultado | Detalle |
|---|---|---|---|---|
| U1 | Actualización | La v1.0.0 está instalada (SW activo) y tiene datos locales | PASA | cachés=['consulta-shell-v6', 'consulta-datos-v6']; tareas=2; pie='Consulta Académica PWA · v6 · 2026' |
| U2 | Actualización | El Service Worker detecta la v1.1.0, la deja en espera y muestra el aviso «Actualizar» | PASA | waiting=True; la página sigue en v1.0.0=True |
| U3 | Actualización | Al aceptar, se activa la v1.1.0 y la app muestra la nueva versión | PASA | pie='Consulta Académica PWA · v1.1.0 · 2026' |
| U4 | Caché | Las cachés de v1.0.0 se eliminan y la caché nueva contiene los archivos actualizados | PASA | cachés=['consulta-shell-v1.1.0', 'consulta-datos-v1.1.0']; index.html nuevo=True; tareas.js nuevo=True |
| D1 | Datos | Las tareas y materias guardadas en IndexedDB con v1.0.0 se conservan sin cambios | PASA | tareas antes=2 después=2; materia conservada=True |
| D2 | Datos | Las tareas anteriores (sin prioridad) se muestran como «Prioridad media» | PASA | etiquetas=['Prioridad media', 'Prioridad media'] |
| N1 | Nueva funcionalidad | Una tarea con prioridad alta muestra su etiqueta y aparece primero aunque venza después | PASA | primera='Entregar CHANGELOG Prioridad alta Sincronizada' |
| N2 | Nueva funcionalidad | El buscador encuentra «Práctica…» al escribir «PRACTICA» (sin acentos ni mayúsculas) | PASA | resultados=['Práctica de Service Worker Prioridad media Sincronizada']; sin coincidencias='No hay tareas que coincidan con «inexistente».'; al borrar=3 |
| N3 | Nueva funcionalidad | Al editar una tarea anterior, la prioridad se guarda en IndexedDB y se sincroniza con el servidor | PASA | prioridad en servidor=baja |
| R1 | Regresión | Completar una tarea y los filtros Pendientes/Completadas siguen funcionando | PASA | completadas=['Práctica de Service Worker Prioridad media Pendiente de envío'] |
| R2 | Regresión | La lista de materias (catálogo + registradas) sigue mostrando la materia de la v1.0.0 | PASA | visible=True |
| R3 | Regresión | Sin conexión la app abre desde caché, guarda la tarea como pendiente y la sincroniza al reconectar | PASA | pendientes sin conexión=1; sincronizada al volver=True |
| R4 | Regresión | La API acepta tareas de clientes v1.0.0 (sin prioridad) y las guarda como «media» | PASA | HTTP 201; prioridad=media |
| R5 | Regresión | No hubo errores de JavaScript durante todo el proceso | PASA | errores=[] |

**14/14 pruebas pasan**
