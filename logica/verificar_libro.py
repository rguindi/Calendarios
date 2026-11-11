# -*- coding: utf-8 -*-
"""
Verificación del libro generado (§9.4): emula las fórmulas del Excel
(COUNTIF × T × W) leyendo el XLSX escrito, y compara los valores emulados
con lo que el solver dice que asignó (fuente de verdad).

Port de `referencia/verificar_2027.py` a cualquier año/entrada.

Devuelve una lista de errores (vacía ⇒ libro correcto).
"""

from __future__ import annotations

import datetime
import re
from collections import Counter

from openpyxl import load_workbook
from openpyxl.utils import column_index_from_string

from .calendario import Calendario
from .generador import (FILA_INICIO_RESUMEN, COL_INICIO_ESTADISTICAS,
                        col_de_weekday, name_fila_bloque)
from .solver import Asignacion


# ---------------------------------------------------------------------------
# Emulación de fórmulas
# ---------------------------------------------------------------------------

def _valores_rango(rng: str, ws) -> list:
    """$K5:$K9 → lista de valores de las celdas del rango."""
    m = re.match(r"\$?([A-Z]+)\$?(\d+):\$?([A-Z]+)\$?(\d+)", rng.strip())
    if not m:
        raise ValueError(f"Rango no reconocido: {rng!r}")
    c1, r1, c2, r2 = (column_index_from_string(m.group(1)), int(m.group(2)),
                      column_index_from_string(m.group(3)), int(m.group(4)))
    salida = []
    for cc in range(min(c1, c2), max(c1, c2) + 1):
        for rr in range(min(r1, r2), max(r1, r2) + 1):
            salida.append(ws.cell(row=rr, column=cc).value)
    return salida


def _criterio(exp: str, ws):
    """Resuelve el criterio: `$B79` → valor de esa celda; `"Vacío"` → literal."""
    exp = exp.strip()
    m = re.match(r"\$?([A-Z]+)\$?(\d+)$", exp)
    if m:
        return ws.cell(row=int(m.group(2)),
                       column=column_index_from_string(m.group(1))).value
    if exp.startswith('"') and exp.endswith('"'):
        return exp[1:-1]
    return exp


def emular_formula(ws, formula) -> int:
    """Suma de todos los COUNTIF(rango, criterio) de una fórmula generada."""
    formula = str(formula)
    total = 0
    for rng, exp in re.findall(r"COUNTIF\(([^,]+),\s*([^)]+)\)", formula):
        crit = _criterio(exp, ws)
        for v in _valores_rango(rng, ws):
            if v is not None and str(v).strip().upper() == \
                    str(crit).strip().upper():
                total += 1
    return total


# ---------------------------------------------------------------------------
# Esperados (desde la asignación, fuente de verdad)
# ---------------------------------------------------------------------------

def _sets_personas(asign: Asignacion) -> dict[str, set[datetime.date]]:
    salida = {}
    for nombre, fechas in list(asign.equipo.items()) + list(asign.area.items()):
        salida[nombre] = {datetime.date.fromisoformat(x) for x in fechas}
    return salida


def _esperado_resumen(cal: Calendario, asign: Asignacion) -> dict[str, dict]:
    """Por persona: contadores del resumen anual (§6.2, quirk incluido)."""
    sets_p = _sets_personas(asign)
    salida: dict[str, dict] = {}
    for nombre, fs in sets_p.items():
        c: dict[str, int] = {"L": 0, "M": 0, "X": 0, "J": 0, "V": 0,
                             "S": 0, "D": 0, "NF": 0, "O_": 0, "P_": 0,
                             "Q_": 0, "R_": 0}
        for dd in cal.dias:
            if dd.fecha not in fs:
                continue
            if dd.festivo:
                md = (dd.fecha.month, dd.fecha.day)
                if md == (12, 24):
                    c["P_"] += 1       # 24/12: solo columna P (fuera de N)
                elif md == (12, 31):
                    c["R_"] += 1       # 31/12: solo columna R (fuera de N)
                else:
                    c["NF"] += 1       # N = festivos menos 24/12 y 31/12
                    if md == (1, 1):
                        c["O_"] += 1
                    elif md == (12, 25):
                        c["Q_"] += 1
            else:
                wd = dd.weekday
                if wd <= 4:
                    c["LMXJV"[wd]] += 1
                elif wd == 5:
                    c["S"] += 1
                else:
                    c["D"] += 1
        horas = (17 * (c["L"] + c["M"] + c["X"] + c["J"] + c["V"])
                 + 24 * (c["S"] + c["D"] + c["NF"] + c["P_"] + c["R_"]))
        guardias = c["L"] + c["M"] + c["X"] + c["J"] + c["V"] + c["S"] \
            + c["D"] + c["NF"] + c["P_"] + c["R_"]
        salida[nombre] = {**c, "horas": horas, "guardias": guardias}
    return salida


