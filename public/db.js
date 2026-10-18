// ===== Almacenamiento local con IndexedDB =====
// Compartido por la página (window) y el Service Worker (importScripts).
// Stores:
//   materias : { uid (clave), ..., estado: "pendiente" | "sincronizado" | "error" }
//              Las materias "pendiente" forman la COLA DE SALIDA (outbox) que se
//              envía al servidor cuando hay conexión.
//   meta     : { clave, valor }  -> p. ej. ultimaSync

(function (global) {
  const DB_NOMBRE = "consulta-academica";
  const DB_VERSION = 1;
  let conexion = null;

  function abrir() {
    if (conexion) return conexion;
    conexion = new Promise((resolver, rechazar) => {
      const pet = indexedDB.open(DB_NOMBRE, DB_VERSION);
      pet.onupgradeneeded = () => {
        const db = pet.result;
        if (!db.objectStoreNames.contains("materias")) {
          const s = db.createObjectStore("materias", { keyPath: "uid" });
          s.createIndex("estado", "estado");
        }
        if (!db.objectStoreNames.contains("meta")) {
          db.createObjectStore("meta", { keyPath: "clave" });
        }
      };
      pet.onsuccess = () => resolver(pet.result);
      pet.onerror = () => { conexion = null; rechazar(pet.error); };
    });
    return conexion;
  }

  async function tx(store, modo, operacion) {
    const db = await abrir();
    return new Promise((resolver, rechazar) => {
      const t = db.transaction(store, modo);
      const resultado = operacion(t.objectStore(store));
      t.oncomplete = () => resolver(resultado && "result" in resultado ? resultado.result : undefined);
      t.onerror = () => rechazar(t.error);
      t.onabort = () => rechazar(t.error);
    });
  }

  const Almacen = {
    todas: () => tx("materias", "readonly", s => s.getAll()),
    obtener: uid => tx("materias", "readonly", s => s.get(uid)),
    guardar: materia => tx("materias", "readwrite", s => s.put(materia)),
    guardarVarias: lista => tx("materias", "readwrite", s => { lista.forEach(m => s.put(m)); }),
    async pendientes(incluirErrores = false) {
      const todas = await this.todas();
      return todas
        .filter(m => m.estado === "pendiente" || (incluirErrores && m.estado === "error"))
        .sort((a, b) => (a.creadoEn || "").localeCompare(b.creadoEn || ""));
    },
    async leerMeta(clave) {
      const r = await tx("meta", "readonly", s => s.get(clave));
      return r ? r.valor : null;
    },
    escribirMeta: (clave, valor) => tx("meta", "readwrite", s => s.put({ clave, valor }))
  };

  global.Almacen = Almacen;
})(self);
