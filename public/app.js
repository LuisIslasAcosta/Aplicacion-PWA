// ===== Consulta Académica PWA - lógica de la aplicación (v2) =====
// Cliente: validación, uid, renderizado, filtros, almacenamiento local, cola offline.
// Servidor (Flask): catálogo base, persistencia, deduplicación por uid.

const CLAVE_LEGADA = "materias-locales"; // versión 1 guardaba en localStorage
const MIN_SPLASH_MS = 1400;
const TIMEOUT_API_MS = 4000;

let materias = [];          // copia en memoria de IndexedDB
let fuenteDatos = "-";      // "Servidor" | "Caché local" | "Catálogo base"
let esperaReintento = 5000;
let temporizadorReintento = null;

const $ = id => document.getElementById(id);
const pausa = ms => new Promise(r => setTimeout(r, ms));

// ---------- 1. Service Worker ----------
if ("serviceWorker" in navigator) {
  window.addEventListener("load", async () => {
    try {
      const registro = await navigator.serviceWorker.register("sw.js");
      console.log("[PWA] Service Worker registrado. Alcance:", registro.scope);
    } catch (error) {
      console.error("[PWA] Error al registrar el Service Worker:", error);
    }
  });
  // El SW (Background Sync) avisa cuando terminó de reenviar la cola
  navigator.serviceWorker.addEventListener("message", e => {
    if (e.data && e.data.tipo === "sync-terminada") refrescar();
  });
}

// ---------- 2. Navegación (App Shell) ----------
const menu = $("menu");
const btnMenu = $("btn-menu");

function mostrarVista() {
  const nombre = location.hash.replace("#", "") || "inicio";
  document.querySelectorAll(".vista").forEach(v => { v.hidden = v.dataset.vista !== nombre; });
  document.querySelectorAll("[data-vista].activo").forEach(a => a.classList.remove("activo"));
  document.querySelectorAll(`a[data-vista="${nombre}"]`).forEach(a => a.classList.add("activo"));
  menu.classList.remove("abierto");
  btnMenu.setAttribute("aria-expanded", "false");
}

btnMenu.addEventListener("click", () => {
  const abierto = menu.classList.toggle("abierto");
  btnMenu.setAttribute("aria-expanded", String(abierto));
});
document.querySelectorAll("[data-ir]").forEach(b =>
  b.addEventListener("click", () => { location.hash = b.dataset.ir; })
);
window.addEventListener("hashchange", mostrarVista);

// ---------- 3. Estado de red ----------
function actualizarRed() {
  const enLinea = navigator.onLine;
  $("estado-red").textContent = enLinea ? "En línea" : "Sin conexión";
  $("estado-red").classList.toggle("offline", !enLinea);
  $("st-red").textContent = enLinea ? "En línea" : "Sin conexión";
}
window.addEventListener("online", () => {
  actualizarRed();
  mostrarAviso("Conexión recuperada. Sincronizando…");
  sincronizar({ origen: "online" });
});
window.addEventListener("offline", () => {
  actualizarRed();
  mostrarAviso("Sin conexión. Puedes seguir registrando materias.");
});

// ---------- 4. Avisos en pantalla ----------
let temporizadorAviso = null;
function mostrarAviso(texto) {
  const t = $("toast");
  t.textContent = texto;
  t.hidden = false;
  clearTimeout(temporizadorAviso);
  temporizadorAviso = setTimeout(() => { t.hidden = true; }, 4500);
}

// ---------- 5. Datos: IndexedDB + API ----------
function nuevoUid() {
  if (crypto.randomUUID) return crypto.randomUUID();
  return "u" + Date.now().toString(36) + Math.random().toString(36).slice(2, 12);
}

// Migración v1 -> v2: lo guardado en localStorage pasa a IndexedDB como pendiente
async function migrarLocalStorage() {
  let viejas = [];
  try { viejas = JSON.parse(localStorage.getItem(CLAVE_LEGADA)) || []; } catch { viejas = []; }
  if (!viejas.length) return;
  await Almacen.guardarVarias(viejas.map(m => ({
    ...m, uid: nuevoUid(), creadoEn: new Date(m.id || Date.now()).toISOString(), estado: "pendiente"
  })));
  localStorage.removeItem(CLAVE_LEGADA);
}

