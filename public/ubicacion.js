// ===== Geolocalización (característica del dispositivo) =====
// API: navigator.geolocation.getCurrentPosition() + Permissions API (estado del permiso).
// Requiere contexto seguro (HTTPS o localhost). El permiso se pide SOLO cuando el usuario
// pulsa "Usar mi ubicación"; antes de eso la pantalla le explica para qué se usa.
// Funciona sin internet: el GPS/Wi-Fi del dispositivo no depende de la red de datos
// (en escritorio, algunos navegadores sí usan un servicio de red y pueden fallar sin conexión).

(function (global) {
  const OPCIONES = { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 };

  const MENSAJES = {
    1: "Permiso denegado. Actívalo en la configuración del sitio (candado junto a la dirección) y vuelve a intentar.",
    2: "No se pudo determinar la ubicación (señal GPS/red no disponible).",
    3: "Se agotó el tiempo de espera (10 s). Intenta de nuevo en un lugar con mejor señal."
  };

  function soportada() {
    return "geolocation" in navigator;
  }

  // "granted" | "denied" | "prompt" | "desconocido" | "no-soportada" | "inseguro"
  async function estadoPermiso() {
    if (!soportada()) return "no-soportada";
    if (!window.isSecureContext) return "inseguro";
    try {
      const r = await navigator.permissions.query({ name: "geolocation" });
      return r.state;
    } catch {
      return "desconocido"; // p. ej. Safari antiguo: no expone el estado
    }
  }

  // Devuelve { lat, lon, precision, tomadoEn }. Lanza Error con mensaje listo para mostrar.
  function obtener() {
    return new Promise((resolver, rechazar) => {
      if (!soportada()) return rechazar(new Error("Este navegador no soporta geolocalización."));
      if (!window.isSecureContext) return rechazar(new Error("La geolocalización requiere HTTPS o localhost."));
      navigator.geolocation.getCurrentPosition(
        pos => resolver({
          lat: Number(pos.coords.latitude.toFixed(6)),
          lon: Number(pos.coords.longitude.toFixed(6)),
          precision: Math.round(pos.coords.accuracy),
          tomadoEn: new Date(pos.timestamp || Date.now()).toISOString()
        }),
        err => rechazar(new Error(MENSAJES[err.code] || "Error de geolocalización.")),
        OPCIONES
      );
    });
  }

  function enlaceMapa(u) {
    return `https://www.openstreetmap.org/?mlat=${u.lat}&mlon=${u.lon}#map=18/${u.lat}/${u.lon}`;
  }

  global.Ubicacion = { soportada, estadoPermiso, obtener, enlaceMapa };
})(window);
