# -*- coding: utf-8 -*-
"""Casos límite (§8) + validaciones del contrato (§9.3)."""

import collections
import datetime
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from logica.calendario import Calendario            # noqa: E402
from logica.solver import categoria_dia, resolver_plan  # noqa: E402
from logica.validar_resultado import validar_resultado  # noqa: E402
from logica.verificar_libro import verificar_libro  # noqa: E402
from logica.generador import GeneradorExcel         # noqa: E402
from logica.excel_logica import procesar, validar   # noqa: E402
from logica.cuotas import factibilidad              # noqa: E402
from logica.festivos_precarga import festivos_precargados  # noqa: E402


def run(anio, fest, n_eq, n_ar, mod, he):
    cal = Calendario(anio, [datetime.date.fromisoformat(x) for x in fest])
    asign, err, cuotas = resolver_plan(cal, n_eq, n_ar, mod, he)
    return cal, asign, err, cuotas


def _resuelto(cal, asign, err, cuotas, mod, he):
    ok, _ = validar_resultado(cal, asign, cuotas, mod, he)
    wb = GeneradorExcel(cal, asign, len(asign.equipo), len(asign.area),
                        mod).construir()
    return ok, verificar_libro(wb, cal, asign, mod)


class TestBisiesto(unittest.TestCase):
    def test_2028_resuelve_y_verifica(self):
        cal_f = festivos_precargados(2028)
        cal = Calendario(2028, cal_f)
        asign, err, cuotas = resolver_plan(cal, 8, 2, 2, 850)
        self.assertEqual(err, "")
        ok, fallos = _resuelto(cal, asign, err, cuotas, 2, 850)
        self.assertTrue(ok)
        self.assertEqual(fallos, [])
        dias_anio = 366
        celdas = (sum(len(x) for x in asign.equipo.values())
                  + sum(len(x) for x in asign.area.values()) + len(asign.bolsa))
        self.assertEqual(celdas, dias_anio * 2)


class TestFestivos(unittest.TestCase):
    """Festivo en sábado / en jueves: se empareja igual (D11) y 24 h."""

    def test_festivo_en_sabado(self):
        # 2027-05-01 cae en sábado: el pool S lo absorbe (D11)
        cal = Calendario(2027, [datetime.date(2027, 5, 1)])
        asign, err, cuotas = resolver_plan(cal, 11, 3, 2, 880)
        self.assertEqual(err, "")
        ok, fallos = _resuelto(cal, asign, "", cuotas, 2, 880)
        self.assertTrue(ok)
        self.assertEqual(fallos, [])

    def test_festivo_en_jueves(self):
        # 2027-03-25 es jueves (Semana Santa): pareja con su sábado +5? no:
        # la pareja es sáb→jue+5; el jueves festivo se compensa del pool F.
        cal = Calendario(2027, [datetime.date(2027, 3, 25)])
        asign, err, cuotas = resolver_plan(cal, 11, 0, 2, 880)
        self.assertEqual(err, "")
        ok, fallos = _resuelto(cal, asign, "", cuotas, 2, 880)
        self.assertTrue(ok)
        self.assertEqual(fallos, [])


class TestPlantillas(unittest.TestCase):
    def test_r13_plantilla_mayor_que_capacidad(self):
        # 52 sábados · 1 módulo · 10 enfermeras: imposible (R13)
        cal = Calendario(2027, [])
        _, err, _ = resolver_plan(cal, 10, 0, 1, 880)
        self.assertIn("admisible", err)

    def test_factibilidad_mensaje_maximo(self):
        cal = Calendario(2026, [])
        ok, msg = factibilidad(cal, 9, 1)
        self.assertFalse(ok)
        self.assertIn("Máximo de enfermeras de equipo admisible: 8", msg)


class TestObjetivoHoras(unittest.TestCase):
    def test_objetivo_menor_base_492(self):
        cal = Calendario(2027, [datetime.date.fromisoformat(x) for x in
                                ["2027-12-25", "2027-01-01"]])
        asign, err, cuotas = resolver_plan(cal, 11, 0, 2, 400)
        self.assertEqual(err, "")
        self.assertEqual(cuotas.lmx, 0)
        self.assertTrue(cuotas.avisos)      # aviso de objetivo insuficiente
        # uniformes salvo redondeo de festivos (±24 h por f redondeado a alumna)
        horas = [sum(cal.por_fecha(datetime.date.fromisoformat(f)).horas
                     for f in fs) for fs in asign.equipo.values()]
        self.assertLessEqual(max(horas) - min(horas), 24)
        self.assertGreater(horas[0], 400)            # base obligatoria 492 h

    def test_demanda_menor_que_oferta_bolsa_cero(self):
        cal = Calendario(2027, [datetime.date.fromisoformat(x) for x in
                                ["2027-01-01", "2027-12-25"]])
        asign, err, cuotas = resolver_plan(cal, 11, 3, 2, 880)
        self.assertEqual(err, "")
        self.assertEqual(len(asign.bolsa), 0)

    def test_bolsa_manual_cuando_oferta_corta(self):
        # m=2, 1 sola enfermera de equipo y 0 de área: la bolsa queda enorme
        cal = Calendario(2027, [])
        asign, err, cuotas = resolver_plan(cal, 1, 0, 2, 492)
        self.assertEqual(err, "")
        self.assertGreater(len(asign.bolsa), 0)
        self.assertGreater(sum(b["horas"] for b in asign.bolsa), 0)


