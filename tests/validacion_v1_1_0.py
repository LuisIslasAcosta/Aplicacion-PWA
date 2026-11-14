"""Actividad 16 - Validación de la versión candidata v1.1.0 (prioridad + búsqueda de tareas).

Uso:  python3 tests/validacion_v1_1_0.py
Requiere: pip install playwright flask  y  playwright install chromium
          y que exista la etiqueta git v1.0.0 (versión publicada anterior).

Simula a un usuario real que tiene instalada la v1.0.0, con datos guardados, y recibe la v1.1.0:
  1) Se publica la v1.0.0 (tomada de la etiqueta git) y el usuario registra una materia y dos tareas.
  2) Se publica la v1.1.0 (el código actual) en la MISMA URL y con los MISMOS datos del servidor.
  3) Se comprueba la actualización del Service Worker, las cachés, la conservación de IndexedDB,
     la nueva funcionalidad y que las funciones anteriores sigan trabajando (regresión).

Genera: docs/capturas16/*.png  y  docs/capturas16/resultados-validacion.md
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
CAP = RAIZ / "docs" / "capturas16"
CAP.mkdir(parents=True, exist_ok=True)
PUERTO = int(os.environ.get("PORT", 5081))
BASE = f"http://127.0.0.1:{PUERTO}"
DATOS = Path(tempfile.mkdtemp())          # "base de datos" del servidor, compartida por ambas versiones
filas = []
errores_js = []


def registrar(id_, tipo, desc, ok, detalle=""):
    filas.append((id_, tipo, desc, "PASA" if ok else "FALLA", detalle))
    print(f"[{'PASA' if ok else 'FALLA'}] {id_} {desc} {('- ' + detalle) if detalle else ''}")


def servir(carpeta):
    p = subprocess.Popen([sys.executable, str(carpeta / "server" / "app.py")],
                         env={**os.environ, "PORT": str(PUERTO), "MATERIAS_DB": str(DATOS / "db.json"),
                              "TAREAS_DB": str(DATOS / "tareas.json")},
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(60):
        try:
            urllib.request.urlopen(BASE + "/api/health", timeout=1)
            return p
        except Exception:
            time.sleep(0.2)
    raise RuntimeError("El servidor no arrancó")


def detener(p):
    p.terminate()
    p.wait(timeout=10)


def esperar_app(page):
    page.wait_for_selector("#splash", state="hidden", timeout=10000)
    page.wait_for_function("navigator.serviceWorker.controller !== null", timeout=10000)


def nueva_tarea(page, titulo, descripcion, fecha, prioridad=None):
    page.goto(f"{BASE}/#tareas")
    page.click("#btn-nueva-tarea")
    page.fill("[name=titulo]", titulo)
    page.fill("[name=descripcion]", descripcion)
    page.fill("[name=fechaLimite]", fecha)
    if prioridad:
        page.select_option("[name=prioridad]", prioridad)
    page.uncheck("#tarea-aviso")
    page.click("#btn-guardar-tarea")
    page.wait_for_selector("#vista-tareas:not([hidden])")


def esperar(page, expresion, segundos=15):
    """Espera a que una expresión ASÍNCRONA sea verdadera.
    (wait_for_function no sirve aquí: una Promesa siempre cuenta como «verdadera».)"""
    limite = time.time() + segundos
    while time.time() < limite:
        if page.evaluate(expresion):
            return True
        time.sleep(0.25)
    raise TimeoutError(f"No se cumplió: {expresion}")


def tareas_locales(page):
    return page.evaluate("Almacen.todasTareas()")


# ---------- Código de la v1.0.0 (etiqueta git) ----------
v1 = Path(tempfile.mkdtemp()) / "v1.0.0"
v1.mkdir()
subprocess.run(f"git -C '{RAIZ}' archive v1.0.0 public server | tar -x -C '{v1}'", shell=True, check=True)

servidor = servir(v1)
with sync_playwright() as pw:
    nav = pw.chromium.launch(channel="chromium")
    ctx = nav.new_context(viewport={"width": 390, "height": 844}, locale="es-MX", service_workers="allow")
    page = ctx.new_page()
    page.on("pageerror", lambda e: errores_js.append(str(e)))
    try:
        # ===== 1. Usuario con la v1.0.0 instalada y datos guardados =====
        page.goto(BASE)
        esperar_app(page)
        page.reload()
        esperar_app(page)
        cache_v1 = page.evaluate("caches.keys()")
        page.goto(f"{BASE}/#agregar")
        for campo, valor in (("nombre", "Programación Web"), ("clave", "PWA-115"), ("semestre", "10"),
                             ("docente", "R. Vinicio Camacho"), ("horario", "Lun 9:00-11:00"), ("salon", "Lab 3"),
                             ("creditos", "5"), ("temas", "PWA, Service Worker"), ("autor", "Luis")):
            page.fill(f"[name={campo}]", valor)
        page.click("#btn-guardar")
        page.wait_for_function("document.getElementById('badge-pendientes').hidden", timeout=10000)
        nueva_tarea(page, "Práctica de Service Worker", "Entregar capturas del ciclo de vida", "2026-11-20")
        nueva_tarea(page, "Leer documentación de IndexedDB", "Capítulo de versiones", "2026-11-25")
        esperar(page, "Almacen.todasTareas().then(l => l.length === 2 && l.every(t => t.sync === 'sincronizado'))")
        antes = tareas_locales(page)
        page.screenshot(path=str(CAP / "v1-01-version-1.0.0-con-datos.png"), full_page=True)
        pie_v1 = page.inner_text("footer")
        registrar("U1", "Actualización", "La v1.0.0 está instalada (SW activo) y tiene datos locales",
                  any("v6" in k for k in cache_v1) and len(antes) == 2,
                  f"cachés={cache_v1}; tareas={len(antes)}; pie='{pie_v1.strip()}'")

        # ===== 2. Se publica la v1.1.0 en la misma URL (mismos datos del servidor) =====
        detener(servidor)
        servidor = servir(RAIZ)
        page.goto(f"{BASE}/#inicio")
        page.evaluate("navigator.serviceWorker.getRegistration().then(r => r.update())")
        page.wait_for_selector("#banner-actualizacion:not([hidden])", timeout=15000)
        en_espera = page.evaluate("navigator.serviceWorker.getRegistration().then(r => !!r.waiting)")
        sigue_v1 = "v6" in page.inner_text("footer")
        page.wait_for_selector("#toast", state="hidden", timeout=10000)
        page.screenshot(path=str(CAP / "v1-02-aviso-nueva-version.png"))
        registrar("U2", "Actualización", "El Service Worker detecta la v1.1.0, la deja en espera y muestra el aviso «Actualizar»",
                  en_espera and sigue_v1, f"waiting={en_espera}; la página sigue en v1.0.0={sigue_v1}")

        with page.expect_navigation(timeout=15000):
            page.click("#btn-actualizar")
        esperar_app(page)
        pie_v2 = page.inner_text("footer")
        cache_v2 = page.evaluate("caches.keys()")
        html_cache = page.evaluate("caches.open('consulta-shell-v1.1.0').then(c => c.match('./index.html')).then(r => r ? r.text() : '')")
        js_cache = page.evaluate("caches.open('consulta-shell-v1.1.0').then(c => c.match('./tareas.js')).then(r => r ? r.text() : '')")
        page.screenshot(path=str(CAP / "v1-03-version-1.1.0-activa.png"))
        registrar("U3", "Actualización", "Al aceptar, se activa la v1.1.0 y la app muestra la nueva versión",
                  "v1.1.0" in pie_v2, f"pie='{pie_v2.strip()}'")
        registrar("U4", "Caché", "Las cachés de v1.0.0 se eliminan y la caché nueva contiene los archivos actualizados",
                  sorted(cache_v2) == ["consulta-datos-v1.1.0", "consulta-shell-v1.1.0"] and
                  "buscar-tareas" in html_cache and "PESO_PRIORIDAD" in js_cache,
                  f"cachés={cache_v2}; index.html nuevo={'buscar-tareas' in html_cache}; tareas.js nuevo={'PESO_PRIORIDAD' in js_cache}")

        # ===== 3. Conservación de datos =====
        despues = tareas_locales(page)
        materias = page.evaluate("Almacen.todas().then(l => l.filter(m => m.clave === 'PWA-115').length)")
        page.goto(f"{BASE}/#tareas")
        page.wait_for_selector(".tarea")
        etiquetas = page.locator(".tarea .etiqueta[class*=prioridad-]").all_inner_texts()
        page.screenshot(path=str(CAP / "v1-04-datos-conservados.png"), full_page=True)
        registrar("D1", "Datos", "Las tareas y materias guardadas en IndexedDB con v1.0.0 se conservan sin cambios",
                  len(despues) == 2 and materias == 1 and
                  sorted(t["uid"] for t in antes) == sorted(t["uid"] for t in despues) and
                  all("prioridad" not in t for t in despues),
                  f"tareas antes={len(antes)} después={len(despues)}; materia conservada={materias == 1}")
        registrar("D2", "Datos", "Las tareas anteriores (sin prioridad) se muestran como «Prioridad media»",
                  etiquetas == ["Prioridad media", "Prioridad media"], f"etiquetas={etiquetas}")

        # ===== 4. Nueva funcionalidad =====
        nueva_tarea(page, "Entregar CHANGELOG", "Documentar la versión 1.1.0", "2026-11-28", "alta")
        page.wait_for_function("document.querySelectorAll('.tarea').length === 3")
        primera = page.locator(".tarea h3").first.inner_text()
        page.screenshot(path=str(CAP / "v1-05-prioridad-alta-primero.png"), full_page=True)
        registrar("N1", "Nueva funcionalidad", "Una tarea con prioridad alta muestra su etiqueta y aparece primero aunque venza después",
                  "Entregar CHANGELOG" in primera and "Prioridad alta" in primera, f"primera='{primera}'")

        page.fill("#buscar-tareas", "PRACTICA")
        visibles = page.locator(".tarea h3").all_inner_texts()
        page.screenshot(path=str(CAP / "v1-06-busqueda.png"), full_page=True)
        page.fill("#buscar-tareas", "inexistente")
        vacio = page.inner_text("#lista-tareas")
        page.fill("#buscar-tareas", "")
        todas = page.locator(".tarea").count()
        registrar("N2", "Nueva funcionalidad", "El buscador encuentra «Práctica…» al escribir «PRACTICA» (sin acentos ni mayúsculas)",
                  len(visibles) == 1 and "Práctica" in visibles[0] and "No hay tareas que coincidan" in vacio and todas == 3,
                  f"resultados={visibles}; sin coincidencias='{vacio.strip()}'; al borrar={todas}")

        # Editar la prioridad de una tarea anterior y comprobar que llega al servidor
        uid_vieja = next(t["uid"] for t in despues if t["titulo"].startswith("Leer"))
        page.click(f".tarea[data-uid='{uid_vieja}'] [data-accion=editar]")
        page.select_option("[name=prioridad]", "baja")
        page.uncheck("#tarea-aviso")
        page.click("#btn-guardar-tarea")
        esperar(page, f"Almacen.obtenerTarea('{uid_vieja}').then(t => t.sync === 'sincronizado' && t.prioridad === 'baja')")
        remotas = json.loads(urllib.request.urlopen(BASE + "/api/tareas").read())
        remota = next(t for t in remotas if t["uid"] == uid_vieja)
        registrar("N3", "Nueva funcionalidad", "Al editar una tarea anterior, la prioridad se guarda en IndexedDB y se sincroniza con el servidor",
                  remota.get("prioridad") == "baja", f"prioridad en servidor={remota.get('prioridad')}")

        # ===== 5. Regresión: funciones de v1.0.0 =====
        page.select_option("#filtro-tareas", "pendientes")
        page.click(".tarea:has-text('Práctica de Service Worker') [data-accion=completar]")
        page.wait_for_function("document.querySelectorAll('.tarea').length === 2")
        page.select_option("#filtro-tareas", "completadas")
        completadas = page.locator(".tarea h3").all_inner_texts()
        page.select_option("#filtro-tareas", "todas")
        registrar("R1", "Regresión", "Completar una tarea y los filtros Pendientes/Completadas siguen funcionando",
                  len(completadas) == 1 and "Práctica" in completadas[0], f"completadas={completadas}")

        page.goto(f"{BASE}/#materias")
        page.wait_for_selector(".tarjeta")
        regresion_mat = "Programación Web" in page.inner_text("#vista-materias")
        registrar("R2", "Regresión", "La lista de materias (catálogo + registradas) sigue mostrando la materia de la v1.0.0",
                  regresion_mat, f"visible={regresion_mat}")

        # Sin conexión: se apaga el servidor (equivale a perder internet)
        detener(servidor)
        ctx.set_offline(True)
        page.goto(f"{BASE}/#tareas")
        page.wait_for_selector("#vista-tareas:not([hidden])", timeout=10000)
        nueva_tarea(page, "Tarea creada sin conexión", "Prueba offline", "2026-11-30", "media")
        pend = page.evaluate("Almacen.todasTareas().then(l => l.filter(t => t.sync === 'pendiente').length)")
        page.screenshot(path=str(CAP / "v1-07-sin-conexion.png"), full_page=True)
        ctx.set_offline(False)
        servidor = servir(RAIZ)
        page.evaluate("sincronizar({ origen: 'prueba' })")
        esperar(page, "Almacen.todasTareas().then(l => l.every(t => t.sync === 'sincronizado'))")
        registrar("R3", "Regresión", "Sin conexión la app abre desde caché, guarda la tarea como pendiente y la sincroniza al reconectar",
                  pend == 1, f"pendientes sin conexión={pend}; sincronizada al volver=True")

        # Compatibilidad de la API con clientes que aún tienen la v1.0.0 (no envían prioridad)
        cuerpo = json.dumps({"uid": "compat-v100-0001", "titulo": "Desde v1.0.0", "fechaLimite": "2026-12-01",
                             "estado": "pendiente", "actualizadoEn": "2026-11-14T15:00:00Z"}).encode()
        req = urllib.request.Request(BASE + "/api/tareas", cuerpo, {"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req)
        dato = json.loads(resp.read())["tarea"]
        registrar("R4", "Regresión", "La API acepta tareas de clientes v1.0.0 (sin prioridad) y las guarda como «media»",
                  resp.status == 201 and dato["prioridad"] == "media", f"HTTP {resp.status}; prioridad={dato['prioridad']}")

        registrar("R5", "Regresión", "No hubo errores de JavaScript durante todo el proceso", not errores_js,
                  f"errores={errores_js}")
    finally:
        nav.close()
        detener(servidor)

total, ok = len(filas), sum(1 for f in filas if f[3] == "PASA")
(CAP / "resultados-validacion.md").write_text(
    "# Resultados de validación v1.1.0-rc.1\n\n| ID | Tipo | Prueba | Resultado | Detalle |\n|---|---|---|---|---|\n" +
    "\n".join(f"| {a} | {b} | {c} | {d} | {e} |" for a, b, c, d, e in filas) +
    f"\n\n**{ok}/{total} pruebas pasan**\n", encoding="utf-8")
print(f"\n{ok}/{total} pruebas pasan")
sys.exit(0 if ok == total else 1)
