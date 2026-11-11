# -*- coding: utf-8 -*-
"""Golden 2027 (§7/§9.1): la entrada del formulario regenera la asignación
congelada en `referencia/golden_2027_rev5.json` y cumple los invariantes Rev. 2."""

import datetime
import json
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from logica.calendario import Calendario                      # noqa: E402
from logica.solver import resolver_plan                       # noqa: E402
from logica.validar_resultado import validar_resultado        # noqa: E402
from logica.verificar_libro import verificar_libro            # noqa: E402
from logica.generador import GeneradorExcel                   # noqa: E402
from logica.excel_logica import procesar                      # noqa: E402

GOLDEN = json.loads((RAIZ / "referencia" / "golden_2027_rev5.json").read_text())
ENTRADA = dict(GOLDEN["entrada"])
ENTRADA["anio"] = GOLDEN["anio"]


class TestGolden2027(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.cal = Calendario(2027, [datetime.date.fromisoformat(x)
                                    for x in ENTRADA["festivos"]])
        cls.asign, cls.err, cls.cuotas = resolver_plan(
            cls.cal, ENTRADA["enfermeras"], ENTRADA["enfermeras_area"],
            ENTRADA["modulos_guardia"], ENTRADA["horas_equipo"],
            ENTRADA["horas_area"])
        cls.ok_v, cls.informe_v = validar_resultado(
            cls.cal, cls.asign, cls.cuotas, ENTRADA["modulos_guardia"],
            ENTRADA["horas_equipo"])

    # --- reproducibilidad del congelado ------------------------------------
    def test_regenera_golden(self):
        self.assertEqual(self.err, "")
        self.assertEqual(self.asign.equipo, GOLDEN["equipo"])
        self.assertEqual(self.asign.area, GOLDEN["area"])
        self.assertEqual(self.asign.bolsa, GOLDEN["bolsa"])

    # --- invariantes Rev. 2 (§3/§4) ------------------------------------------
    def test_cuotas_6_6_6_y_880h(self):
        for nombre, fechas in self.asign.equipo.items():
            dias = [self.cal.por_fecha(datetime.date.fromisoformat(f))
                    for f in fechas]
            horas = sum(d.horas for d in dias)
            self.assertEqual(horas, 880, nombre)
            cont = {"S": 0, "D": 0, "V": 0, "J": 0, "F": 0, "LMX": 0}
            for d in dias:
                cont[self._cat(d)] += 1
            self.assertEqual(cont["S"], 6, nombre)     # incluye sáb-festivo
            self.assertEqual(cont["D"], 6, nombre)
            self.assertEqual(cont["V"], 6, nombre)
            self.assertEqual(cont["J"], 6, nombre)
            self.assertEqual(cont["F"], 2, nombre)
            self.assertEqual(cont["LMX"], 20, nombre)
            self.assertEqual(sum(cont.values()), 46, nombre)

    @staticmethod
    def _cat(d):
        if d.horas == 24:
            if d.fecha.weekday() == 5:
                return "S"
            if d.fecha.weekday() == 6:
                return "D"
            return "F"
        if d.weekday <= 2:
            return "LMX"
        if d.weekday == 3:
            return "J"
        return "V"

    def test_validador_interno_ok(self):
        self.assertTrue(self.ok_v, self.informe_v)

    def test_parejas_y_descanso(self):
        fs = {n: {datetime.date.fromisoformat(x) for x in ls}
              for n, ls in self.asign.equipo.items()}
        for nombre, fechas in fs.items():
            for s in (d for d in fechas if d.weekday() == 5):
                self.assertIn(s + datetime.timedelta(days=5), fechas,
                              f"{nombre} sáb {s} sin jueves +5")
                for delta in (-2, -1, 1, 2, 3, 4):
                    self.assertNotIn(s + datetime.timedelta(days=delta),
                                     fechas, f"{nombre} 72 h roto en {s}")

    def test_area_media_objetivo(self):
        horas = [sum(self.cal.por_fecha(datetime.date.fromisoformat(f)).horas
                     for f in fs) for fs in self.asign.area.values()]
        media = sum(horas) // len(horas)
        # la reserva de bolsa sin días seguidos puede costar 1–2 celdas de 24 h
        self.assertAlmostEqual(media, 1460, delta=2 * 24 / len(horas))

    def test_cuotas_informe(self):
        self.assertEqual(self.cuotas.festivos, 2)
        self.assertEqual(self.cuotas.lmx, 20)
        self.assertEqual(self.cuotas.desvio, 0)
        # tope estricto de área: 31/12 (1460 + 24 > 1460) queda en bolsa
        self.assertEqual(self.asign.bolsa, GOLDEN["bolsa"])

    # --- libro generado pasa la emulación (§9.4) ------------------------------
    def test_libro_pasa_emulacion(self):
        wb = GeneradorExcel(self.cal, self.asign, ENTRADA["enfermeras"],
                            ENTRADA["enfermeras_area"],
                            ENTRADA["modulos_guardia"]).construir()
        errores = verificar_libro(wb, self.cal, self.asign,
                                  ENTRADA["modulos_guardia"])
        self.assertEqual(errores, [])

    # --- end-to-end del contrato §11 -----------------------------------------
    def test_procesar_end_to_end(self):
        r = procesar(ENTRADA)
        self.assertTrue(r.ok, r.mensaje)
        self.assertIsNotNone(r.contenido)
        self.assertEqual(r.archivo, "Calendario 2027.xlsx")
        self.assertIn("880", r.mensaje)
        self.assertIn("sin cubrir", r.mensaje.lower())


if __name__ == "__main__":
    unittest.main()
