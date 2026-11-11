# -*- coding: utf-8 -*-
"""
Contrato de la lógica de negocio (§11 del PLAN.md).

- `validar(parametros) -> str | None`: validación de entrada (D13: fechas fuera
  del año elegido, festivos duplicados, módulos ≠ {1, 2}, horas negativas y
  factibilidad 6/6/6 — R13 sobre los sábados/domingos/viernes del año).
- `procesar(parametros) -> Resultado`: resolver el plan, generar el libro Excel
  con la maqueta del modelo y verificarlo emulando sus fórmulas (§9.4).

`ok=True` aunque haya horas sin cubrir (eso se informa en `mensaje`, no es error).
"""

from __future__ import annotations

import datetime
import collections
import io
from dataclasses import dataclass

from .calendario import Calendario
from .cuotas import factibilidad
from .festivos_precarga import mezclar
from .generador import GeneradorExcel
from .solver import categoria_dia, resolver_plan
from .validar_resultado import validar_resultado
from .verificar_libro import verificar_libro

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


@dataclass
class Resultado:
    """Resultado estandarizado que debe devolver `procesar`."""

    ok: bool
    """True si el proceso terminó correctamente (horas sin cubrir NO es error)."""

    mensaje: str
    """Informe para mostrar al usuario: horas sin cubrir, bolsa, desvíos, avisos."""

    contenido: bytes | None = None
    """Contenido binario del Excel resultante (xlsx), o None."""

    archivo: str | None = None
    """Nombre sugerido del archivo para descargar."""


# ---------------------------------------------------------------------------
# Validación de entrada (§11)
# ---------------------------------------------------------------------------

DIAS_NOMBRE = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado",
               "domingo"]


def _coercion_int(opcion) -> int | None:
    if isinstance(opcion, bool):
        return None
    if isinstance(opcion, int):
        return opcion
    if isinstance(opcion, float):
        return int(opcion) if opcion == int(opcion) else None
    if isinstance(opcion, str):
        try:
            return int(opcion.strip())
        except ValueError:
            return None
    return None


def _leer_fechas(paquetes) -> list[datetime.date] | str:
    """Lista de fechas desde ISO strings (front) u objetos date; devuelve str
    como mensaje de error si algo no encaja."""
    if not isinstance(paquetes, (list, tuple)):
        return "Los festivos deben llegar como una lista."
    salida: list[datetime.date] = []
    for x in paquetes:
        if isinstance(x, datetime.date):
            salida.append(x)
        elif isinstance(x, str):
            try:
                salida.append(datetime.date.fromisoformat(x.strip()))
            except ValueError:
                return f"Fecha de festivo no válida: «{x}»."
        else:
            return f"Fecha de festivo no válida: «{x}»."
    return salida


def validar(parametros: dict) -> str | None:
    """None = OK; str = mensaje de error."""
    if not isinstance(parametros, dict):
        return "Parámetros no reconocidos."

    # --- año (D13) ---------------------------------------------------------
    anio = _coercion_int(parametros.get("anio"))
    if anio is None:
        return "El año no es válido."
    if not (2020 <= anio <= 2100):
        return f"El año debe estar entre 2020 y 2100 (recibido: {anio})."

    # --- plantilla -----------------------------------------------------------
    n_eq = _coercion_int(parametros.get("enfermeras", 0)) or 0
    n_ar = _coercion_int(parametros.get("enfermeras_area", 0)) or 0
    if n_eq < 0:
        return "El número de enfermeras de equipo no puede ser negativo."
    if n_ar < 0:
        return "El número de enfermeras de área no puede ser negativo."
    if n_eq == 0 and n_ar == 0:
        return "Introduce al menos una enfermera (de equipo o de área)."

    # --- módulos de guardia --------------------------------------------------
    modulos = _coercion_int(parametros.get("modulos_guardia", 0))
    if modulos is None or modulos not in (1, 2):
        return "Los módulos de guardia deben ser 1 o 2."

    # --- horas ---------------------------------------------------------------
    for clave in ("horas_equipo", "horas_area"):
        horas = _coercion_int(parametros.get(clave, 0))
        if horas is None or horas < 0:
            return "Las horas objetivo no pueden ser negativas."

    # --- festivos ------------------------------------------------------------
    festivos = _leer_fechas(parametros.get("festivos", []))
    if isinstance(festivos, str):
        return festivos
    fest_set: dict[datetime.date, int] = {}
    for f in festivos:
        fest_set[f] = fest_set.get(f, 0) + 1
    duplicados = sorted(f for f, n in fest_set.items() if n > 1)
    if duplicados:
        return ("Festivos duplicados: " +
                ", ".join(d.isoformat() for d in duplicados) + ".")
    fuera = sorted(f for f in festivos if f.year != anio)
    if fuera:
        otros = sorted({f.year for f in fuera})
        return ("Hay festivos de otro año (D13: todos deben ser del "
                f"{anio}). Corrige "
                + ", ".join(d.isoformat() for d in fuera[:5])
                + ("…" if len(fuera) > 5 else "")
                + f" (años: {', '.join(map(str, otros))}).")

    # --- factibilidad 6/6/6 (R13) -------------------------------------------
    cal = Calendario(anio, festivos)
    ok, msg = factibilidad(cal, n_eq, modulos)
    if not ok:
        return msg
    return None


