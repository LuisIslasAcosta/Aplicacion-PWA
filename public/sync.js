// ===== Sincronización de la cola de salida con el servidor =====
// Compartido por la página y el Service Worker (evento "sync").
//
// Evita duplicados con tres mecanismos:
//  1) Cada registro nace con un `uid` (UUID) generado en el cliente.
//  2) El servidor es idempotente: si ya existe ese uid responde 200 y no crea otro.
//  3) Solo se marca "sincronizado" tras recibir respuesta; si se pierde la respuesta,
//     el reintento envía el mismo uid y el servidor lo reconoce.
// Un candado (enCurso) impide dos sincronizaciones simultáneas dentro del mismo contexto.

(function (global) {
  const ENDPOINT = "api/materias"; // relativo: funciona en cualquier subruta
  let enCurso = null;

  function cargaUtil(m) {
    const { estado, detalle, ...resto } = m;
    return resto;
  }

  async function ejecutar(opciones) {
    const resultado = { enviados: 0, duplicados: 0, rechazados: 0, fallidos: 0, sinConexion: false, pendientesRestantes: 0 };
    const lista = await global.Almacen.pendientes(!!opciones.incluirErrores);

    for (const materia of lista) {
      let resp;
      try {
        resp = await fetch(ENDPOINT, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(cargaUtil(materia))
        });
      } catch {
        resultado.sinConexion = true; // sin red o servidor caído: se conserva en la cola
        break;
      }

      if (resp.ok) {
        const cuerpo = await resp.json().catch(() => ({}));
        await global.Almacen.guardar({ ...materia, ...(cuerpo.materia || {}), estado: "sincronizado", detalle: null });
        cuerpo.duplicado ? resultado.duplicados++ : resultado.enviados++;
      } else if ([404, 405, 501].includes(resp.status)) {
        // No hay API en ese servidor (hosting estático, Live Server, etc.): no es culpa del registro.
        // Se conserva (o se devuelve) a la cola como pendiente y se reintentará.
        if (materia.estado === "error") await global.Almacen.guardar({ ...materia, estado: "pendiente", detalle: null });
        resultado.sinApi = true;
        resultado.sinConexion = true;
        break;
      } else if (resp.status >= 400 && resp.status < 500) {
        const cuerpo = await resp.json().catch(() => ({}));
        await global.Almacen.guardar({ ...materia, estado: "error", detalle: cuerpo.error || `HTTP ${resp.status}` });
        resultado.rechazados++;
      } else {
        resultado.fallidos++; // 5xx: reintentar más tarde
        break;
      }
    }

    if (resultado.enviados || resultado.duplicados) {
      await global.Almacen.escribirMeta("ultimaSync", new Date().toISOString());
    }
    resultado.pendientesRestantes = (await global.Almacen.pendientes()).length;
    return resultado;
  }

  function sincronizar(opciones = {}) {
    if (enCurso) return enCurso;
    enCurso = ejecutar(opciones).finally(() => { enCurso = null; });
    return enCurso;
  }

  global.Sync = { sincronizar };
})(self);
