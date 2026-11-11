# -*- coding: utf-8 -*-
"""
M6 — Precarga de festivos nacionales y de Castilla y León (D2/D6).

La precarga se ORIGINA en el backend: cuando el usuario declara festivos,
se mezclan con los oficiales del año (nacionales + autonómicos de CyL) más
los especiales del modelo (24 y 31 de diciembre). Los locales (p. ej. 17/5 o
29/6) los añade el usuario y nunca se eliminan.

Con el paquete `holidays` disponible se usa su calendario oficial
(por ejemplo, cuando 15/8 cae en domingo se traslada); sin él, un fallback
estático con la Pascua calculada por Butcher.

`festivos_precargados(anio) -> list[datetime.date]` (ordenada, sin duplicados).
"""

from __future__ import annotations

import datetime

from .calendario import domingo_pascua

# fijos de todo el Estado + fiesta autonómica de Castilla y León (23/4)
FIJOS_ES_CL = {(1, 1), (1, 6), (4, 23), (5, 1), (8, 15), (10, 12), (11, 1),
               (12, 6), (12, 8), (12, 25)}

# especiales del modelo (morado oscuro): víspera de Navidad y San Silvestre
ESPECIALES = {(12, 24), (12, 31)}


def _estaticos(anio: int) -> list[datetime.date]:
    """Fallback sin `holidays`: fijos + Jueves/Viernes Santo (Butcher)."""
    fechas = {datetime.date(anio, m, d) for (m, d) in FIJOS_ES_CL | ESPECIALES}
    pascua = domingo_pascua(anio)
    fechas.add(pascua - datetime.timedelta(days=2))   # Jueves Santo
    fechas.add(pascua - datetime.timedelta(days=1))   # Viernes Santo
    return sorted(fechas)


def festivos_precargados(anio: int) -> list[datetime.date]:
    """Festivos oficiales nacionales + Castilla y León + 24/12 y 31/12."""
    salida: set[datetime.date] = {
        datetime.date(anio, m, d) for (m, d) in ESPECIALES}
    try:
        import holidays
        cal = holidays.country_holidays("ES", subdiv="CL", years=[anio])
        salida.update(d for d in cal.keys())
    except Exception:
        salida.update(_estaticos(anio))
    return sorted(salida)


def mezclar(festivos_usuario: list[datetime.date],
            anio: int) -> tuple[list[datetime.date], int, int]:
    """Une lo declarado con la precarga.

    Devuelve (lista final ordenada, nº oficiales precargados presentes,
    nº de festivos propios del usuario no cubiertos por la precarga)."""
    precarga = set(festivos_precargados(anio))
    usuario = set(festivos_usuario)          # ya validadas: todas del año
    final = sorted(usuario | precarga)
    return final, len(precarga), len(usuario - precarga)
