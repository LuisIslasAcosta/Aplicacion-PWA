"""Servidor de Consulta Académica PWA (Actividades 08 y 10).

- Sirve la PWA estática desde ../public
- API REST:
    GET  /api/health    -> 200 si el servidor está disponible (sondeo de conectividad)
    GET  /api/materias  -> catálogo base + materias registradas
    POST /api/materias  -> registra una materia. IDEMPOTENTE por `uid`:
                           si el uid ya existe responde 200 {duplicado: true}
                           y NO crea otro registro (evita duplicados en reintentos).
"""
import json
import os
import re
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

RAIZ = Path(__file__).resolve().parent
PUBLICO = RAIZ.parent / "public"
SEMILLA = PUBLICO / "data" / "materias.json"
ARCHIVO_DB = Path(os.environ.get("MATERIAS_DB", RAIZ / "db.json"))

UID_VALIDO = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
CAMPOS_TEXTO = ("nombre", "clave", "docente", "horario", "salon", "autor")

app = Flask(__name__, static_folder=None)
candado = threading.Lock()  # serializa lecturas/escrituras del archivo


def leer_registradas():
    if not ARCHIVO_DB.exists():
        return []
    try:
        return json.loads(ARCHIVO_DB.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def guardar_registradas(lista):
    # Escritura atómica: archivo temporal + reemplazo
    fd, ruta = tempfile.mkstemp(dir=ARCHIVO_DB.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(lista, f, ensure_ascii=False, indent=2)
    os.replace(ruta, ARCHIVO_DB)


def catalogo_base():
    datos = json.loads(SEMILLA.read_text(encoding="utf-8"))
    for m in datos:
        m["uid"] = f"base-{m['id']}"
    return datos


def validar_ubicacion(u):
    """Devuelve (ubicacion_limpia, error). lat/lon obligatorios y en rango; precision opcional."""
    if not isinstance(u, dict):
        return None, "ubicacion inválida"
    try:
        lat, lon = float(u.get("lat")), float(u.get("lon"))
    except (TypeError, ValueError):
        return None, "ubicacion: lat y lon deben ser numéricos"
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None, "ubicacion: lat/lon fuera de rango"
    limpia = {"lat": round(lat, 6), "lon": round(lon, 6)}
    try:
        precision = u.get("precision")
        if precision is not None:
            limpia["precision"] = max(0, int(precision))
    except (TypeError, ValueError):
        return None, "ubicacion: precision inválida"
    if isinstance(u.get("tomadoEn"), str):
        limpia["tomadoEn"] = u["tomadoEn"][:40]
    return limpia, None


def validar(d):
    """Devuelve (materia_limpia, error)."""
    if not isinstance(d, dict):
        return None, "Cuerpo JSON inválido"
    uid = d.get("uid")
    if not isinstance(uid, str) or not UID_VALIDO.match(uid):
        return None, "uid requerido (8-64 caracteres alfanuméricos, - o _)"
    limpia = {"uid": uid}
    for campo in CAMPOS_TEXTO:
        valor = d.get(campo)
        if not isinstance(valor, str) or not valor.strip():
            return None, f"Campo requerido: {campo}"
        limpia[campo] = valor.strip()[:200]
    for campo, minimo, maximo in (("semestre", 1, 12), ("creditos", 1, 12)):
        try:
            n = int(d.get(campo))
        except (TypeError, ValueError):
            return None, f"Campo numérico inválido: {campo}"
        if not minimo <= n <= maximo:
            return None, f"{campo} debe estar entre {minimo} y {maximo}"
        limpia[campo] = n
    temas = d.get("temas")
    if not isinstance(temas, list) or not temas:
        return None, "temas debe ser una lista no vacía"
    limpia["temas"] = [str(t).strip()[:100] for t in temas if str(t).strip()][:30]
    ubicacion = d.get("ubicacion")
    if ubicacion is not None:  # opcional: coordenadas capturadas con la geolocalización del dispositivo
        limpia_u, error_u = validar_ubicacion(ubicacion)
        if error_u:
            return None, error_u
        limpia["ubicacion"] = limpia_u
    limpia["creadoEn"] = d.get("creadoEn") if isinstance(d.get("creadoEn"), str) else None
    return limpia, None


@app.get("/api/health")
def salud():
    return jsonify(ok=True), 200, {"Cache-Control": "no-store"}


@app.get("/api/materias")
def listar():
    with candado:
        registradas = leer_registradas()
    return jsonify(catalogo_base() + registradas), 200, {"Cache-Control": "no-store"}


@app.post("/api/materias")
def crear():
    materia, error = validar(request.get_json(silent=True))
    if error:
        return jsonify(error=error), 400
    with candado:
        registradas = leer_registradas()
        existente = next((m for m in registradas if m["uid"] == materia["uid"]), None)
        if existente:  # reintento: no se duplica
            return jsonify(materia=existente, duplicado=True), 200
        materia["recibidoEn"] = datetime.now(timezone.utc).isoformat()
        registradas.append(materia)
        guardar_registradas(registradas)
    return jsonify(materia=materia, duplicado=False), 201


@app.get("/")
def raiz():
    return send_from_directory(PUBLICO, "index.html")


@app.get("/<path:ruta>")
def estaticos(ruta):
    respuesta = send_from_directory(PUBLICO, ruta)
    # El SW debe revalidarse siempre para detectar nuevas versiones
    if ruta == "sw.js":
        respuesta.headers["Cache-Control"] = "no-cache"
    return respuesta


if __name__ == "__main__":
    puerto = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=puerto, debug=False, threaded=True)