# ---------------------------------------------------------------------------
# Procesar
# ---------------------------------------------------------------------------

def _plural(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def _area_bloquea(cal, asign, horas_area: int) -> bool:
    """True si las celdas sin cubrir se deben a las reglas del área (objetivo
    de horas y no trabajar dos días seguidos): ninguna enfermera de área
    puede tomar ninguna de esas celdas sin romper una de las dos."""
    if not asign.area:
        return False
    ar = {n: ({datetime.date.fromisoformat(f) for f in fs},
              sum(cal.por_fecha(datetime.date.fromisoformat(f)).horas
                  for f in fs))
          for n, fs in asign.area.items()}
    for b in asign.bolsa:
        dd = cal.por_fecha(datetime.date.fromisoformat(b["fecha"]))
        for fs, h in ar.values():
            cabe_horas = horas_area <= 0 or h + dd.horas <= horas_area
            if cabe_horas and (dd.fecha - datetime.timedelta(days=1) not in fs
                               and dd.fecha + datetime.timedelta(days=1)
                               not in fs):
                return False       # alguna cabría: el bloqueo es otra cosa
    return True


def _informe(asign, cuotas, cal, n_ar, horas_area, modulos,
             n_oficiales: int = 0, n_propios: int = 0) -> str:
    """Informe final para el front (§11), en Markdown (st.success lo pinta).

    Estructura: cabecera · equipo · área · horas sin cubrir · avisos
    (falta de personal, exceso de personal, festivos con reparto no exacto)."""
    anio = cal.anio
    lineas: list[str] = []

    # --- cabecera -------------------------------------------------------------
    lineas.append(f"### 📅 Calendario {anio} generado")
    lineas.append(
        f"**{modulos} módulo{'s' if modulos != 1 else ''} de guardia** · "
        f"**{len(cal.festivos)} festivos** "
        f"({n_oficiales} oficiales Estado/CL precargados · "
        f"{n_propios} propios)")

    # --- equipo -----------------------------------------------------------------
    if asign.equipo:
        horas_eq = {n: sum(cal.por_fecha(datetime.date.fromisoformat(f)).horas
                           for f in fs)
                    for n, fs in asign.equipo.items()}
        hmin, hmax = min(horas_eq.values()), max(horas_eq.values())
        gmin, gmax = (min(len(fs) for fs in asign.equipo.values()),
                      max(len(fs) for fs in asign.equipo.values()))
        lineas.append(f"\n**{_plural(len(asign.equipo), 'enfermera', 'enfermeras')} de equipo**")
        if hmin == hmax and gmin == gmax:
            estado = "✔" if hmin <= cuotas.objetivo else "⚠"
            lineas.append(f"{estado} Cada enfermera hace **{gmin} guardias / "
                          f"{hmin} h** (objetivo {cuotas.objetivo} h).")
        else:
            lineas.append(f"⚠ Horas {hmin}–{hmax} h y guardias {gmin}–{gmax} "
                          f"(objetivo {cuotas.objetivo} h): revisa el aviso "
                          f"de festivos más abajo.")
        lineas.append(
            f"Cuota fija **{cuotas.sabados} S · {cuotas.domingos} D · "
            f"{cuotas.viernes} V · {cuotas.jueves} J** + {cuotas.festivos} "
            f"festivo{'s' if cuotas.festivos != 1 else ''} + {cuotas.lmx} LMX.")
        if cuotas.desvio:
            lineas.append(f"Desvío del objetivo: **{cuotas.desvio} h** por "
                          f"enfermera.")

    # --- área --------------------------------------------------------------------
    if asign.area:
        horas_ar = [sum(cal.por_fecha(datetime.date.fromisoformat(f)).horas
                        for f in fs) for fs in asign.area.values()]
        total_ar = sum(horas_ar)
        media = total_ar // len(horas_ar) if horas_ar else 0
        lineas.append(f"\n**Área · {_plural(len(asign.area), 'enfermera', 'enfermeras')}**")
        if horas_area > 0:
            lineas.append(
                f"**{total_ar} h** en total ({min(horas_ar)}–{max(horas_ar)} h "
                f"por enfermera, media {media} h · objetivo {horas_area} h, "
                f"siempre por debajo). Cubren las celdas libres sin pasarse "
                f"del objetivo.")
        else:
            lineas.append(
                f"**{total_ar} h** en total ({min(horas_ar)}–{max(horas_ar)} h "
                f"por enfermera, media {media} h) · sin objetivo de horas: "
                f"cubren todas las celdas libres.")
        # reparto proporcional por categorías (S/D/V/J/F/LMX)
        splits = []
        for n, fs in asign.area.items():
            fset = {datetime.date.fromisoformat(x) for x in fs}
            cont = collections.Counter(
                categoria_dia(cal.por_fecha(x)) for x in fset)
            splits.append(f"{n} " + "·".join(str(cont.get(k, 0))
                                             for k in ("S", "D", "V", "J", "F", "LMX")))
        lineas.append("Reparto proporcional S·D·V·J·F·LMX: " + " | ".join(splits) + ".")

    # --- horas sin cubrir (falta de personal o tope del área) ---------------------
    total_celdas = (365 + (1 if anio % 4 == 0 and (anio % 100 or anio % 400 == 0)
                           else 0)) * modulos
    if asign.bolsa:
        cs = sorted({b["fecha"] for b in asign.bolsa})
        htotal = sum(b["horas"] for b in asign.bolsa)
        muestra = ", ".join(c[5:] for c in cs[:6])
        if _area_bloquea(cal, asign, horas_area):
            obj = (f"objetivo de {horas_area} h" if horas_area > 0
                   else "sin objetivo de horas")
            causa = (
                f"Las **reglas del área limitan la cobertura** ({obj} y no "
                f"trabajar dos días seguidos): ninguna enfermera de área "
                f"puede tomar estas celdas sin pasarse del objetivo o quedar "
                f"dos días seguidos. Si quieres cubrirlas, sube el objetivo "
                f"de horas del área o asigna estas celdas a mano.")
        else:
            causa = (
                "No es posible cubrir todas las guardias del año con esta "
                "plantilla (falta de personal).")
        lineas.append(
            f"\n### ⚠ Horas sin cubrir\n"
            f"{causa} Quedan **{len(asign.bolsa)} "
            f"celdas / {htotal} h** de las {total_celdas} del calendario, "
            f"marcadas en morado como bolsa «Vacío» para repartir a mano.\n\n"
            f"Días con celdas vacías ({len(cs)}): {muestra}"
            f"{'…' if len(cs) > 6 else ''}")
    else:
        lineas.append(f"\n✔ **Sin horas sin cubrir**: las {total_celdas} "
                      f"celdas del año están cubiertas.")

    # --- exceso de personal ---------------------------------------------------------
    if asign.equipo and not asign.bolsa and cuotas.desvio > 0:
        lineas.append(
            f"⚠ **Exceso de personal para este calendario**: con {len(asign.equipo)} "
            f"enfermeras de equipo cada una queda en {hmax} h, **{cuotas.desvio} h "
            f"por debajo** del objetivo ({cuotas.objetivo} h) — el año no ofrece "
            f"más guardias repartibles (cap de {cuotas.lmx} guardias LMX por "
            f"enfermera). Sube el objetivo de horas o reduce plantilla.")

    # --- festivos con reparto no exacto ------------------------------------------------
    if asign.equipo:
        fest_n = {n: sum(1 for f in fs
                         if cal.por_fecha(datetime.date.fromisoformat(f)).festivo
                         and cal.por_fecha(datetime.date.fromisoformat(f)).weekday != 5)
                  for n, fs in asign.equipo.items()}
        fmin, fmax = min(fest_n.values()), max(fest_n.values())
        if fmin != fmax:
            con_mas = ", ".join(n for n, c in fest_n.items() if c == fmax)
            n_mas = len(con_mas)
            lineas.append(
                f"⚠ **Reparto de festivos no exacto**: {fmin}–{fmax} "
                f"festivo{'s' if fmax != 1 else ''} por enfermera "
                f"(la división entre {len(fest_n)} no es exacta). "
                f"**{con_mas}** {'tienen' if n_mas > 1 else 'tiene'} un "
                f"festivo más por ser imposible la división exacta.")

    # --- avisos -------------------------------------------------------------------------
    if cuotas.avisos:
        lineas.append("\n**Avisos**")
        for aviso in cuotas.avisos:
            lineas.append(f"- ⚠ {aviso}")
    return "\n".join(lineas)


def procesar(parametros: dict) -> Resultado:
    """Punto de entrada: resolver → generar → verificar (§9.4) → devolver."""
    error = validar(parametros)
    if error:
        return Resultado(ok=False, mensaje=error)

    anio = _coercion_int(parametros["anio"])
    # D2/D6: la precarga de festivos la hace el backend — se mezcla lo
    # declarado por el usuario con los oficiales del año (nunca se elimina).
    usuario = _leer_fechas(parametros.get("festivos", []))
    festivos, n_oficiales, n_propios = mezclar(usuario, anio)
    n_eq = _coercion_int(parametros["enfermeras"]) or 0
    n_ar = _coercion_int(parametros["enfermeras_area"]) or 0
    modulos = _coercion_int(parametros["modulos_guardia"])
    horas_equipo = _coercion_int(parametros.get("horas_equipo", 0)) or 0
    horas_area = _coercion_int(parametros.get("horas_area", 0)) or 0

    cal = Calendario(anio, festivos)
    asign, err, cuotas = resolver_plan(cal, n_eq, n_ar, modulos, horas_equipo,
                                       horas_area)
    if err:
        return Resultado(ok=False, mensaje=err)
    assert asign is not None

    ok_v, informe_v = validar_resultado(cal, asign, cuotas, modulos,
                                        horas_equipo)
    if not ok_v:
        detalle = informe_v.replace("FALLOS: ", "").replace(" ‖ ", "\n")
        return Resultado(
            ok=False,
            mensaje="⚠ No se pudo completar el calendario respetando todas "
                    "las reglas (la plantilla está justo al límite de "
                    "capacidad del año):\n\n" + detalle
                    + "\n\nPrueba con menos enfermeras de equipo o más "
                      "módulos de guardia.")

    wb = GeneradorExcel(cal, asign, n_eq, n_ar, modulos).construir()
    fallos_libro = verificar_libro(wb, cal, asign, modulos)
    if fallos_libro:
        return Resultado(
            ok=False,
            mensaje="El libro generado no supera la verificación de fórmulas "
                    "(§9.4):\n" + "\n".join(f"- {e}" for e in fallos_libro[:10]))

    bufer = io.BytesIO()
    wb.save(bufer)
    extra = ("\n\n✔ *Reglas verificadas: cuota 6/6/6, parejas sábado→jueves+5, "
             "descanso de 72 h y horas ≤ objetivo.*"
             if ok_v else "")
    return Resultado(
        ok=True,
        mensaje=_informe(asign, cuotas, cal, n_ar, horas_area, modulos,
                         n_oficiales=n_oficiales, n_propios=n_propios) + extra,
        contenido=bufer.getvalue(),
        archivo=f"Calendario {anio}.xlsx",
    )