# ---------------------------------------------------------------------------
# Verificación completa
# ---------------------------------------------------------------------------

def verificar_libro(ruta_o_wb, cal: Calendario, asign: Asignacion,
                    modulos: int) -> list[str]:
    """Comprueba el libro contra la asignación. Devuelve lista de errores."""
    wb = ruta_o_wb
    if isinstance(wb, (str, bytes)):
        wb = load_workbook(wb)
    ws = wb.worksheets[0]
    errores: list[str] = []
    resumen_esperado = _esperado_resumen(cal, asign)
    sets_p = _sets_personas(asign)
    nombres = list(sets_p)

    # ---- 1) letras del calendario ----------------------------------------
    bolsa_por: dict[str, int] = {}
    for b in asign.bolsa:
        bolsa_por[b["fecha"]] = bolsa_por.get(b["fecha"], 0) + 1
    # días CONSECUTIVOS desde la columna del primer día del maestre (modelo §6.1)
    col0_de: dict[int, int] = {}
    for mes in range(1, 13):
        d1 = datetime.date(cal.anio, mes, 1)
        col0_de[mes] = col_de_weekday(cal.por_fecha(d1).weekday)
    for dd in cal.dias:
        mes = dd.fecha.month
        nf = name_fila_bloque(mes)
        col = col0_de[mes] + (dd.fecha.day - 1)
        # número del día en su columna
        num = ws.cell(row=nf + 1, column=col).value
        if num != dd.fecha.day:
            errores.append(f"{dd.fecha}: número {num!r} ≠ "
                           f"{dd.fecha.day} (col {col})")
        # nombres presentes en las filas de guardias (team..aux2)
        esperado: Counter = Counter(n for n in nombres
                                    if dd.fecha in sets_p[n])
        vacios = bolsa_por.get(dd.fecha.isoformat(), 0)
        if vacios:                       # celdas sin cubrir → bolsa «Vacío»
            esperado["Vacío"] += vacios
        con_letra = [v for r in range(nf + 2, nf + 6)
                     if (v := ws.cell(row=r, column=col).value) is not None]
        if Counter(con_letra) != esperado:
            errores.append(f"{dd.fecha}: celdas {dict(Counter(con_letra))} "
                           f"≠ {dict(esperado)} (col {col})")
        if len(con_letra) != len(list(esperado.elements())):
            errores.append(f"{dd.fecha}: cobertura incompleta "
                           f"({len(con_letra)} letras)")

    # ---- 2) tripleta mensual 17/24/T por persona --------------------------
    for i, nombre in enumerate(nombres):
        col0 = COL_INICIO_ESTADISTICAS + 3 * i      # AR + 3·i
        fs = sets_p[nombre]
        for mes in range(1, 13):
            nf = name_fila_bloque(mes)
            e17 = sum(1 for dd in cal.dias if dd.fecha.month == mes
                      and dd.fecha in fs and dd.horas == 17)
            e24 = sum(1 for dd in cal.dias if dd.fecha.month == mes
                      and dd.fecha in fs and dd.horas == 24)
            f17 = emular_formula(ws, ws.cell(row=nf + 2, column=col0).value or 0)
            f24 = emular_formula(ws,
                                 ws.cell(row=nf + 2, column=col0 + 1).value or 0)
            if f17 != e17 or f24 != e24:
                errores.append(
                    f"Estadísticas {nombre} mes {mes}: emulado "
                    f"(17={f17}, 24={f24}) ≠ esperado (17={e17}, 24={e24})")

    # ---- 3) resumen anual: fórmulas emuladas vs esperado ------------------
    mapa = [("F", "L"), ("G", "M"), ("H", "X"), ("I", "J"), ("J", "V"),
            ("K", "S"), ("L", "D"), ("N", "NF")]
    mapa_f = {"O": "O_", "P": "P_", "Q": "Q_", "R": "R_"}
    fila = FILA_INICIO_RESUMEN + 1
    for nombre in sorted(nombres):
        esp = resumen_esperado[nombre]
        evals: dict[str, int] = {}
        for col_l, clave in mapa + list(mapa_f.items()):
            v = emular_formula(ws, ws[f"{col_l}{fila}"].value or 0)
            evals[col_l] = v
            if v != esp[clave]:
                errores.append(f"Resumen {nombre} {col_l} ({clave}): "
                               f"emulado {v} ≠ {esp[clave]}")
        t = str(ws[f"T{fila}"].value or "")
        if "17" not in t or "24" not in t:
            errores.append(f"Resumen {nombre} T{fila}: fórmula sin 17/24: {t!r}")
        # W = SUM(F:L) + SUM(R) + SUM(N) + SUM(P): evaluamos con los contadores
        guardias_emulado = sum(evals[k] for k in ("F", "G", "H", "I", "J",
                                                  "K", "L", "N", "P", "R"))
        if guardias_emulado != esp["guardias"]:
            errores.append(f"Resumen {nombre} W{fila}: {guardias_emulado} ≠ "
                           f"{esp['guardias']} guardias")
        fila += 1

    # ---- 4) fila SUMA ------------------------------------------------------
    fila_suma = fila + 1
    if str(ws[f"B{fila_suma}"].value or "").strip().upper() != "SUMA":
        errores.append(f"B{fila_suma}: no es la fila SUMA")
        return errores
    # las celdas son =SUM(...): evaluamos columna a columna por persona
    for col_l, clave in mapa + list(mapa_f.items()):
        emulado = sum(emular_formula(ws, ws[f"{col_l}{r}"].value or 0)
                      for r in range(FILA_INICIO_RESUMEN + 1, fila))
        esperado = sum(resumen_esperado[n][clave] for n in nombres)
        if emulado != esperado:
            errores.append(f"SUMA {col_l}{fila_suma}: {emulado} ≠ {esperado}")
    esperado_h = sum(resumen_esperado[n]["horas"] for n in nombres)
    esperado_g = sum(resumen_esperado[n]["guardias"] for n in nombres)
    # columnas T y W: derivadas de los contadores evaluados por persona
    t_emulado = g_emulado = 0
    for r in range(FILA_INICIO_RESUMEN + 1, fila):
        evals_r = {k: emular_formula(ws, ws[f"{k}{r}"].value or 0)
                   for k in ("F", "G", "H", "I", "J", "K", "L", "N", "P", "R")}
        g_emulado += sum(evals_r.values())
        t_emulado += (17 * (evals_r["F"] + evals_r["G"] + evals_r["H"]
                            + evals_r["I"] + evals_r["J"])
                      + 24 * (evals_r["K"] + evals_r["L"] + evals_r["N"]
                              + evals_r["P"] + evals_r["R"]))
    if t_emulado != esperado_h:
        errores.append(f"SUMA T{fila_suma}: {t_emulado} ≠ {esperado_h}")
    if g_emulado != esperado_g:
        errores.append(f"SUMA W{fila_suma}: {g_emulado} ≠ {esperado_g}")

    # ---- 5) cobertura de celdas: días × módulos ----------------------------
    dias_con_celda = sum(len(sets_p[n]) for n in nombres) + len(asign.bolsa)
    dias_anio = cal.n_dias if hasattr(cal, "n_dias") else \
        (366 if cal.anio % 4 == 0 and (cal.anio % 100 or cal.anio % 400 == 0)
         else 365)
    if dias_con_celda != dias_anio * modulos:
        errores.append(f"Cobertura global: {dias_con_celda} celdas ≠ "
                       f"{dias_anio * modulos}")
    return errores