async function refrescar() {
  materias = (await Almacen.todas()).sort((a, b) =>
    (a.creadoEn || "").localeCompare(b.creadoEn || "") || a.uid.localeCompare(b.uid));
  actualizarListas();
  await actualizarEstado();
}

async function peticionConTiempo(url) {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), TIMEOUT_API_MS);
  try { return await fetch(url, { signal: ctl.signal }); }
  finally { clearTimeout(t); }
}

// Obtiene el catálogo: API -> (caché del SW) -> IndexedDB -> JSON estático
async function descargarCatalogo() {
  try {
    const resp = await peticionConTiempo("api/materias");
    if (!resp.ok) throw new Error("HTTP " + resp.status);
    const remotas = await resp.json();
    if (!Array.isArray(remotas)) throw new Error("Respuesta inesperada");
    await Almacen.guardarVarias(remotas.map(m => ({ ...m, estado: "sincronizado" })));
    if (!resp.headers.get("X-Desde-Cache")) await Almacen.escribirMeta("ultimaSync", new Date().toISOString());
    fuenteDatos = resp.headers.get("X-Desde-Cache") ? "Caché local" : "Servidor";
    return;
  } catch (error) {
    console.warn("[PWA] API no disponible:", error.message);
  }
  if ((await Almacen.todas()).length) { fuenteDatos = "Caché local"; return; }
  try {
    const resp = await fetch("data/materias.json");
    const base = await resp.json();
    await Almacen.guardarVarias(base.map(m => ({ ...m, uid: `base-${m.id}`, estado: "sincronizado" })));
    fuenteDatos = "Catálogo base";
  } catch (error) {
    console.warn("[PWA] No se pudo cargar materias.json:", error);
    fuenteDatos = "Sin datos";
  }
}

// ---------- 6. Sincronización ----------
async function sincronizar({ origen = "manual", incluirErrores = false } = {}) {
  const boton = $("btn-sync");
  boton.disabled = true;
  boton.textContent = "Sincronizando…";
  try {
    const r = await Sync.sincronizar({ incluirErrores });
    await refrescar();
    const enviados = r.enviados + r.duplicados;
    if (r.sinConexion || r.fallidos) {
      if (navigator.onLine) programarReintento();
      if (origen === "manual") mostrarAviso(r.sinApi
        ? "No hay API en este servidor (¿Live Server?). Ejecuta server/app.py. Los registros siguen pendientes."
        : "No se pudo contactar al servidor. Se reintentará automáticamente.");
    } else {
      esperaReintento = 5000;
      if (enviados) mostrarAviso(`Sincronizadas ${enviados} materia(s) con el servidor.`);
      else if (origen === "manual") mostrarAviso(r.rechazados ? "El servidor rechazó algún registro." : "No hay registros pendientes.");
    }
    return r;
  } finally {
    boton.disabled = false;
    boton.textContent = "Sincronizar ahora";
  }
}

// Reintento con espera creciente (5 s, 10 s, 20 s… máx. 60 s) mientras queden pendientes
function programarReintento() {
  clearTimeout(temporizadorReintento);
  temporizadorReintento = setTimeout(() => sincronizar({ origen: "reintento" }), esperaReintento);
  esperaReintento = Math.min(esperaReintento * 2, 60000);
}

async function pedirBackgroundSync() {
  try {
    const reg = await navigator.serviceWorker.ready;
    if ("sync" in reg) await reg.sync.register("sync-materias");
  } catch { /* no soportado: se usa el reintento al reconectar */ }
}
$("btn-sync").addEventListener("click", () => sincronizar({ origen: "manual", incluirErrores: true }));

// ---------- 7. Render ----------
function escapar(texto) {
  const div = document.createElement("div");
  div.textContent = texto;
  return div.innerHTML;
}

function actualizarListas() {
  llenarSemestres();
  llenarSelectorRecordatorio();
  pintarMaterias();
}

