"""Pruebas end-to-end de la PWA (Actividad 08) con Playwright + Chromium.

Uso:  python3 tests/e2e.py
Genera: docs/capturas/*.png  y  tests/resultados/resultados.md|json
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parent.parent
CAPTURAS = RAIZ / "docs" / "capturas"
RESULTADOS = RAIZ / "tests" / "resultados"
PUERTO = int(os.environ.get("PORT", 5057))
BASE = f"http://127.0.0.1:{PUERTO}"
CAPTURAS.mkdir(parents=True, exist_ok=True)
RESULTADOS.mkdir(parents=True, exist_ok=True)

resultados = []


def prueba(id_, descripcion, condicion, detalle=""):
    estado = "PASA" if condicion else "FALLA"
    resultados.append({"id": id_, "descripcion": descripcion, "estado": estado, "detalle": detalle})
    print(f"[{estado}] {id_} {descripcion} {('- ' + detalle) if detalle else ''}")


def api(ruta, datos=None):
    req = urllib.request.Request(BASE + ruta, method="POST" if datos is not None else "GET",
                                 data=json.dumps(datos).encode() if datos is not None else None,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def registradas():
    return [m for m in api("/api/materias")[1] if not m["uid"].startswith("base-")]


def llenar_formulario(page, nombre, clave):
    page.goto(f"{BASE}/#agregar")
    page.fill("[name=nombre]", nombre)
    page.fill("[name=clave]", clave)
    page.fill("[name=semestre]", "6")
    page.fill("[name=docente]", "Ing. Prueba Automática")
    page.fill("[name=horario]", "Vie 9:00–11:00")
    page.fill("[name=salon]", "Aula 7")
    page.fill("[name=creditos]", "4")
    page.fill("[name=temas]", "Tema A, Tema B")
    page.fill("[name=autor]", "Integrante QA")


def pendientes_ui(page):
    return page.evaluate("document.getElementById('badge-pendientes').hidden ? 0 : Number(document.getElementById('badge-pendientes').textContent)")


def pendientes_idb(page):
    return page.evaluate("Almacen.pendientes().then(l => l.length)")


# ---------- servidor temporal ----------
db_tmp = Path(tempfile.mkdtemp()) / "db.json"
servidor = None


def arrancar_servidor():
    global servidor
    servidor = subprocess.Popen([sys.executable, str(RAIZ / "server" / "app.py")],
                                env={**os.environ, "PORT": str(PUERTO), "MATERIAS_DB": str(db_tmp)},
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        try:
            api("/api/health")
            return
        except Exception:
            time.sleep(0.2)
    raise RuntimeError("El servidor no arrancó")


def detener_servidor():
    global servidor
    if servidor:
        servidor.terminate()
        servidor.wait()
        servidor = None


def sin_red(contexto, activo):
    """Sin conexión REAL: apaga el servidor (las peticiones del Service Worker no
    obedecen a set_offline de Playwright) y emula offline en el navegador."""
    if activo:
        contexto.set_offline(True)
        detener_servidor()
    else:
        arrancar_servidor()
        contexto.set_offline(False)


try:
    arrancar_servidor()

    with sync_playwright() as pw:
        navegador = pw.chromium.launch()
        contexto = navegador.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2,
                                         locale="es-MX", service_workers="allow")
        page = contexto.new_page()
        errores_consola = []
        page.on("pageerror", lambda e: errores_consola.append(str(e)))

        # ===== P1. Splash y Home =====
        page.goto(BASE, wait_until="commit")
        page.wait_for_selector("#splash:not([hidden])", timeout=3000)
        time.sleep(0.5)
        splash_visible = page.is_visible("#splash") and "Consulta Académica" in page.inner_text("#splash")
        page.screenshot(path=str(CAPTURAS / "01-splash.png"))
        page.wait_for_selector("#splash", state="hidden", timeout=8000)
        page.wait_for_selector("#vista-inicio:not([hidden])")
        prueba("P1", "Se presenta la Splash Screen y luego la Home Screen", splash_visible and page.is_visible("#vista-inicio"))
        page.wait_for_function("navigator.serviceWorker.controller !== null", timeout=8000)
        page.screenshot(path=str(CAPTURAS / "02-home-online.png"))

        # ===== P2. Datos en la interfaz =====
        page.goto(f"{BASE}/#materias")
        page.wait_for_selector(".tarjeta")
        n = page.locator(".tarjeta").count()
        page.goto(f"{BASE}/#inicio")
        fuente = page.inner_text("#st-fuente")
        page.goto(f"{BASE}/#materias")
        page.wait_for_selector(".tarjeta")
        prueba("P2", "Los datos (catálogo del servidor) se muestran en la interfaz", n == 4 and fuente == "Servidor",
               f"{n} tarjetas; fuente={fuente}")
        page.screenshot(path=str(CAPTURAS / "03-materias-online.png"))

        # ===== P3. Caché: abrir sin conexión =====
        cache_ok = page.evaluate("caches.keys().then(k => k.length >= 1)")
        sin_red(contexto, True)
        page.reload()
        page.wait_for_selector("#splash", state="hidden", timeout=8000)
        page.wait_for_selector(".tarjeta", timeout=5000)
        n_off = page.locator(".tarjeta").count()
        estado_red = page.inner_text("#estado-red")
        page.goto(f"{BASE}/#inicio")
        fuente_off = page.inner_text("#st-fuente")
        prueba("P3", "Con la caché la app abre sin conexión y muestra los datos guardados",
               cache_ok and n_off == 4 and estado_red == "Sin conexión" and fuente_off == "Caché local",
               f"{n_off} tarjetas offline; red='{estado_red}'; fuente='{fuente_off}'")
        page.screenshot(path=str(CAPTURAS / "04-home-offline.png"))

        # ===== P4. Registro sin conexión + persistencia tras recargar =====
        llenar_formulario(page, "Seguridad Informática", "ISC-401")
        page.click("#btn-guardar")
        page.wait_for_selector(".tarjeta[data-estado=pendiente]")
        pend_antes = pendientes_ui(page)
        page.locator(".tarjeta[data-estado=pendiente]").scroll_into_view_if_needed()
        page.screenshot(path=str(CAPTURAS / "05-registro-offline-pendiente.png"))
        page.reload()
        page.wait_for_selector("#splash", state="hidden", timeout=8000)
        page.goto(f"{BASE}/#materias")
        page.wait_for_selector(".tarjeta")
        persiste = page.locator(".tarjeta[data-estado=pendiente]").count() == 1
        prueba("P4", "El registro hecho sin conexión queda como pendiente y persiste tras recargar",
               pend_antes == 1 and persiste and pendientes_idb(page) == 1,
               f"badge={pend_antes}; servidor apagado, aún sin registros")

        # ===== P5. Sincronización automática al recuperar conexión =====
        sin_red(contexto, False)
        automatica = False
        try:
            page.wait_for_function("document.getElementById('badge-pendientes').hidden", timeout=15000)
            automatica = True
        except Exception:
            pass
        if not automatica:  # respaldo: botón manual
            page.goto(f"{BASE}/#inicio")
            page.click("#btn-sync")
            page.wait_for_function("document.getElementById('badge-pendientes').hidden", timeout=8000)
        en_servidor = registradas()
        prueba("P5", "Los pendientes se envían al servidor al recuperar la conectividad",
               len(en_servidor) == 1 and en_servidor[0]["clave"] == "ISC-401" and pendientes_idb(page) == 0,
               f"{'automática (evento online/Background Sync)' if automatica else 'manual (botón)'}; servidor={len(en_servidor)}")
        page.goto(f"{BASE}/#materias")
        page.wait_for_selector(".tarjeta[data-uid]")
        page.locator(".tarjeta[data-uid]").last.scroll_into_view_if_needed()
        page.screenshot(path=str(CAPTURAS / "06-sincronizado.png"))

        # ===== P6. Sin duplicados en reintentos =====
        # (a) Respuesta perdida: el servidor procesa el POST pero el cliente nunca recibe la respuesta
        llenar_formulario(page, "Inteligencia Artificial", "ISC-402")

        def perder_respuesta(route):
            if route.request.method == "POST":
                route.fetch()      # el servidor SÍ crea el registro...
                route.abort()      # ...pero el cliente ve un fallo de red
            else:
                route.continue_()
        page.route("**/api/materias", perder_respuesta)
        page.click("#btn-guardar")
        page.wait_for_selector(".tarjeta[data-estado=pendiente]")
        tras_perdida_cliente = pendientes_idb(page)
        tras_perdida_servidor = len([m for m in registradas() if m["clave"] == "ISC-402"])
        page.unroute("**/api/materias")
        # (b) Reintento manual: mismo uid -> el servidor responde duplicado
        page.goto(f"{BASE}/#inicio")
        page.click("#btn-sync")
        page.wait_for_function("document.getElementById('badge-pendientes').hidden", timeout=8000)
        despues = [m for m in registradas() if m["clave"] == "ISC-402"]
        # (c) Reintentos simultáneos desde la página con el mismo uid
        uid = despues[0]["uid"]
        paralelo = page.evaluate("""async (uid) => {
            const m = await Almacen.obtener(uid);
            const { estado, detalle, ...carga } = m;
            const r = await Promise.all([1,2,3,4,5].map(() => fetch('api/materias', {method:'POST',
                headers:{'Content-Type':'application/json'}, body: JSON.stringify(carga)}).then(x => x.status)));
            return r;
        }""", uid)
        total_final = len([m for m in registradas() if m["clave"] == "ISC-402"])
        todos_uid = [m["uid"] for m in registradas()]
        prueba("P6", "No se duplican registros durante los reintentos de sincronización",
               tras_perdida_cliente == 1 and tras_perdida_servidor == 1 and len(despues) == 1
               and total_final == 1 and len(todos_uid) == len(set(todos_uid)) == 2,
               f"respuesta perdida -> cliente pendiente={tras_perdida_cliente}, servidor={tras_perdida_servidor}; "
               f"tras reintento servidor={len(despues)}; 5 POST paralelos {paralelo} -> servidor={total_final}")
        page.goto(f"{BASE}/#materias")
        page.wait_for_selector(".tarjeta")

        # ===== P7. Validación del servidor =====
        codigo, cuerpo = api("/api/materias", {"uid": "x", "nombre": "Mala"})
        prueba("P7", "El servidor rechaza datos inválidos (HTTP 400) sin crear registros",
               codigo == 400 and len(registradas()) == 2, f"HTTP {codigo}: {cuerpo.get('error')}")

        # ===== P8. Persistencia total tras reiniciar (datos en IDB) =====
        sin_red(contexto, True)
        page.reload()
        page.wait_for_selector("#splash", state="hidden", timeout=8000)
        page.goto(f"{BASE}/#materias")
        page.wait_for_selector(".tarjeta")
        n_final = page.locator(".tarjeta").count()
        prueba("P8", "Datos sincronizados y locales disponibles sin conexión tras recargar", n_final == 6, f"{n_final} tarjetas")
        sin_red(contexto, False)

        # ===== P10. Servidor estático sin API (p. ej. Live Server): no se marca como rechazado =====
        estatico = subprocess.Popen([sys.executable, "-m", "http.server", "5058", "--bind", "127.0.0.1", "--directory", str(RAIZ / "public")],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            time.sleep(1)
            ctx2 = navegador.new_context(viewport={"width": 390, "height": 844}, locale="es-MX")
            p2 = ctx2.new_page()
            p2.goto("http://127.0.0.1:5058/")
            p2.wait_for_selector("#splash", state="hidden", timeout=8000)
            p2.goto("http://127.0.0.1:5058/#agregar")
            for campo, valor in (("nombre", "Sin API"), ("clave", "SIN-1"), ("docente", "X"), ("horario", "Y"),
                                 ("salon", "Z"), ("temas", "a"), ("autor", "QA")):
                p2.fill(f"[name={campo}]", valor)
            p2.click("#btn-guardar")
            p2.wait_for_selector(".tarjeta[data-uid]")
            time.sleep(1.5)
            estados = p2.evaluate("Almacen.todas().then(l => l.filter(m => m.clave === 'SIN-1').map(m => m.estado))")
            prueba("P10", "En un servidor sin API (404/405/501) el registro sigue pendiente y no se marca como rechazado",
                   estados == ["pendiente"], f"estados={estados}")
            ctx2.close()
        finally:
            estatico.terminate()

        prueba("P9", "Sin errores de JavaScript no controlados durante las pruebas", not errores_consola, "; ".join(errores_consola))
        navegador.close()
finally:
    detener_servidor()

(RESULTADOS / "resultados.json").write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")
lineas = ["| ID | Prueba | Resultado | Detalle |", "|---|---|---|---|"]
for r in resultados:
    lineas.append(f"| {r['id']} | {r['descripcion']} | {r['estado']} | {r['detalle']} |")
(RESULTADOS / "resultados.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")
fallas = [r for r in resultados if r["estado"] != "PASA"]
print(f"\n{len(resultados) - len(fallas)}/{len(resultados)} pruebas pasan")
sys.exit(1 if fallas else 0)
