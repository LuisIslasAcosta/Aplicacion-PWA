// ===== Service Worker - Consulta Académica PWA (v3, Actividad 10) =====
importScripts("db.js", "sync.js");

const VERSION = "v5";
const CACHE_SHELL = `consulta-shell-${VERSION}`;
const CACHE_DATOS = `consulta-datos-${VERSION}`;

// App shell: lo mínimo para abrir la app sin conexión
const RECURSOS_SHELL = [
  "./",
  "./index.html",
  "./style.css",
  "./db.js",
  "./sync.js",
  "./ubicacion.js",
  "./app.js",
  "./manifest.json",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
  "./data/materias.json"
];

// INSTALACIÓN: se precachea el app shell. NO se llama a skipWaiting() aquí: si ya había una
// versión anterior, la nueva queda "en espera" hasta que el usuario acepte actualizar
// (mensaje SKIP_WAITING desde la página), así no se cambia la app a mitad de un registro.
self.addEventListener("install", evento => {
  console.log("[SW] Instalando", VERSION);
  evento.waitUntil(
    caches.open(CACHE_SHELL).then(cache => cache.addAll(RECURSOS_SHELL))
  );
});

// ACTUALIZACIÓN: la página pide activar la versión en espera
self.addEventListener("message", evento => {
  if (evento.data && evento.data.tipo === "SKIP_WAITING") self.skipWaiting();
});

// ACTIVACIÓN: se borran las cachés de versiones anteriores y se toma el control de las pestañas
self.addEventListener("activate", evento => {
  console.log("[SW] Activando", VERSION);
  evento.waitUntil(
    caches.keys()
      .then(claves => Promise.all(
        claves.filter(c => c !== CACHE_SHELL && c !== CACHE_DATOS).map(c => caches.delete(c))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", evento => {
  const peticion = evento.request;
  if (peticion.method !== "GET") return; // los POST (sincronización) van directo a la red
  const url = new URL(peticion.url);
  if (url.origin !== location.origin) return;

  // Sondeo de conectividad: nunca desde caché
  if (url.pathname.endsWith("/api/health")) return;

  // Datos (API y JSON): red primero, caché como respaldo sin conexión
  if (url.pathname.includes("/api/") || (url.pathname.endsWith(".json") && url.pathname.includes("/data/"))) {
    evento.respondWith(
      fetch(peticion)
        .then(resp => {
          if (resp.ok) {
            const copia = resp.clone();
            caches.open(CACHE_DATOS).then(c => c.put(peticion, copia));
          }
          return resp;
        })
        .catch(() => caches.match(peticion).then(r => {
          if (!r) return Response.error();
          // Se marca la respuesta para que la app sepa que viene de la caché y no del servidor
          const cabeceras = new Headers(r.headers);
          cabeceras.set("X-Desde-Cache", "1");
          return new Response(r.body, { status: r.status, statusText: r.statusText, headers: cabeceras });
        }))
    );
    return;
  }

  // Navegación: devolver el shell si no hay red
  if (peticion.mode === "navigate") {
    evento.respondWith(
      caches.match(peticion, { ignoreSearch: true })
        .then(r => r || fetch(peticion))
        .catch(() => caches.match("./index.html"))
    );
    return;
  }

  // Recursos estáticos: caché primero
  evento.respondWith(
    caches.match(peticion).then(enCache => enCache || fetch(peticion))
  );
});

// Background Sync: reenvía la cola aunque la página esté cerrada (Chromium)
self.addEventListener("sync", evento => {
  if (evento.tag !== "sync-materias") return;
  evento.waitUntil(
    self.Sync.sincronizar().then(async resultado => {
      const ventanas = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
      ventanas.forEach(v => v.postMessage({ tipo: "sync-terminada", resultado }));
      // Si nadie está viendo la app, se avisa con una notificación (solo con permiso concedido)
      const visible = ventanas.some(v => v.visibilityState === "visible");
      const total = (resultado.enviados || 0) + (resultado.duplicados || 0);
      if (total && !visible && self.Notification && Notification.permission === "granted") {
        await self.registration.showNotification("Materias sincronizadas", {
          body: `Se enviaron ${total} materia(s) al servidor.`,
          icon: "icons/icon-192.png", badge: "icons/icon-192.png", tag: "consulta-sync",
          data: { url: "./index.html#materias" }
        });
      }
      if (resultado.sinConexion || resultado.fallidos) throw new Error("reintentar"); // el navegador reprograma
    })
  );
});

self.addEventListener("notificationclick", evento => {
  evento.notification.close();
  const destino = (evento.notification.data && evento.notification.data.url) || "./index.html";
  evento.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(ventanas => {
      for (const v of ventanas) {
        if ("focus" in v) return v.focus();
      }
      return self.clients.openWindow(destino);
    })
  );
});