function llenarSemestres() {
  const select = $("filtro-semestre");
  const actual = select.value;
  const semestres = [...new Set(materias.map(m => Number(m.semestre)))].sort((a, b) => a - b);
  select.innerHTML = '<option value="">Todos</option>' +
    semestres.map(s => `<option value="${s}">Semestre ${s}</option>`).join("");
  select.value = actual;
}

function llenarSelectorRecordatorio() {
  const select = $("rec-materia");
  const actual = select.value;
  select.innerHTML = materias.map(m => `<option value="${escapar(m.uid)}">${escapar(m.nombre)}</option>`).join("");
  if (actual) select.value = actual;
}

function etiquetaEstado(m) {
  if (m.estado === "pendiente") return '<span class="etiqueta pendiente">⏳ Pendiente de envío</span>';
  if (m.estado === "error") return `<span class="etiqueta error">⚠ Rechazada: ${escapar(m.detalle || "error")}</span>`;
  return '<span class="etiqueta sincronizado">✓ Sincronizada</span>';
}

function pintarMaterias() {
  const semestre = $("filtro-semestre").value;
  const texto = $("buscar").value.trim().toLowerCase();

  const visibles = materias.filter(m =>
    (!semestre || String(m.semestre) === semestre) &&
    (!texto || [m.nombre, m.clave, m.docente].join(" ").toLowerCase().includes(texto))
  );

  $("lista-materias").innerHTML = visibles.map(m => `
    <article class="tarjeta" data-uid="${escapar(m.uid)}" data-estado="${escapar(m.estado)}">
      <h3>${escapar(m.nombre)}</h3>
      <span class="etiqueta">${escapar(m.clave)}</span>
      <span class="etiqueta">Semestre ${Number(m.semestre)}</span>
      <span class="etiqueta">${Number(m.creditos)} créditos</span>
      ${etiquetaEstado(m)}
      <p class="dato">👤 ${escapar(m.docente)}</p>
      <p class="dato">🕘 ${escapar(m.horario)} · ${escapar(m.salon)}</p>
      <details>
        <summary>Ver temas</summary>
        <ul>${(m.temas || []).map(t => `<li>${escapar(t)}</li>`).join("")}</ul>
      </details>
      <p class="autor">Aportada por: ${escapar(m.autor)}</p>
    </article>`).join("") || "<p>No se encontraron materias.</p>";

  const autores = new Set(materias.map(m => m.autor));
  $("resumen").textContent = `${materias.length} materias registradas por ${autores.size} integrantes.`;
}

async function actualizarEstado() {
  const pendientes = materias.filter(m => m.estado === "pendiente").length;
  const errores = materias.filter(m => m.estado === "error").length;
  $("st-total").textContent = materias.length;
  $("st-pendientes").textContent = pendientes + (errores ? ` (+${errores} con error)` : "");
  $("st-fuente").textContent = fuenteDatos;
  const badge = $("badge-pendientes");
  badge.textContent = pendientes;
  badge.hidden = pendientes === 0;
  const ultima = await Almacen.leerMeta("ultimaSync");
  $("st-ultima").textContent = ultima ? new Date(ultima).toLocaleString("es-MX") : "nunca";
}

$("filtro-semestre").addEventListener("change", pintarMaterias);
$("buscar").addEventListener("input", pintarMaterias);

