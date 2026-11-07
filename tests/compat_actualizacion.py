"""Actividad 14 - Pruebas de compatibilidad y de actualización de la PWA.

Uso:  python3 tests/compat_actualizacion.py
Requiere: pip install playwright flask  y  playwright install chromium

1) COMPATIBILIDAD: abre las pantallas principales en dos navegadores (Chromium de Playwright y, si está
   instalado, Google Chrome) y en dos tamaños (escritorio y móvil emulado). Si hay Firefox/WebKit instalados
   (playwright install firefox webkit) también se incluyen.
2) ACTUALIZACIÓN: publica una "versión 2" (texto de bienvenida distinto + nueva VERSION del Service Worker)
   sobre una copia del proyecto, comprueba que la versión nueva queda en espera, que se muestra el aviso,
   que al aceptar se activa, que las cachés viejas se borran y que los datos locales (IndexedDB) se conservan.

Genera: docs/capturas14/*.png  y  tests/resultados/compat_actualizacion.md
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parent.parent
CAP = RAIZ / "docs" / "capturas14"
RES = RAIZ / "tests" / "resultados"
CAP.mkdir(parents=True, exist_ok=True)
RES.mkdir(parents=True, exist_ok=True)
PUERTO = int(os.environ.get("PORT", 5071))
BASE = f"http://127.0.0.1:{PUERTO}"
filas = []


def registrar(id_, desc, ok, detalle=""):
    filas.append((id_, desc, "PASA" if ok else "FALLA", detalle))
    print(f"[{'PASA' if ok else 'FALLA'}] {id_} {desc} {('- ' + detalle) if detalle else ''}")


def servir(carpeta):
    """Arranca el servidor Flask usando la carpeta del proyecto indicada."""
    datos = Path(tempfile.mkdtemp())
    p = subprocess.Popen([sys.executable, str(carpeta / "server" / "app.py")],
                         env={**os.environ, "PORT": str(PUERTO), "MATERIAS_DB": str(datos / "db.json"),
                              "TAREAS_DB": str(datos / "tareas.json")},
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        try:
            urllib.request.urlopen(BASE + "/api/health", timeout=1)
            return p
        except Exception:
            time.sleep(0.2)
    raise RuntimeError("El servidor no arrancó")


def esperar_app(page):
    page.wait_for_selector("#splash", state="hidden", timeout=10000)
    page.wait_for_function("navigator.serviceWorker.controller !== null", timeout=10000)


# =========================== 1. COMPATIBILIDAD ===========================
servidor = servir(RAIZ)
try:
    with sync_playwright() as pw:
        navegadores = [("Chromium", lambda: pw.chromium.launch(channel="chromium"))]
        try:
            b = pw.chromium.launch(channel="chrome"); b.close()
            navegadores.append(("Google Chrome", lambda: pw.chromium.launch(channel="chrome")))
        except Exception:
            pass
        for nombre, motor in (("Firefox", pw.firefox), ("WebKit (Safari)", pw.webkit)):
            try:
                b = motor.launch(); b.close()
                navegadores.append((nombre, lambda m=motor: m.launch()))
            except Exception:
                pass
        tamanos = [("escritorio", {"width": 1280, "height": 800}), ("móvil", {"width": 390, "height": 844})]
        pantallas = [("inicio", "#vista-inicio"), ("materias", "#vista-materias"), ("agregar", "#vista-agregar"),
                     ("tareas", "#vista-tareas")]
        for nombre, abrir in navegadores:
            nav = abrir()
            for tam_nombre, vp in tamanos:
                ctx = nav.new_context(viewport=vp, locale="es-MX", device_scale_factor=1)
                page = ctx.new_page()
                errores = []
                page.on("pageerror", lambda e: errores.append(str(e)))
                page.goto(BASE)
                esperar_app(page)
                visibles, desborde = [], False
                for pant, sel in pantallas:
                    page.goto(f"{BASE}/#{pant}")
                    page.wait_for_selector(sel + ":not([hidden])", timeout=5000)
                    visibles.append(page.is_visible(sel))
                    # desbordamiento horizontal = la pantalla no se adapta al ancho
                    if page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth + 1"):
                        desborde = True
                    page.screenshot(path=str(CAP / f"compat-{nombre.split()[0].lower()}-{tam_nombre}-{pant}.png"))
                registrar(f"C-{nombre.split()[0]}-{tam_nombre}",
                          f"{nombre} ({tam_nombre}): las 4 pantallas se muestran, sin desbordamiento horizontal y sin errores de JavaScript",
                          all(visibles) and not desborde and not errores,
                          f"pantallas visibles={sum(visibles)}/4; desborde={desborde}; errores={errores}")
                ctx.close()
            nav.close()
finally:
    servidor.terminate()

# =========================== 2. ACTUALIZACIÓN ===========================
copia = Path(tempfile.mkdtemp()) / "proyecto"
shutil.copytree(RAIZ, copia, ignore=shutil.ignore_patterns("docs", "tests", "lh", ".git", "__pycache__", "*.json.bak", "db.json", "tareas.json"))
sw_ruta = copia / "public" / "sw.js"
version_actual = re.search(r'const VERSION = "([^"]+)"', sw_ruta.read_text()).group(1)
servidor = servir(copia)
try:
    with sync_playwright() as pw:
        nav = pw.chromium.launch(channel="chromium")
        ctx = nav.new_context(viewport={"width": 390, "height": 844}, locale="es-MX", service_workers="allow")
        page = ctx.new_page()
        page.goto(BASE)
        esperar_app(page)
        page.reload()  # segunda visita: la página ya nace controlada por el Service Worker (caso real de actualización)
        esperar_app(page)
        texto_v1 = page.inner_text("#vista-inicio h2")
        cache_v1 = page.evaluate("caches.keys()")
        # Se registra un dato local (materia) para comprobar que sobrevive a la actualización
        page.goto(f"{BASE}/#agregar")
        for campo, valor in (("nombre", "Materia antes de actualizar"), ("clave", "UPD-101"), ("semestre", "6"),
                             ("docente", "Ing. Update"), ("horario", "Lun 9:00–11:00"), ("salon", "Aula 1"),
                             ("creditos", "4"), ("temas", "A, B"), ("autor", "QA")):
            page.fill(f"[name={campo}]", valor)
        page.click("#btn-guardar")
        page.wait_for_selector(".tarjeta[data-uid]")
        page.wait_for_function("document.getElementById('badge-pendientes').hidden", timeout=10000)
        antes = page.evaluate("Almacen.todas().then(l => l.filter(m => m.clave === 'UPD-101').length)")
        page.screenshot(path=str(CAP / "act-01-version1.png"))
        registrar("U1", f"Versión 1 instalada: Service Worker activo y caché «consulta-shell-{version_actual}»",
                  any(version_actual in k for k in cache_v1), f"cachés={cache_v1}; texto='{texto_v1}'")

        # ----- Se publica la versión 2: cambia el texto de bienvenida y la VERSION del Service Worker -----
        nueva = f"{version_actual}-actualizada"
        sw_ruta.write_text(sw_ruta.read_text().replace(f'const VERSION = "{version_actual}"', f'const VERSION = "{nueva}"'))
        idx = copia / "public" / "index.html"
        idx.write_text(idx.read_text().replace("<h2>Bienvenido</h2>", "<h2>Bienvenido (versión 2)</h2>"))

        # Se busca la actualización (equivale a volver a abrir la app o a «Update» en DevTools)
        page.goto(f"{BASE}/#inicio")
        page.evaluate("navigator.serviceWorker.getRegistration().then(r => r.update())")
        page.wait_for_selector("#banner-actualizacion:not([hidden])", timeout=10000)
        espera = page.evaluate("navigator.serviceWorker.getRegistration().then(r => !!r.waiting)")
        texto_aun_v1 = page.inner_text("#vista-inicio h2")
        page.wait_for_selector("#toast", state="hidden", timeout=8000)  # que el aviso de sincronización no tape el banner
        page.screenshot(path=str(CAP / "act-02-aviso-nueva-version.png"))
        registrar("U2", "La versión nueva se instala en segundo plano, queda en espera y se muestra el aviso «Actualizar»",
                  espera and texto_aun_v1 == texto_v1, f"waiting={espera}; texto sigue='{texto_aun_v1}'")

        # ----- El usuario acepta la actualización -----
        with page.expect_navigation(timeout=15000):
            page.click("#btn-actualizar")
        esperar_app(page)
        page.wait_for_selector("#vista-inicio:not([hidden])")
        texto_v2 = page.inner_text("#vista-inicio h2")
        cache_v2 = page.evaluate("caches.keys()")
        page.screenshot(path=str(CAP / "act-03-version2.png"))
        registrar("U3", "Al aceptar, el Service Worker nuevo se activa y la app muestra el contenido de la versión 2",
                  "versión 2" in texto_v2, f"texto='{texto_v2}'")
        registrar("U4", "Se eliminan las cachés de la versión anterior y queda solo la nueva",
                  all(nueva in k for k in cache_v2) and not any(k.endswith(f"-{version_actual}") for k in cache_v2),
                  f"cachés={cache_v2}")
        despues = page.evaluate("Almacen.todas().then(l => l.filter(m => m.clave === 'UPD-101').length)")
        page.goto(f"{BASE}/#materias")
        page.wait_for_selector(".tarjeta")
        visible = "Materia antes de actualizar" in page.inner_text("#lista-materias") if page.query_selector("#lista-materias") else \
            "Materia antes de actualizar" in page.inner_text("body")
        page.screenshot(path=str(CAP / "act-04-datos-conservados.png"))
        registrar("U5", "Los datos locales (IndexedDB) se conservan después de actualizar",
                  antes == 1 and despues == 1 and visible, f"antes={antes}; después={despues}; visible en la lista={visible}")
        nav.close()
finally:
    servidor.terminate()

total, ok = len(filas), sum(1 for f in filas if f[2] == "PASA")
(RES / "compat_actualizacion.md").write_text(
    "| ID | Prueba | Resultado | Detalle |\n|---|---|---|---|\n" +
    "\n".join(f"| {a} | {b} | {c} | {d} |" for a, b, c, d in filas) + f"\n\n{ok}/{total} pruebas pasan\n", encoding="utf-8")
print(f"\n{ok}/{total} pruebas pasan")
sys.exit(0 if ok == total else 1)