class TestTopeArea(unittest.TestCase):
    """horas_area > 0 limita el relleno del área; el resto va a la bolsa."""

    def test_area_no_supera_objetivo(self):
        cal = Calendario(2027, [datetime.date.fromisoformat(x) for x in
                                ["2027-01-01", "2027-12-25"]])
        asign, err, cuotas = resolver_plan(cal, 4, 2, 2, 600, 900)
        self.assertEqual(err, "")
        horas = [sum(cal.por_fecha(datetime.date.fromisoformat(f)).horas
                     for f in fs) for fs in asign.area.values()]
        self.assertTrue(all(h <= 900 + 24 for h in horas))   # soft cap ≤ +24 h
        self.assertGreater(len(asign.bolsa), 0)              # resto → bolsa
        ok, fallos = _resuelto(cal, asign, "", cuotas, 2, 600)
        self.assertTrue(ok)
        self.assertEqual(fallos, [])

    def test_sin_objetivo_no_para_por_horas(self):
        # horas_area = 0 → sin límite de horas: el área no se detiene por
        # cuota, solo por la regla dura de no-consecutivos (con 2 enfermeras
        # y m=2 quedan celdas para la bolsa los días alternos)
        cal = Calendario(2027, [datetime.date.fromisoformat(x) for x in
                                ["2027-01-01", "2027-12-25"]])
        asign, err, _ = resolver_plan(cal, 4, 2, 2, 600, 0)
        self.assertEqual(err, "")
        horas = [sum(cal.por_fecha(datetime.date.fromisoformat(f)).horas
                     for f in fs) for fs in asign.area.values()]
        self.assertGreater(min(horas), 900)   # sin tope: sigue rellenando
        for fs in asign.area.values():
            fset = {datetime.date.fromisoformat(x) for x in fs}
            for f in fset:
                self.assertNotIn(f + datetime.timedelta(days=1), fset)


class TestBolsaNoSeguida(unittest.TestCase):
    """La bolsa «Vacío» se reparte por el año y sus días no quedan seguidos."""

    def test_bolsa_pequeña_sin_seguidos(self):
        # golden-like: 2 celdas de bolsa en días no consecutivos
        cal = Calendario(2027, [datetime.date.fromisoformat(x) for x in
                                ["2027-01-01", "2027-12-25"]])
        asign, err, _ = resolver_plan(cal, 11, 3, 2, 880, 1460)
        self.assertEqual(err, "")
        fechas = sorted(datetime.date.fromisoformat(b["fecha"])
                        for b in asign.bolsa)
        self.assertGreaterEqual(len(fechas), 1)
        for a, b in zip(fechas, fechas[1:]):
            self.assertGreater((b - a).days, 1,
                               f"bolsa en días seguidos: {a} y {b}")

    def test_bolsa_moderada_sin_seguidos(self):
        # 133 días de bolsa repartidos sin adyacencias (best effort)
        cal = Calendario(2027, [datetime.date.fromisoformat(x) for x in
                                ["2027-01-01", "2027-12-25"]])
        asign, err, _ = resolver_plan(cal, 9, 3, 2, 860, 1300)
        self.assertEqual(err, "")
        fechas = sorted({datetime.date.fromisoformat(b["fecha"])
                         for b in asign.bolsa})
        self.assertGreater(len(fechas), 100)
        pares = [b for a, b in zip(fechas, fechas[1:]) if (b - a).days == 1]
        self.assertLessEqual(len(pares), 2,
                             f"demasiados días de bolsa seguidos: {pares[:5]}")

    def test_caso_10_2_tope_1460_sin_seguidos(self):
        # caso real de usuario: 10 enfermeras · 2 de área · tope 1460:
        # el fallo del relleno caía junto a un día reservado → par seguido
        cal = Calendario(2027, festivos_precargados(2027))
        asign, err, _ = resolver_plan(cal, 10, 2, 2, 880, 1460)
        self.assertEqual(err, "")
        fechas = sorted({datetime.date.fromisoformat(b["fecha"])
                         for b in asign.bolsa})
        self.assertGreater(len(fechas), 50)
        pares = [b for a, b in zip(fechas, fechas[1:]) if (b - a).days == 1]
        self.assertEqual(pares, [], f"días de bolsa seguidos: {pares[:5]}")

    def test_bolsa_masiva_mejor_esfuerzo(self):
        # con falta de personal la bolsa supera la mitad de los días: no se
        # puede garantizar la no-adyacencia, pero el solver no se cuelga
        cal = Calendario(2027, [datetime.date.fromisoformat(x) for x in
                                ["2027-01-01", "2027-12-25"]])
        asign, err, _ = resolver_plan(cal, 6, 2, 2, 700, 900)
        self.assertEqual(err, "")
        self.assertGreater(len(asign.bolsa), 300)


