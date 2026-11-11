# -*- coding: utf-8 -*-
"""
M1 — Construcción del calendario de guardias de un año.

Dado un `anio` y una lista de fechas festivas (locales del formulario +
precargadas), produce la estructura de días del año con:

- weekday, ¿festivo?, ¿festivo especial? (Butcher sobre Pascua),
- horas de la celda según §3.1 del PLAN.md:
    festivo 24 h  ·  sábado/domingo no festivo 24 h  ·  laborable 17 h.

Los festivos ESPECIALES (1/1, Jueves y Viernes Santo, 24/12, 25/12 y 31/12)
se derivan del domingo de Pascua (algoritmo de Butcher) — nunca fijados.
"""

from __future__ import annotations

import calendar
import datetime
from dataclasses import dataclass
from typing import Iterable

# Horas por tipo de celda (§3.1)
HORAS_FESTIVO = 24
HORAS_FINDISM = 24
HORAS_LABORABLE = 17

# Festivos especiales de fecha fija (reparto obligatorio mitad/mitad, §3.4)
ESPECIALES_FIJOS = {(1, 1), (12, 24), (12, 25), (12, 31)}

# Nombres cortos del weekday (python: 0=lun … 6=dom)
NOMBRE_DIA = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

# Abreviaturas para el Excel (orden de columnas del modelo: E=miércoles…)
ABREVIATURA = {0: "Lun", 1: "Mar", 2: "Mié", 3: "Jue", 4: "Vie", 5: "Sáb", 6: "Dom"}