// ---------- 8. Registro de materias (funciona sin conexión) ----------
$("form-materia").addEventListener("submit", async e => {
  e.preventDefault();
  const boton = $("btn-guardar");
  if (boton.disabled) return; // evita doble envío del formulario
  boton.disabled = true;
  try {
    const datos = new FormData(e.target);
    const nueva = {
      uid: nuevoUid(),                       // identificador idempotente generado en el cliente
      nombre: datos.get("nombre").trim(),
      clave: datos.get("clave").trim(),
      semestre: Number(datos.get("semestre")),
      docente: datos.get("docente").trim(),
      horario: datos.get("horario").trim(),
      salon: datos.get("salon").trim(),
      creditos: Number(datos.get("creditos")),
      temas: datos.get("temas").split(",").map(s => s.trim()).filter(Boolean),
      autor: datos.get("autor").trim(),
      creadoEn: new Date().toISOString(),
      estado: "pendiente"
    };
    await Almacen.guardar(nueva);            // 1) siempre primero en local
    e.target.reset();
    await refrescar();
    location.hash = "materias";
    pedirBackgroundSync();

    if (navigator.onLine) {                  // 2) intentar enviar de inmediato
      const r = await sincronizar({ origen: "guardar" });
      if (!r.sinConexion && !r.fallidos) {
        notificar("Materia guardada", `"${nueva.nombre}" se agregó y se sincronizó.`);
        return;
      }
    }
    mostrarAviso("Guardada en este dispositivo. Se enviará al recuperar la conexión.");
    notificar("Materia guardada sin conexión", `"${nueva.nombre}" se enviará al servidor al reconectar.`);
  } catch (error) {
    console.error("[PWA] No se pudo guardar:", error);
    mostrarAviso("No se pudo guardar en el dispositivo.");
  } finally {
    boton.disabled = false;
  }
});

// ---------- 9. Notificaciones ----------
// API: Notification API (permiso) + ServiceWorkerRegistration.showNotification()
function actualizarPermiso() {
  if (!("Notification" in window)) { $("permiso-estado").textContent = "no soportado"; return; }
  const textos = { granted: "concedido", denied: "denegado", default: "sin decidir" };
  $("permiso-estado").textContent = textos[Notification.permission];
}

$("btn-permiso").addEventListener("click", async () => {
  if (!("Notification" in window)) return;
  await Notification.requestPermission();
  actualizarPermiso();
  if (Notification.permission === "granted") {
    notificar("Notificaciones activadas", "Te avisaremos de tus recordatorios de clase.");
  }
});

async function notificar(titulo, cuerpo) {
  if (!("Notification" in window) || Notification.permission !== "granted") return;
  const opciones = {
    body: cuerpo, icon: "icons/icon-192.png", badge: "icons/icon-192.png",
    tag: "consulta-academica", data: { url: "./index.html#materias" }
  };
  try {
    const registro = await navigator.serviceWorker.ready;
    registro.showNotification(titulo, opciones);
  } catch {
    new Notification(titulo, opciones);
  }
}

let recordatorio = null;
$("btn-recordatorio").addEventListener("click", async () => {
  if ("Notification" in window && Notification.permission === "default") {
    await Notification.requestPermission();
    actualizarPermiso();
  }
  const materia = materias.find(m => m.uid === $("rec-materia").value);
  if (!materia) return;
  const minutos = Number($("rec-minutos").value) || 1;
  clearTimeout(recordatorio);
  $("rec-estado").textContent = `Recordatorio de "${materia.nombre}" programado en ${minutos} min.`;
  recordatorio = setTimeout(() => {
    $("rec-estado").textContent = "Recordatorio enviado.";
    notificar(`Recordatorio: ${materia.nombre}`, `${materia.horario} · ${materia.salon}`);
  }, minutos * 60 * 1000);
});

// ---------- 10. Arranque (Splash -> Home) ----------
function ocultarSplash() {
  const splash = $("splash");
  splash.classList.add("oculto");
  document.body.classList.remove("cargando");
  setTimeout(() => { splash.hidden = true; }, 500);
}

async function iniciar() {
  const inicio = performance.now();
  $("anio").textContent = new Date().getFullYear();
  actualizarRed();
  actualizarPermiso();
  mostrarVista();
  try {
    $("splash-estado").textContent = "Abriendo almacenamiento local…";
    await migrarLocalStorage();
    await refrescar();
    $("splash-estado").textContent = "Cargando catálogo de materias…";
    await descargarCatalogo();
    await refrescar();
    $("splash-estado").textContent = "Listo";
  } catch (error) {
    console.error("[PWA] Error al iniciar:", error);
    $("splash-estado").textContent = "Almacenamiento local no disponible";
  }
  await pausa(Math.max(0, MIN_SPLASH_MS - (performance.now() - inicio)));
  ocultarSplash();
  if (navigator.onLine) sincronizar({ origen: "arranque" });
}
iniciar();
