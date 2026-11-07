// ===== Sincronización de las colas de salida con el servidor =====
// Compartido por la página y el Service Worker (evento "sync").
// Sincroniza dos colas: materias (estado = "pendiente") y tareas (sync = "pendiente").
//
// Evita duplicados con tres mecanismos:
//  1) Cada registro nace con un `uid` (UUID) generado en el cliente.
//  2) El servidor es idempotente: si ya existe ese uid responde 200 y no crea otro.
//  3) Solo se marca "sincronizado" tras recibir respuesta; si se pierde la respuesta,
//     el reintento envía el mismo uid y el servidor lo reconoce.
// Un candado (enCurso) impide dos sincronizaciones simultáneas dentro del mismo contexto.
//
// Tareas editadas: el servidor aplica "gana la última edición" (campo actualizadoEn). Si el usuario
// vuelve a editar una tarea mientras se enviaba la versión anterior, se conserva su versión local
// como pendiente (no se marca sincronizada) y se envía en el siguiente turno.

(function (global) {
  let enCurso = null;

  const COLAS = {
    materias: {
      endpoint: "api/materias", clave: "materia", campo: "estado", versionado: false,
      lista: inc => global.Almacen.pendientes(inc),
      obtener: uid => global.Almacen.obtener(uid),
      guardar: m => global.Almacen.guardar(m)
    },
    tareas: {
      endpoint: "api/tareas", clave: "tarea", campo: "sync", versionado: true,
      lista: inc => global.Almacen.tareasPorSincronizar(inc),
      obtener: uid => global.Almacen.obtenerTarea(uid),
      guardar: t => global.Almacen.guardarTarea(t)
    }
  };

  function cargaUtil(registro, campo) {
    const { detalle, ...resto } = registro;
    delete resto[campo]; // el estado de sincronización es solo local
    if (campo === "estado") return resto; // materias: `estado` era el de sync
    return { ...resto, estado: registro.estado }; // tareas: `estado` sí viaja (pendiente/completada)
  }

  // Devuelve true si hay que detener el envío (sin conexión, sin API o error del servidor)
  async function enviarCola(cfg, lista, resultado) {
    for (const item of lista) {
      let resp;
      try {
        resp = await fetch(cfg.endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(cargaUtil(item, cfg.campo))
        });
      } catch {
        resultado.sinConexion = true; // sin red o servidor caído: se conserva en la cola
        return true;
      }

      if (resp.ok) {
        const cuerpo = await resp.json().catch(() => ({}));
        const remoto = cuerpo[cfg.clave] || {};
        const actual = await cfg.obtener(item.uid);
        if (cfg.versionado && actual && actual.actualizadoEn !== item.actualizadoEn) {
          resultado.enviados++; // se editó mientras se enviaba: queda pendiente la versión nueva
          continue;
        }
        const confirmado = { ...item, ...remoto, [cfg.campo]: "sincronizado", detalle: null };
        if (cfg.campo === "sync") confirmado.estado = remoto.estado || item.estado;
        await cfg.guardar(confirmado);
        cuerpo.duplicado ? resultado.duplicados++ : resultado.enviados++;
      } else if ([404, 405, 501].includes(resp.status)) {
        // No hay API en ese servidor (hosting estático, Live Server, etc.): no es culpa del registro.
        // Se conserva (o se devuelve) a la cola como pendiente y se reintentará.
        if (item[cfg.campo] === "error") await cfg.guardar({ ...item, [cfg.campo]: "pendiente", detalle: null });
        resultado.sinApi = true;
        resultado.sinConexion = true;
        return true;
      } else if (resp.status >= 400 && resp.status < 500) {
        const cuerpo = await resp.json().catch(() => ({}));
        await cfg.guardar({ ...item, [cfg.campo]: "error", detalle: cuerpo.error || `HTTP ${resp.status}` });
        resultado.rechazados++;
      } else {
        resultado.fallidos++; // 5xx: reintentar más tarde
        return true;
      }
    }
    return false;
  }

  async function ejecutar(opciones) {
    const inc = !!opciones.incluirErrores;
    const resultado = { enviados: 0, duplicados: 0, rechazados: 0, fallidos: 0, sinConexion: false, pendientesRestantes: 0 };

    const detener = await enviarCola(COLAS.materias, await COLAS.materias.lista(inc), resultado);
    if (!detener) await enviarCola(COLAS.tareas, await COLAS.tareas.lista(inc), resultado);

    if (resultado.enviados || resultado.duplicados) {
      await global.Almacen.escribirMeta("ultimaSync", new Date().toISOString());
    }
    resultado.pendientesRestantes =
      (await global.Almacen.pendientes()).length + (await global.Almacen.tareasPorSincronizar()).length;
    return resultado;
  }

  function sincronizar(opciones = {}) {
    if (enCurso) return enCurso;
    enCurso = ejecutar(opciones).finally(() => { enCurso = null; });
    return enCurso;
  }

  global.Sync = { sincronizar };
})(self);
