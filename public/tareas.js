// ===== Módulo de tareas (Actividad 12) =====
// Registro y consulta de tareas con fecha límite, ubicación opcional y avisos locales.
// Datos: IndexedDB (store "tareas"). Se envían al servidor con la cola de Sync (api/tareas).
// Usa funciones globales de app.js: escapar, nuevoUid, mostrarAviso, notificar, sincronizar,
// pedirBackgroundSync, requiereConexion, peticionConTiempo, refrescar, actualizarControlesConexion.
// Avisos: SOLO locales y disparados por una acción del usuario o al abrir la app.
// No se usan temporizadores para avisos futuros (no funcionarían con la página cerrada).

(function (global) {
  const $ = id => document.getElementById(id); // propio del módulo (no depende del $ de app.js)
  let lista = [];          // copia en memoria de IndexedDB
  let filtro = "todas";    // todas | pendientes | completadas
  let editando = null;     // uid de la tarea en edición, o null si es nueva
  let ubicacion = null;    // { lat, lon, precision, tomadoEn } o null

  // ---------- Fechas (siempre en hora local, formato AAAA-MM-DD) ----------
  function hoyLocal() {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  }
  function diasHasta(fechaLimite) {
    const [a, m, d] = fechaLimite.split("-").map(Number);
    const [ha, hm, hd] = hoyLocal().split("-").map(Number);
    return Math.round((Date.UTC(a, m - 1, d) - Date.UTC(ha, hm - 1, hd)) / 86400000);
  }
  function formatoFecha(f) {
    const [a, m, d] = f.split("-");
    return `${d}/${m}/${a}`;
  }
  // { texto, clase } según la cercanía de la fecha límite
  function vencimiento(t) {
    if (t.estado === "completada") return { texto: "Completada", clase: "ok" };
    const dias = diasHasta(t.fechaLimite);
    if (dias < 0) return { texto: `Vencida hace ${-dias} día(s)`, clase: "vencida" };
    if (dias === 0) return { texto: "Vence hoy", clase: "hoy" };
    if (dias === 1) return { texto: "Vence mañana", clase: "pronto" };
    if (dias <= 3) return { texto: `Vence en ${dias} días`, clase: "pronto" };
    return { texto: `Vence el ${formatoFecha(t.fechaLimite)}`, clase: "normal" };
  }
  function porAtender() { // pendientes vencidas o que vencen hoy
    return lista.filter(t => t.estado === "pendiente" && diasHasta(t.fechaLimite) <= 0);
  }

  // ---------- Datos ----------
  async function cargar() {
    lista = (await Almacen.todasTareas()).sort((a, b) =>
      (a.estado === "completada") - (b.estado === "completada") ||
      a.fechaLimite.localeCompare(b.fechaLimite) || a.creadoEn.localeCompare(b.creadoEn));
    pintar();
  }
  function contarSync() { return lista.filter(t => t.sync === "pendiente").length; }

  // Baja las tareas del servidor y las mezcla sin pisar cambios locales pendientes
  async function descargarRemotas() {
    try {
      const resp = await peticionConTiempo("api/tareas");
      if (!resp.ok) return;
      const remotas = await resp.json();
      if (!Array.isArray(remotas)) return;
      const locales = new Map((await Almacen.todasTareas()).map(t => [t.uid, t]));
      const nuevas = [];
      for (const r of remotas) {
        const l = locales.get(r.uid);
        if (!l || (l.sync !== "pendiente" && r.actualizadoEn > l.actualizadoEn)) nuevas.push({ ...r, sync: "sincronizado" });
      }
      if (nuevas.length) await Almacen.guardarTareas(nuevas);
    } catch { /* sin red: se trabaja con lo guardado en el dispositivo */ }
  }

  // ---------- Pantalla de listado ----------
  function etiquetaSync(t) {
    if (t.sync === "sincronizado") return '<span class="etiqueta sincronizado">Sincronizada</span>';
    if (t.sync === "error") return `<span class="etiqueta error" title="${escapar(t.detalle || "")}">Rechazada</span>`;
    return '<span class="etiqueta pendiente">Pendiente de envío</span>';
  }

  function pintarEstado() {
    const el = $("tareas-estado");
    if (!el) return;
    const pend = contarSync();
    el.textContent = `${navigator.onLine ? "En línea" : "Sin conexión"} · ` +
      (pend ? `${pend} cambio(s) pendiente(s) de sincronizar` : "todo sincronizado");
    el.classList.toggle("offline", !navigator.onLine);
  }

  function pintar() {
    const cont = $("lista-tareas");
    if (!cont) return;
    const visibles = lista.filter(t =>
      filtro === "todas" || (filtro === "pendientes" ? t.estado === "pendiente" : t.estado === "completada"));
    cont.innerHTML = visibles.map(t => {
      const v = vencimiento(t);
      const u = t.ubicacion;
      return `<article class="tarjeta tarea" data-uid="${escapar(t.uid)}" data-estado="${t.sync}" data-tarea="${t.estado}">
        <h3>${escapar(t.titulo)} ${etiquetaSync(t)}</h3>
        <p class="dato"><span class="venc ${v.clase}">${v.texto}</span> · Fecha límite: ${formatoFecha(t.fechaLimite)}</p>
        ${u ? `<p class="dato">📍 ${Number(u.lat).toFixed(5)}, ${Number(u.lon).toFixed(5)}${u.precision ? ` (±${Number(u.precision)} m)` : ""}
          <a class="enlace-mapa${navigator.onLine ? "" : " sin-red"}" data-requiere-conexion="Ver en mapa" href="${escapar(Ubicacion.enlaceMapa(u))}" target="_blank" rel="noopener">Ver en mapa</a></p>`
          : '<p class="dato sin-ubicacion">Sin ubicación</p>'}
        <div class="detalle-tarea" hidden>
          <p>${t.descripcion ? escapar(t.descripcion) : "<em>Sin descripción.</em>"}</p>
        </div>
        <div class="acciones">
          <button class="boton secundario" data-accion="ver" type="button">Ver detalle</button>
          <button class="boton secundario" data-accion="editar" type="button">Editar</button>
          <button class="boton secundario" data-accion="completar" type="button">${t.estado === "completada" ? "Reabrir" : "Completar"}</button>
        </div>
      </article>`;
    }).join("") || "<p>No hay tareas en esta lista.</p>";

    const urgentes = porAtender();
    const aviso = $("tareas-urgentes");
    aviso.hidden = urgentes.length === 0;
    if (urgentes.length) aviso.textContent = `Atención: ${urgentes.length} tarea(s) vencida(s) o que vence(n) hoy.`;
    const pendientes = lista.filter(t => t.estado === "pendiente").length;
    $("tareas-resumen").textContent = `${lista.length} tarea(s) · ${pendientes} por hacer`;
    const home = $("resumen-tareas");
    if (home) home.textContent = `Tareas por hacer: ${pendientes}${urgentes.length ? ` (${urgentes.length} por atender)` : ""}.`;
    pintarEstado();
    actualizarControlesConexion();
  }

  // ---------- Avisos locales ----------
  // Pide permiso solo si aún no se ha decidido (siempre desde una acción del usuario).
  async function asegurarPermiso() {
    if (!("Notification" in window)) return false;
    if (Notification.permission === "default") await Notification.requestPermission();
    if (typeof actualizarPermiso === "function") actualizarPermiso();
    return Notification.permission === "granted";
  }

  // Aviso al abrir la app: una vez al día, si hay tareas vencidas o que vencen hoy.
  async function avisarVencimientos() {
    if (!("Notification" in window) || Notification.permission !== "granted") return;
    const n = porAtender().length;
    if (!n) return;
    const hoy = hoyLocal();
    if ((await Almacen.leerMeta("avisoVencimiento")) === hoy) return;
    await Almacen.escribirMeta("avisoVencimiento", hoy);
    notificar("Tareas por atender", `Tienes ${n} tarea(s) vencida(s) o que vencen hoy.`, "./index.html#tareas", "consulta-tareas");
  }

  // ---------- Formulario (crear / editar) ----------
  function mostrarUbicacion(texto) { $("tarea-ubicacion-estado").textContent = texto; }

  function abrirFormulario(uid) {
    const form = $("form-tarea");
    form.reset();
    editando = uid || null;
    ubicacion = null;
    mostrarUbicacion("");
    $("btn-quitar-tarea-ubicacion").hidden = true;
    $("titulo-form-tarea").textContent = editando ? "Editar tarea" : "Nueva tarea";
    $("btn-guardar-tarea").textContent = editando ? "Guardar cambios" : "Guardar tarea";
    if (editando) {
      const t = lista.find(x => x.uid === editando);
      if (!t) return;
      form.elements.titulo.value = t.titulo;
      form.elements.descripcion.value = t.descripcion || "";
      form.elements.fechaLimite.value = t.fechaLimite;
      form.elements.estado.value = t.estado;
      if (t.ubicacion) {
        ubicacion = t.ubicacion;
        mostrarUbicacion(`Ubicación guardada: ${t.ubicacion.lat}, ${t.ubicacion.lon}.`);
        $("btn-quitar-tarea-ubicacion").hidden = false;
      }
    } else {
      form.elements.fechaLimite.value = hoyLocal();
    }
    location.hash = "tarea";
  }

  async function guardarFormulario(e) {
    e.preventDefault();
    const boton = $("btn-guardar-tarea");
    if (boton.disabled) return;
    boton.disabled = true;
    try {
      const datos = new FormData(e.target);
      const ahora = new Date().toISOString();
      const previa = editando ? lista.find(x => x.uid === editando) : null;
      const tarea = {
        ...(previa || {}),
        uid: previa ? previa.uid : nuevoUid(),         // identificador único: evita duplicados
        titulo: datos.get("titulo").trim(),
        descripcion: datos.get("descripcion").trim(),
        fechaLimite: datos.get("fechaLimite"),
        estado: datos.get("estado"),
        creadoEn: previa ? previa.creadoEn : ahora,
        actualizadoEn: ahora,
        sync: "pendiente",                              // cambio pendiente de enviar
        detalle: null
      };
      if (ubicacion) tarea.ubicacion = ubicacion; else delete tarea.ubicacion; // la ubicación es opcional
      const quiereAviso = $("tarea-aviso").checked;

      await Almacen.guardarTarea(tarea);                // 1) siempre primero en el dispositivo
      editando = null;
      await refrescar();
      location.hash = "tareas";
      pedirBackgroundSync();

      let enviada = false;
      if (navigator.onLine) {                           // 2) enviar de inmediato si hay conexión
        const r = await sincronizar({ origen: "guardar" });
        enviada = !r.sinConexion && !r.fallidos;
      }
      if (!enviada) mostrarAviso("Tarea guardada en este dispositivo. Se enviará al recuperar la conexión.");
      if (quiereAviso) {                                // 3) aviso local con permiso del usuario
        if (await asegurarPermiso()) {
          notificar(previa ? "Tarea actualizada" : "Tarea registrada",
            `"${tarea.titulo}" · vence ${formatoFecha(tarea.fechaLimite)}${enviada ? "" : " · pendiente de envío"}`,
            "./index.html#tareas", "consulta-tareas");
        } else {
          mostrarAviso("La tarea se guardó, pero las notificaciones están desactivadas.");
        }
      }
    } catch (error) {
      console.error("[PWA] No se pudo guardar la tarea:", error);
      mostrarAviso("No se pudo guardar la tarea en el dispositivo.");
    } finally {
      boton.disabled = false;
    }
  }

  // ---------- Acciones de cada tarjeta ----------
  async function accionTarjeta(e) {
    const boton = e.target.closest("[data-accion]");
    if (!boton) return;
    const uid = boton.closest(".tarea").dataset.uid;
    const t = lista.find(x => x.uid === uid);
    if (!t) return;
    if (boton.dataset.accion === "editar") return abrirFormulario(uid);
    if (boton.dataset.accion === "ver") {
      const detalle = boton.closest(".tarea").querySelector(".detalle-tarea");
      detalle.hidden = !detalle.hidden;
      boton.textContent = detalle.hidden ? "Ver detalle" : "Ocultar detalle";
      // Al consultar una tarea pendiente se muestra un aviso local (si el permiso está concedido)
      if (!detalle.hidden && t.estado === "pendiente") {
        if (!("Notification" in window) || Notification.permission !== "granted") {
          mostrarAviso(`Pendiente: ${vencimiento(t).texto.toLowerCase()}. Activa las notificaciones en Avisos para recibir recordatorios.`);
        } else {
          notificar("Tarea pendiente", `${t.titulo} · ${vencimiento(t).texto.toLowerCase()}`, "./index.html#tareas", "consulta-tareas");
        }
      }
      return;
    }
    if (boton.dataset.accion === "completar") {
      await Almacen.guardarTarea({ ...t, estado: t.estado === "completada" ? "pendiente" : "completada",
        actualizadoEn: new Date().toISOString(), sync: "pendiente", detalle: null });
      await refrescar();
      pedirBackgroundSync();
      if (navigator.onLine) sincronizar({ origen: "guardar" });
    }
  }

  // ---------- Geolocalización de la tarea ----------
  async function usarUbicacion() {
    const boton = $("btn-tarea-ubicacion");
    boton.disabled = true;
    mostrarUbicacion("Solicitando ubicación… acepta el permiso del navegador.");
    try {
      ubicacion = await Ubicacion.obtener();
      mostrarUbicacion(`Ubicación capturada: ${ubicacion.lat}, ${ubicacion.lon} (precisión ±${ubicacion.precision} m).`);
      $("btn-quitar-tarea-ubicacion").hidden = false;
    } catch (error) {
      ubicacion = null; // el usuario puede guardar la tarea sin ubicación
      mostrarUbicacion(`${error.message} Puedes guardar la tarea sin ubicación.`);
    } finally {
      boton.disabled = false;
      if (typeof actualizarPermisos === "function") actualizarPermisos();
    }
  }

  // ---------- Montaje de eventos (lo llama app.js al iniciar) ----------
  function montar() {
    $("form-tarea").addEventListener("submit", guardarFormulario);
    $("btn-nueva-tarea").addEventListener("click", () => abrirFormulario(null));
    $("btn-cancelar-tarea").addEventListener("click", () => { editando = null; location.hash = "tareas"; });
    $("lista-tareas").addEventListener("click", accionTarjeta);
    $("filtro-tareas").addEventListener("change", e => { filtro = e.target.value; pintar(); });
    $("btn-tarea-ubicacion").addEventListener("click", usarUbicacion);
    $("btn-quitar-tarea-ubicacion").addEventListener("click", () => {
      ubicacion = null;
      mostrarUbicacion("Ubicación descartada. La tarea se guardará sin ubicación.");
      $("btn-quitar-tarea-ubicacion").hidden = true;
    });
  }

  global.Tareas = { montar, cargar, descargarRemotas, contarSync, pintarEstado, avisarVencimientos };
})(window);
