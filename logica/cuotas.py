# -*- coding: utf-8 -*-
"""
M1 — Cuotas del equipo (§4 del PLAN.md, Rev. 2).

El cliente fija **exactamente 6 viernes, 6 sábados y 6 domingos** por enfermera
de equipo (R13/D9). Los 6 jueves salen de las parejas sábado→jueves +5 (§3.3).
Los palancas `f` (festivos por enfermera, mitad de las celdas festivas, §3.4)
y `l` (guardias lunes–miércoles) completan las horas hasta el máximo
**por debajo del objetivo** (D10).

Estructura de horas por enfermera (todas con las mismas cuotas ±1):

    6×24 (sáb) + 6×24 (dom) + 6×17 (vie) + 6×17 (jue)  = 492 h base obligatoria
    + 24·f (festivos)  +  17·l (lun–mié)  +  compensación de jueves-festivo ≤ objetivo
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .calendario import Calendario

SABADOS_CUOTA = 6
DOMINGOS_CUOTA = 6
VIERNES_CUOTA = 6
JUEVES_CUOTA = 6

HORAS_SAB = 24
HORAS_DOM = 24
HORAS_VIE = 17
HORAS_JUE = 17
HORAS_FEST = 24
HORAS_LMX = 17

HORAS_BASE = (SABADOS_CUOTA * HORAS_SAB + DOMINGOS_CUOTA * HORAS_DOM
              + VIERNES_CUOTA * HORAS_VIE + JUEVES_CUOTA * HORAS_JUE)  # 492 h


@dataclass
class Cuotas:
    """Cuotas fijas por enfermera de equipo (Rev. 2)."""

    sabados: int = SABADOS_CUOTA
    domingos: int = DOMINGOS_CUOTA
    viernes: int = VIERNES_CUOTA
    jueves: int = JUEVES_CUOTA
    festivos: int = 0               # f — celdas festivas no sábado por enfermera
    lmx: int = 0                    # l — guardias lunes–miércoles por enfermera
    horas_base: int = HORAS_BASE
    objetivo: int = 0
    desvio: int = 0                 # objetivo − horas_previstas (≥ 0: por debajo)
    avisos: list[str] = field(default_factory=list)

    def horas_previstas(self) -> int:
        return self.horas_base + HORAS_FEST * self.festivos + HORAS_LMX * self.lmx


def factibilidad(cal: Calendario, n_equipo: int, modulos: int) -> tuple[bool, str]:
    """R13 (§4-2): 6·n_equipo ≤ m·min(S, D, V) — los jueves llegan con las
    parejas sábado→jueves+5 (S cuenta ya los sábados emparejables «Sp»).

    Devuelve (es_posible, mensaje). El mensaje indica el máximo de enfermeras
    de equipo admisibles cuando no cabe el 6/6/6.
    """
    S = cal.contar("Sp")              # sábados con jueves +5 dentro del año
    D = cal.contar("D")
    V = cal.contar("V")
    cuello = min(S, D, V)
    capacidad = modulos * cuello
    if n_equipo == 0:
        return True, ""
    maximo = capacidad // 6  # 6 cuota mínima (sáb, dom o vie) por enfermera
    if 6 * n_equipo <= capacidad:
        return True, ""
    return False, (
        f"Exceso de personal: imposible aplicar la cuota fija 6/6/6 (R13). "
        f"Con {n_equipo} enfermeras de equipo y "
        f"{modulos} módulo(s) de guardia se necesitan {6 * n_equipo} sábados/domingos/viernes, "
        f"pero el año {cal.anio} solo ofrece {cuello} por jornada (capacidad {capacidad} celdas). "
        f"Máximo de enfermeras de equipo admisible: {maximo}. "
        f"Reduce el número de enfermeras o aumenta los módulos de guardia.")


def calcular_cuotas(cal: Calendario, n_equipo: int, modulos: int,
                    horas_objetivo: int) -> Cuotas:
    """Cuota fija 6/6/6 + palancas f (festivos) y l (LMX) — §4 (D9, D10).

    - f: reparto equitativo (±1 por enfermera ≈ mitad de las celdas festivas
      del equipo, §3.4). La cuota nominal usa el reparto entero por enfémera.
    - l: mayor nº de guardias LMX tal que horas ≤ objetivo, siempre que la
      base 492 h quepa; si el objetivo < 492 h se informa y el relleno queda a 0.
    """
    cuotas = Cuotas(objetivo=horas_objetivo)

    # --- f: celdas festivas del equipo (mitad/mitad, §3.4) ------------------
    # Los sábados-festivo consumen la cuota de SÁBADOS (D11), no la de festivos.
    # Con m=2: 1 celda de equipo por día festivo; con m=1: días alternos,
    # empezando por equipo.
    festivos_equipo = CeldasFestivasEquipo(cal, modulos)
    if n_equipo:
        cuotas.festivos = festivos_equipo.total_celdas // n_equipo
        if festivos_equipo.total_celdas % n_equipo:
            cuotas.festivos += 1   # redondeo hacia arriba; el solver iguala con ±1

    # --- l: relleno LMX por debajo del objetivo (D10) -----------------------
    margen = horas_objetivo - HORAS_BASE - 24 * cuotas.festivos
    if margen < 0:
        cuotas.lmx = 0
        cuotas.avisos.append(
            f"El objetivo de horas ({horas_objetivo} h) es inferior a la base obligatoria "
            f"de la cuota 6/6/6 ({HORAS_BASE} h): no se añade relleno y el resultado "
            f"superará el objetivo en {HORAS_BASE - horas_objetivo} h por enfermera.")
        cuotas.desvio = margen  # negativo: por encima del objetivo
        return cuotas

    l = margen // HORAS_LMX
    # Capacidad del pool de LMX para no dejar enfermeras sin llenar
    pool_lmx = cal.contar("LMX") * min(2, modulos)
    if n_equipo:
        l_max_pool = int(pool_lmx // n_equipo)
        l = min(l, l_max_pool)
    cuotas.lmx = l
    cuotas.desvio = horas_objetivo - cuotas.horas_previstas()
    return cuotas


class CeldasFestivasEquipo:
    """Celdas festivas de EQUIPO generadas para el año («f» global, §3.4)."""

    def __init__(self, cal: Calendario, modulos: int):
        self.cal = cal
        self.modulos = modulos
        self.total_celdas = 0
        self._celdas: list[tuple] = []          # (fecha, índice de celda 0..m-1)
        turno = 0                                # alterna m=1 desde equipo
        for dd in cal.dias_de("F"):
            if modulos == 2:
                self.total_celdas += 1
                self._celdas.append((dd.fecha, 0))
            elif turno == 0:
                self.total_celdas += 1
                self._celdas.append((dd.fecha, 0))
            turno ^= 1

    @property
    def celdas(self) -> list[tuple]:
        return list(self._celdas)


def resumen_cuotas(cuotas: Cuotas) -> str:
    if cuotas.avisos:
        return " · ".join(cuotas.avisos)
    return (f"Cuotas 6/6/6 exactas; festivos f={cuotas.festivos}; "
            f"LMX l={cuotas.lmx}; horas previstas {cuotas.horas_previstas()} h "
            f"(desvío {cuotas.desvio} h).")
