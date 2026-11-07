"""Pruebas de la API de tareas (Actividad 12) sin navegador. Uso: python3 tests/api_tareas.py"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

carpeta = tempfile.mkdtemp()
os.environ["MATERIAS_DB"] = os.path.join(carpeta, "db.json")
os.environ["TAREAS_DB"] = os.path.join(carpeta, "tareas.json")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))
import app as servidor  # noqa: E402


def tarea(**cambios):
    base = {"uid": "tarea-0001-abc", "titulo": "Entregar reporte", "descripcion": "Actividad 12",
            "fechaLimite": "2026-11-10", "estado": "pendiente",
            "creadoEn": "2026-11-04T10:00:00.000Z", "actualizadoEn": "2026-11-04T10:00:00.000Z"}
    base.update(cambios)
    return base


class PruebasTareas(unittest.TestCase):
    def setUp(self):
        servidor.ARCHIVO_TAREAS.unlink(missing_ok=True)
        self.c = servidor.app.test_client()

    def test_crea_y_lista(self):
        r = self.c.post("/api/tareas", json=tarea())
        self.assertEqual(r.status_code, 201)
        self.assertFalse(r.get_json()["duplicado"])
        self.assertEqual(len(self.c.get("/api/tareas").get_json()), 1)

    def test_reintento_no_duplica(self):
        for _ in range(5):
            self.c.post("/api/tareas", json=tarea())
        lista = self.c.get("/api/tareas").get_json()
        self.assertEqual(len(lista), 1)
        r = self.c.post("/api/tareas", json=tarea())
        self.assertEqual((r.status_code, r.get_json()["duplicado"]), (200, True))

    def test_edicion_mas_reciente_actualiza(self):
        self.c.post("/api/tareas", json=tarea())
        r = self.c.post("/api/tareas", json=tarea(titulo="Reporte final", estado="completada",
                                                  actualizadoEn="2026-11-05T09:00:00.000Z"))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.get_json()["actualizada"])
        lista = self.c.get("/api/tareas").get_json()
        self.assertEqual((len(lista), lista[0]["titulo"], lista[0]["estado"]), (1, "Reporte final", "completada"))

    def test_edicion_mas_vieja_se_ignora(self):
        self.c.post("/api/tareas", json=tarea(actualizadoEn="2026-11-05T09:00:00.000Z", titulo="Nueva"))
        r = self.c.post("/api/tareas", json=tarea(titulo="Vieja", actualizadoEn="2026-11-04T09:00:00.000Z"))
        self.assertTrue(r.get_json()["duplicado"])
        self.assertEqual(self.c.get("/api/tareas").get_json()[0]["titulo"], "Nueva")

    def test_ubicacion_opcional_y_validada(self):
        self.assertEqual(self.c.post("/api/tareas", json=tarea()).status_code, 201)  # sin ubicación
        ok = self.c.post("/api/tareas", json=tarea(uid="tarea-0002-abc",
                         ubicacion={"lat": 19.2827, "lon": -99.6557, "precision": 20}))
        self.assertEqual(ok.status_code, 201)
        self.assertEqual(ok.get_json()["tarea"]["ubicacion"]["lat"], 19.2827)
        malo = self.c.post("/api/tareas", json=tarea(uid="tarea-0003-abc", ubicacion={"lat": 120, "lon": 0}))
        self.assertEqual(malo.status_code, 400)

    def test_datos_invalidos(self):
        casos = [tarea(titulo="  "), tarea(fechaLimite="10/11/2026"), tarea(fechaLimite="2026-13-40"),
                 tarea(estado="hecha"), tarea(uid="x"), tarea(actualizadoEn="ayer")]
        for caso in casos:
            self.assertEqual(self.c.post("/api/tareas", json=caso).status_code, 400, caso)
        self.assertEqual(self.c.post("/api/tareas", data="no es json").status_code, 400)
        self.assertEqual(self.c.get("/api/tareas").get_json(), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
