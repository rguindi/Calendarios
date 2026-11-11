# -*- coding: utf-8 -*-
"""
M3 — Validación F7 del resultado (§5 del PLAN.md).

Comprueba todas las invariantes Rev. 2 sobre la asignación:

- cobertura exacta: cada día tiene exactamente `modulos` celdas
  (equipo + área + bolsa),
- equipo: exactamente 6/6/6 (sábados —incl. sábados-festivo—, domingos,
  viernes) y 6 jueves vía parejas (D9/R13),
- parejas: TODO sábado de equipo tiene su jueves +5 de la misma enfermera
  (incl. sábados festivos; §3.3/D11),
- descanso de 72 h: nada en −2/−1/+1…+4 de un sábado propio; un jueves propio
  nunca convive con su sábado +2,
- horas: todas las enfermeras de equipo ≤ objetivo (D10); desvío informado,
- sin guardias consecutivas en equipo (subsumidas en el descanso 72 h),
- equidad: dispersión de horas del área y festivos del equipo informados.
"""

from __future__ import annotations

import datetime

from .calendario import Calendario
from .cuotas import Cuotas
from .solver import Asignacion, Estado, reparto_proporcional


def _violacion_72h(fs: set[datetime.date], f: datetime.date) -> list[str]:
    """Días propios alrededor de `f` que violan la separación mínima:
    reglas por weekday (sábado: −2/−1/+1…+4; jueves: −1/+1/sábado+2; resto ±1)."""
    violas = []
    for g in fs:
        if g == f:
            continue
        k = (f - g).days
        wd = g.weekday()
        if wd == 5 and k in (-2, -1, 1, 2, 3, 4):
            violas.append(g.isoformat())
        elif wd == 3 and k in (-1, 1, 2):
            violas.append(g.isoformat())
        elif k in (-1, 1):
            violas.append(g.isoformat())
    return violas


def validar_resultado(cal: Calendario, asign: Asignacion, cuotas: Cuotas,
                      modulos: int, horas_equipo: int) -> tuple[bool, str]:
    """Devuelve (ok, informe). El informe resume; los fallos van a la cabeza."""
    fallos: list[str] = []
    fecha_de = datetime.date.fromisoformat

    eq_n = {n: {fecha_de(x) for x in ls} for n, ls in asign.equipo.items()}
    ar_n = {n: {fecha_de(x) for x in ls} for n, ls in asign.area.items()}
    bolsa = {(fecha_de(b["fecha"]), b["celda"]) for b in asign.bolsa}

    # --- cobertura: equipo + área + bolsa, sin duplicar celdas -----------------
    for dd in cal.dias:
        ocupadas = 0
        for fs in list(eq_n.values()) + list(ar_n.values()):
            if dd.fecha in fs:
                ocupadas += 1
        ocupadas += sum(1 for (f, _) in bolsa if f == dd.fecha)
        if ocupadas > modulos:
            fallos.append(f"{dd.fecha}: {ocupadas} ocupaciones para {modulos} celdas")

    # --- cuotas del equipo (mismo criterio de cómputo que el solver) ------------
    estados: dict[str, Estado] = {}
    for n, fs in eq_n.items():
        st = Estado()
        for f in fs:
            dia = cal.por_fecha(f)
            if dia is None:
                fallos.append(f"{f}: fecha fuera del año {cal.anio} (equipo {n})")
                continue
            st.put(dia)
        estados[n] = st
        if st.cont["S"] != cuotas.sabados:
            fallos.append(f"{n}: sábados {st.cont['S']} ≠ {cuotas.sabados} (D9)")
        if st.cont["D"] != cuotas.domingos:
            fallos.append(f"{n}: domingos {st.cont['D']} ≠ {cuotas.domingos}")
        if st.cont["V"] != cuotas.viernes:
            fallos.append(f"{n}: viernes {st.cont['V']} ≠ {cuotas.viernes}")
        if st.cont["J"] != cuotas.jueves:
            fallos.append(f"{n}: jueves {st.cont['J']} ≠ {cuotas.jueves} (parejas)")
        if st.horas > horas_equipo:
            fallos.append(f"{n}: horas {st.horas} > objetivo {horas_equipo} (D10)")

    # --- parejas sábado → jueves +5 (D11) ---------------------------------------
    fin = datetime.date(cal.anio, 12, 31)
    parejables = {dd.fecha for dd in cal.dias_de("S")}
    for n, fs in eq_n.items():
        for s in (f for f in fs if f.weekday() == 5):
            jt = s + datetime.timedelta(days=5)
            if s in parejables and s != fin and jt <= fin and jt not in fs:
                fallos.append(f"{n}: sábado {s} sin su jueves +5 ({jt})")

    # --- área: sin dos días seguidos + reparto proporcional por categorías ----
    cats_ar: dict[str, dict[str, int]] = {}
    for n, fs in ar_n.items():
        st_ar = Estado()
        for f in fs:
            st_ar.put(cal.por_fecha(f))
        cats_ar[n] = st_ar.cont
        for f in fs:
            if f + datetime.timedelta(days=1) in fs:
                fallos.append(f"{n}: dos días seguidos ({f.isoformat()} y "
                              f"+1, área)")
    if len(cats_ar) > 1 and not reparto_proporcional(cats_ar):
        # señala la categoría desequilibrada para el informe
        for clave in ("S", "D", "V", "J", "F", "LMX"):
            valores = [c[clave] for c in cats_ar.values()]
            if max(valores) >= 8 and min(valores) * 10 < max(valores) * 7:
                fallos.append(f"área: reparto desproporcionado de {clave} "
                              f"({min(valores)}–{max(valores)})")

    # --- descanso de 72 h (D11) --------------------------------------------------
    for n, fs in eq_n.items():
        for f in fs:
            malas = _violacion_72h(fs, f)
            if malas:
                fallos.append(f"{n}: guardias mal separadas alrededor de "
                              f"{f.isoformat()} → {malas}")

    # --- informe ------------------------------------------------------------------
    horas_eq = {n: estados[n].horas for n in asign.equipo}
    horas_ar = {n: sum(cal.por_fecha(f).horas for f in fs) for n, fs in ar_n.items()}
    partes = []
    if horas_eq:
        desvio_min = min(horas_equipo - h for h in horas_eq.values())
        partes.append(f"equipo: {len(horas_eq)} enfermeras, "
                      f"{min(horas_eq.values())}–{max(horas_eq.values())} h "
                      f"(desvío {desvio_min} h respecto de {horas_equipo} h)")
    partes.append(f"bolsa: {len(asign.bolsa)} celdas, "
                  f"{sum(b['horas'] for b in asign.bolsa)} h")
    if horas_ar:
        dispersion = max(horas_ar.values()) - min(horas_ar.values())
        partes.append(f"área: {min(horas_ar.values())}–{max(horas_ar.values())} h "
                      f"(dispersión {dispersion} h)")
    msg = " · ".join(partes)
    if fallos:
        return False, "FALLOS: " + " | ".join(fallos[:12]) + " ‖ " + msg
    return True, msg