class TestAreaProporcional(unittest.TestCase):
    """Las enfermeras de área reparten las categorías de forma proporcional."""

    FEST = ["2027-01-01", "2027-12-25"]

    def _reparto(self, n_eq, n_ar, m, he, ha):
        cal = Calendario(2027, [datetime.date.fromisoformat(x) for x in self.FEST])
        asign, err, cuotas = resolver_plan(cal, n_eq, n_ar, m, he, ha)
        self.assertEqual(err, "")
        cats = {}
        for n, fs in asign.area.items():
            fset = {datetime.date.fromisoformat(x) for x in fs}
            cats[n] = collections.Counter(
                categoria_dia(cal.por_fecha(f)) for f in fset)
        return cal, asign, cuotas, cats

    def test_golden_proporcional(self):
        _, _, _, cats = self._reparto(11, 3, 2, 880, 1460)
        for clave in ("S", "D", "V", "J", "F", "LMX"):
            valores = [c.get(clave, 0) for c in cats.values()]
            self.assertLessEqual(max(valores) - min(valores), 3,
                                 f"{clave} desequilibrado: {valores}")

    def test_validador_detecta_desequilibrio(self):
        # el validador interno falla con un reparto claramente desproporcionado
        cal = Calendario(2027, [datetime.date.fromisoformat(x) for x in self.FEST])
        _, asign, cuotas, _ = self._reparto(11, 3, 2, 880, 1460)
        ok, msg = validar_resultado(cal, asign, cuotas, 2, 880)
        self.assertTrue(ok)                       # el caso normal está equilibrado
        asign.area["R1"] = [f for f in asign.area["R1"]
                            if cal.por_fecha(datetime.date.fromisoformat(f))
                            .weekday != 5]
        ok, msg = validar_resultado(cal, asign, cuotas, 2, 880)
        self.assertFalse(ok)
        self.assertIn("desproporcionado de S", msg)


class TestValidarContrato(unittest.TestCase):
    BASE = {"anio": 2027, "enfermeras": 11, "enfermeras_area": 3,
            "modulos_guardia": 2, "horas_equipo": 880, "horas_area": 1460,
            "festivos": ["2027-01-01", "2027-12-25"]}

    def test_ok(self):
        self.assertIsNone(validar(self.BASE))

    def test_modulos(self):
        for mal in (0, 3):
            p = dict(self.BASE, modulos_guardia=mal)
            self.assertIsNotNone(validar(p))

    def test_negativas(self):
        p = dict(self.BASE, horas_area=-1)
        self.assertIsNotNone(validar(p))

    def test_anio_fuera(self):
        self.assertIsNotNone(validar(dict(self.BASE, anio=2110)))
        self.assertIsNotNone(validar(dict(self.BASE, anio="abc")))

    def test_duplicados(self):
        p = dict(self.BASE, festivos=["2027-01-01", "2027-01-01"])
        self.assertIn("duplicados", str(validar(p)))

    def test_anios_mezclados(self):
        p = dict(self.BASE, festivos=["2027-01-01", "2028-01-01"])
        self.assertIn("otro año", str(validar(p)))

    def test_procesar_rechaza_r13(self):
        r = procesar(dict(self.BASE, festivos=[], modulos_guardia=1,
                          enfermeras=10))
        self.assertFalse(r.ok)
        self.assertIn("Máximo", r.mensaje)

    def test_procesar_genera_bytes(self):
        r = procesar(self.BASE)
        self.assertTrue(r.ok)
        self.assertTrue(r.contenido.startswith(b"PK"))   # xlsx zip


if __name__ == "__main__":
    unittest.main()