def domingo_pascua(anio: int) -> datetime.date:
    """Domingo de Pascua por el algoritmo de Butcher (Gregoriano)."""
    a = anio % 19
    b, c = divmod(anio, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = ((h + l - 7 * m + 114) % 31) + 1
    return datetime.date(anio, mes, dia)


def festivos_especiales(anio: int) -> set[datetime.date]:
    """1/1, Jueves y Viernes Santo, 24, 25 y 31/12 del año."""
    pascua = domingo_pascua(anio)
    fechas = {datetime.date(anio, m, d) for (m, d) in ESPECIALES_FIJOS}
    fechas.update(pascua - datetime.timedelta(days=o) for o in (3, 2))
    return {f for f in fechas if f.year == anio}


def a_fecha(valor) -> datetime.date:
    """Acepta `date`, `datetime` o cadena ISO 'YYYY-MM-DD'."""
    if isinstance(valor, datetime.datetime):
        return valor.date()
    if isinstance(valor, datetime.date):
        return valor
    return datetime.date.fromisoformat(str(valor).strip())


@dataclass
class Dia:
    """Un día del calendario de guardias."""

    fecha: datetime.date
    weekday: int          # 0=lunes … 6=domingo
    festivo: bool         # festivo del año (locales + precargados)
    especial: bool        # festivo especial (mitad/mitad obligatoria)
    horas: int            # horas de la celda de guardia (§3.1)

    # --- categorías del solver (portadas del modelo Excel) ---
    @property
    def es_sabado(self) -> bool:
        return self.weekday == 5

    @property
    def es_domingo(self) -> bool:
        return self.weekday == 6

    @property
    def es_jueves(self) -> bool:
        return self.weekday == 3

    @property
    def es_17h(self) -> bool:
        """Celda de 17 h: laborable no festivo (L–V)."""
        return self.horas == HORAS_LABORABLE

    @property
    def es_s_festivo(self) -> bool:
        """Sábado-festivo: cuenta en la cuota de sábados (R13/D11), no en f."""
        return self.festivo and self.es_sabado

    @property
    def grupo_especial(self) -> str | None:
        """Grupo del festivo especial: 'NAV' (1/1, 24, 25 y 31/12), 'SS'
        (Semana Santa) o None si el día no es especial."""
        if not (self.festivo and self.especial):
            return None
        return "NAV" if (self.fecha.month, self.fecha.day) in ESPECIALES_FIJOS else "SS"

    def categoria_24h(self) -> str:
        """Clave del contador de horas: festivo / sábado / domingo."""
        if self.festivo:
            return "F"
        return "K" if self.es_sabado else "D"


class Calendario:
    """Todos los días del año de guardias, categorizados."""

    def __init__(self, anio: int, festivos: Iterable[datetime.date]):
        self.anio = anio
        self.especiales = festivos_especiales(anio)
        fechas = sorted({a_fecha(f) for f in festivos})
        self.festivos = {f for f in fechas if f.year == anio}
        self.dias: list[Dia] = []
        d = datetime.date(anio, 1, 1)
        fin = datetime.date(anio, 12, 31)
        while d <= fin:
            festivo = d in self.festivos
            if festivo:
                horas = HORAS_FESTIVO
            elif d.weekday() >= 5:
                horas = HORAS_FINDISM
            else:
                horas = HORAS_LABORABLE
            self.dias.append(Dia(fecha=d, weekday=d.weekday(), festivo=festivo,
                                 especial=d in self.especiales, horas=horas))
            d += datetime.timedelta(days=1)
        self._pordia = {dd.fecha: dd for dd in self.dias}

    # ------------------------------------------------------------------
    def por_fecha(self, fecha: datetime.date) -> Dia | None:
        return self._pordia.get(fecha)

    def hay(self, fecha: datetime.date) -> bool:
        return fecha in self._pordia

    # --- contadores globales de categorías (para cuotas/factibilidad) ---
    def contar(self, clave: str) -> int:
        """Nº de días de una categoría:
        'S' sábados (todos, incl. sáb-festivo), 'Sp' sábados emparejables
        (los que disponen de jueves +5 dentro del año), 'D' domingos (todos),
        'V' viernes ordinarios, 'F' festivos no sábado, 'LMX' lunes a miércoles,
        'J' jueves (todos — vía parejas siempre hay jueves +5 inmediato)."""
        if clave == "S":
            return sum(1 for dd in self.dias if dd.es_sabado)
        if clave == "Sp":
            fin = datetime.date(self.anio, 12, 31)
            return sum(1 for dd in self.dias
                       if dd.es_sabado and dd.fecha + datetime.timedelta(days=5) <= fin)
        if clave == "D":
            return sum(1 for dd in self.dias if dd.es_domingo)
        if clave == "V":
            return sum(1 for dd in self.dias if dd.weekday == 4 and not dd.festivo)
        if clave == "J":
            return sum(1 for dd in self.dias if dd.es_jueves)
        if clave == "F":
            return sum(1 for dd in self.dias if dd.festivo and not dd.es_sabado)
        if clave == "LMX":
            return sum(1 for dd in self.dias if dd.weekday <= 2 and not dd.festivo)
        raise KeyError(clave)

    def celdas_equipo_especiales(self, modulos: int) -> dict[datetime.date, int]:
        """Celdas de EQUIPO de cada festivo especial (mitad/mitad, R12).

        Con 2 módulos, 1 celda de equipo por día y la otra es de área. Con 1
        módulo, los días de cada grupo alternan equipo/área empezando por
        equipo; los sábados y jueves especiales son siempre de equipo (pool S
        y su pareja sábado→jueves, R13).
        """
        salida: dict[datetime.date, int] = {}
        for grupo in ("NAV", "SS"):
            turno = 0
            for dd in self.dias:
                if dd.grupo_especial != grupo:
                    continue
                if modulos == 2 or dd.es_sabado or dd.es_jueves:
                    salida[dd.fecha] = 1
                else:
                    salida[dd.fecha] = 1 if turno == 0 else 0
                    turno ^= 1
        return salida

    def dias_de(self, clave: str) -> list[Dia]:
        """Días que forman el pool de una categoría del solver:
        'S' todos los sábados (emparejables), 'D' domingos ordinarios,
        'V' viernes ordinarios, 'F' festivos no sábado (excl. sáb-festivo),
        'LMX' lunes a miércoles no festivos, 'Jordinarios' jueves no festivos.
        """
        fin = datetime.date(self.anio, 12, 31)
        if clave == "S":
            return [dd for dd in self.dias
                    if dd.es_sabado and dd.fecha + datetime.timedelta(days=5) <= fin]
        if clave == "D":
            return [dd for dd in self.dias if dd.es_domingo and not dd.festivo]
        if clave == "V":
            return [dd for dd in self.dias if dd.weekday == 4 and not dd.festivo]
        if clave == "F":
            return [dd for dd in self.dias if dd.festivo and not dd.es_sabado]
        if clave == "LMX":
            return [dd for dd in self.dias if dd.weekday <= 2 and not dd.festivo]
        if clave == "Jordinarios":
            return [dd for dd in self.dias if dd.es_jueves and not dd.festivo]
        raise KeyError(clave)

    def festivo_del_dia(self, fecha: datetime.date) -> Dia | None:
        dd = self._pordia.get(fecha)
        return dd if (dd and dd.festivo) else None


def meses_del_anio() -> list[tuple[int, str]]:
    """[(1, 'ENERO'), …, (12, 'DICIEMBRE')] con la ortografía del modelo."""
    nombres = ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO",
               "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"]
    return list(zip(range(1, 13), nombres))


def dias_del_mes(anio: int, mes: int) -> list[datetime.date]:
    n = calendar.monthrange(anio, mes)[1]
    return [datetime.date(anio, mes, d) for d in range(1, n + 1)]
