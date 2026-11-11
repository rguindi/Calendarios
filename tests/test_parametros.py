# -*- coding: utf-8 -*-
"""Parámetros declarativos: campo `anio` (D13) primero y con límites correctos."""

import datetime
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from config.parametros import CAMPOS_NUMERICOS       # noqa: E402


class TestCampoAnio(unittest.TestCase):
    def test_anio_primero(self):
        self.assertEqual(CAMPOS_NUMERICOS[0].clave, "anio")

    def test_limites_d13(self):
        anio = CAMPOS_NUMERICOS[0]
        self.assertEqual(anio.minimo, 2020)
        self.assertEqual(anio.maximo, 2100)

    def test_inicial_siguiente_anio(self):
        # tolerante a la medianoche de fin de año
        esperado = datetime.date.today().year + 1
        self.assertIn(CAMPOS_NUMERICOS[0].inicial, (esperado, esperado + 1))


if __name__ == "__main__":
    unittest.main()
