# -*- coding: utf-8 -*-
"""
M4 — Generador del libro Excel del calendario (§6 del PLAN.md).

Construye el libro POR CÓDIGO con openpyxl para cualquier año (D4),
replicando la maqueta del modelo 2027:

- 12 bloques de mes (nombre + números de día + fila equipo + fila área + 2 aux),
  columnas E–AN fijas por día de la semana (E=miércoles … K=martes),
- estadísticas mensuales por enfermera (tripletas 17/24/T con COUNTIF),
- bloque de resumen anual (L,M,X,J,V,S,D,F,01.01,24.12,25.12,31.12,Horas,Guardias)
  con el QUIRK de §6.2: un festivo no cuenta en la columna de su día de la
  semana (se excluyen los segmentos de las celdas de los días festivos),
- festivos pintados en NARANJA (especiales en naranja oscuro, D12) y «Vacío»
  de bolsa en MORADO (única celda morada, D5),
- una hoja de detalle por enfermera (D7).
"""

from __future__ import annotations

import datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .calendario import Calendario, dias_del_mes, meses_del_anio
from .solver import Asignacion

# --- paleta Rev. 3 (D12 revisado: festivos naranjas, bolsa morada) ---------
NARANJA_FESTIVO = "FFFFC000"        # festivo normal
NARANJA_FESTIVO_OSCURO = "FFC55A11" # festivo especial (1/1, Semana Santa, 24-31/12)
MORADO_BOLSA = "FFC9A0DC"           # celda «Vacío» de la bolsa (sin cubrir)
GRIS_FINDISM = "FFD9D9D9"    # sombreado sábados/domingos (tema th0 tint −0.15)
GRIS_T = "FFD9D9D9"          # celda «T» de horas
GRIS_MES = "FFE8E8E8"        # banda del nombre de mes (tema lt2)
BLANCO = "FFFFFFFF"          # fondo sólido que oculta la cuadrícula

# Maqueta de filas (§6.1)
FILA_TITULO = 1
FILA_CABECERA_ESTAD = 1      # fila 1 letras, fila 2 «17 24 T»
FILA_CODIGOS_ESTAD = 2
FILA_NOMBRES_DIA = 3
FILA_PRIMER_BLOQUE = 4       # bloques 1-6 desde la fila 4; 7-12 desde la 41
FILA_PRIMER_BLOQUE_2 = 41
FILA_INICIO_RESUMEN = 78

COL_INICIO_CALENDARIO = 5    # E = miércoles
COL_FIN_CALENDARIO = 41      # hasta AN (mes martes+31 días llega a la 41 = AO)
COL_INICIO_ESTADISTICAS = 44  # AR
COL_RESUMEN_NOMBRE = 2       # B

FONT_GUARDIAS = Font(name="Calibri", size=11)
FONT_CELDA = Font(name="Calibri", size=11)
FONT_NUM = Font(name="Calibri", size=14)
FONT_TITULO = Font(name="Calibri", size=22, bold=True)
FONT_MES = Font(name="Calibri", size=13, bold=True)
FONT_DIA = Font(name="Calibri", size=13)
FONT_ESTAD = Font(name="Calibri", size=10)
FONT_LETRA_ESTAD = Font(name="Calibri", size=20, bold=True)
FONT_RESUMEN = Font(name="Calibri", size=14)
FONT_CAB_RESUMEN = Font(name="Calibri", size=14)

BORDE_THIN = Side(style="thin")
BORDE_MED = Side(style="medium")
CAJA = Border(left=BORDE_THIN, right=BORDE_THIN, top=BORDE_THIN, bottom=BORDE_THIN)
BORDE_NUM = Border(left=BORDE_THIN, right=BORDE_THIN, bottom=BORDE_THIN)
BORDE_MES = Border(bottom=BORDE_THIN)
CAJA_IZQ = Border(left=BORDE_MED)               # marco lateral izquierdo
CAJA_DER = Border(right=BORDE_MED)              # marco lateral derecho
CAJA_IZQ_FIN = Border(left=BORDE_MED, right=BORDE_THIN,
                      top=BORDE_THIN, bottom=BORDE_THIN)
CAJA_DER_FIN = Border(left=BORDE_THIN, right=BORDE_MED,
                      top=BORDE_THIN, bottom=BORDE_THIN)
CAJA_CAB = Border(left=BORDE_THIN, right=BORDE_THIN,
                  top=BORDE_MED, bottom=BORDE_THIN)
CENTRO_C = Alignment(horizontal="center", vertical="center")

# fills compartidos (los estilos de openpyxl se pueden reutilizar entre celdas)
FILL_BLANCO = PatternFill("solid", start_color=BLANCO)
FILL_FINDISM = PatternFill("solid", start_color=GRIS_FINDISM)
FILL_MES = PatternFill("solid", start_color=GRIS_MES)
FILL_NARANJA = PatternFill("solid", start_color=NARANJA_FESTIVO)
FILL_OSCURO = PatternFill("solid", start_color=NARANJA_FESTIVO_OSCURO)
FILL_MORADO = PatternFill("solid", start_color=MORADO_BOLSA)
FILL_GRIS_T = PatternFill("solid", start_color=GRIS_T)


def col_de_weekday(wd: int) -> int:
    """Columna fija del día de la semana en la maqueta: E=miércoles, F=jueves,
    G=viernes, H=sábado, I=domingo, J=lunes, K=martes…",
    """
    return COL_INICIO_CALENDARIO + ((wd - 2) % 7)


def name_fila_bloque(mes: int) -> int:
    """Fila del nombre de mes: los bloques apilan en VERTICAL cada 6 filas
    (maqueta real: 4, 10, 16, 22, 28, 34 | 41, 47, 53, 59, 65, 71)."""
    if mes <= 6:
        return FILA_PRIMER_BLOQUE + 6 * (mes - 1)
    return FILA_PRIMER_BLOQUE_2 + 6 * (mes - 7)


def _rng(c1: int, r1: int, c2: int = 0, r2: int = 0) -> str:
    if not c2:
        return f"${get_column_letter(c1)}{r1}"
    return f"${get_column_letter(c1)}{r1}:${get_column_letter(c2)}{r2}"


def runs(listas: list[int]) -> list[tuple[int, int]]:
    """Columnas consecutivas agrupadas (para las fórmulas COUNTIF del §6.2)."""
    if not listas:
        return []
    grupos = []
    inicio = prev = listas[0]
    for c in listas[1:]:
        if c == prev + 1:
            prev = c
        else:
            grupos.append((inicio, prev))
            inicio = prev = c
    grupos.append((inicio, prev))
    return grupos


class GeneradorExcel:
    """Monta el libro a partir de la asignación del solver."""

    def __init__(self, cal: Calendario, asign: Asignacion, n_equipo: int,
                 n_area: int, modulos: int):
        self.cal = cal
        self.asign = asign
        self.n_equipo = n_equipo
        self.n_area = n_area
        self.modulos = modulos
        self.wb = Workbook()
        self.hoja = self.wb.active
        self.hoja.title = f"Calendario {cal.anio}"
        self.eq_fechas: dict[str, set[datetime.date]] = {
            n: {datetime.date.fromisoformat(x) for x in ls}
            for n, ls in asign.equipo.items()}
        self.ar_fechas: dict[str, set[datetime.date]] = {
            n: {datetime.date.fromisoformat(x) for x in ls}
            for n, ls in asign.area.items()}
        # mapa fecha → [letra_team, ..., nombre_area]
        self.celdas: dict[datetime.date, list[str | None]] = {
            dd.fecha: [None] * modulos for dd in cal.dias}
        for n, fs in self.eq_fechas.items():
            for f in fs:
                self._celda(f, n)
        for n, fs in self.ar_fechas.items():
            for f in fs:
                self._celda(f, n)
        vols = {(datetime.date.fromisoformat(b["fecha"]), b["celda"])
                for b in asign.bolsa}
        for (f, i) in vols:
            if self.celdas.get(f) and self.celdas[f][i] is None:
                self.celdas[f][i] = "Vacío"

    def _celda(self, fecha: datetime.date, nombre: str) -> None:
        celdas = self.celdas.get(fecha)
        if celdas is None:
            return
        for i, v in enumerate(celdas):
            if v is None:
                celdas[i] = nombre
                break

    # ------------------------------------------------------------------
    def construir(self) -> Workbook:
        self._titulo_y_cabeceras()
        self._bloques()
        self._estadisticas()
        self._resumen_anual()
        self._anchos()
        for nombre, n in self._nombres():
            self._detalle(nombre, n)
        return self.wb

    def _nombres(self) -> list[tuple[str, str]]:
        salida = []
        for i in range(self.n_equipo):
            letra = chr(ord("A") + i) if i < 26 else f"N{i}"
            salida.append((letra, "eq"))
        for i in range(self.n_area):
            salida.append((f"R{i + 1}", "ar"))
        return salida

    # ------------------------------------------------------------------
    def _titulo_y_cabeceras(self) -> None:
        ws = self.hoja
        # título combinado D1:AP1, centrado con el calendario (plantilla)
        ws.merge_cells(start_row=FILA_TITULO, start_column=4,
                       end_row=FILA_TITULO, end_column=42)
        ws.cell(row=FILA_TITULO, column=4,
                value=(f"CALENDARIO TIPO ZAMORA PROFESIONALES {self.n_equipo} EAP "
                       f"CON {self.n_area} PROF AREA AÑO {self.cal.anio}"))
        ws.cell(row=FILA_TITULO, column=4).font = FONT_TITULO
        ws.cell(row=FILA_TITULO, column=4).alignment = CENTRO_C
        ws.row_dimensions[FILA_TITULO].height = 28.5
        # fondo blanco sólido de la fila 2 (oculta la cuadrícula, plantilla)
        for col in range(COL_INICIO_CALENDARIO, COL_FIN_CALENDARIO + 1):
            ws.cell(row=FILA_CODIGOS_ESTAD, column=col).fill = FILL_BLANCO
        # cabecera de días de la semana (fila 3): E..AN; D en gris de banda
        dnombre = {2: "Miér", 3: "Jue", 4: "Vie", 5: "Sáb", 6: "Dom", 0: "Lun", 1: "Mar"}
        ws.cell(row=FILA_NOMBRES_DIA, column=4).fill = FILL_MES
        for col in range(COL_INICIO_CALENDARIO, COL_FIN_CALENDARIO + 1):
            wd = (col - COL_INICIO_CALENDARIO + 2) % 7
            c = ws.cell(row=FILA_NOMBRES_DIA, column=col, value=dnombre[wd])
            c.font = FONT_DIA
            c.alignment = CENTRO_C
            c.fill = FILL_FINDISM if wd in (5, 6) else FILL_BLANCO

    # ------------------------------------------------------------------
    def _bloques(self) -> None:
        ws = self.hoja
        for mes, nombre in meses_del_anio():
            nf = name_fila_bloque(mes)
            # fondo blanco sólido del bloque (oculta la cuadrícula) y columna
            # D en gris de banda (plantilla: th2 en D, blanco en E..AO)
            for rr in range(nf, nf + 6):
                ws.cell(row=rr, column=4).fill = FILL_MES
                for col in range(COL_INICIO_CALENDARIO, COL_FIN_CALENDARIO + 1):
                    ws.cell(row=rr, column=col).fill = FILL_BLANCO
            # fila del nombre de mes: borde inferior D..AO
            for col in range(4, COL_FIN_CALENDARIO + 1):
                ws.cell(row=nf, column=col).border = BORDE_MES
            cm = ws.cell(row=nf, column=4, value=nombre)
            cm.font = FONT_MES
            # celdas del bloque
            n_fila = nf + 1                      # números de día
            f_teq, f_tar = nf + 2, nf + 3        # equipo / área
            f_aux1, f_aux2 = nf + 4, nf + 5
            dias = [self.cal.por_fecha(d) for d in dias_del_mes(self.cal.anio, mes)]
            col0 = col_de_weekday(dias[0].weekday)
            ws.row_dimensions[nf].height = 19.5
            ws.row_dimensions[n_fila].height = 19.5
            ws.row_dimensions[f_teq].height = 19.5
            ws.row_dimensions[f_tar].height = 19.5
            for k, dia in enumerate(dias):
                col = col0 + k
                for rr in (f_teq, f_tar, f_aux1, f_aux2, n_fila):
                    ws.cell(row=rr, column=col).font = FONT_CELDA
                    ws.cell(row=rr, column=col).alignment = CENTRO_C
                # sombreado de fin de semana + festivos (morado; §6.3)
                if dia.weekday in (5, 6):
                    for rr in (n_fila, f_teq, f_tar, f_aux1, f_aux2):
                        ws.cell(row=rr, column=col).fill = FILL_FINDISM
                        ws.cell(row=rr, column=col).border = CAJA
                if dia.festivo:
                    for rr in (n_fila, f_teq, f_tar, f_aux1, f_aux2):
                        ws.cell(row=rr, column=col).fill = (
                            FILL_OSCURO if dia.especial else FILL_NARANJA)
                    # (el borde ya está)
                # número del día
                cn = ws.cell(row=n_fila, column=col, value=dia.fecha.day)
                cn.font = FONT_NUM
                cn.alignment = CENTRO_C
                # la plantilla subraya los números también en festivos
                cn.border = BORDE_NUM
                # equipos / área / bolsa
                valores = self.celdas[dia.fecha]
                for i, v in enumerate(valores):
                    rr = f_teq if i == 0 else f_tar
                    cel = ws.cell(row=rr, column=col)
                    cel.border = CAJA
                    if v is not None:
                        cel.value = v
                        cel.font = FONT_GUARDIAS
                        cel.alignment = CENTRO_C
                        if v == "Vacío":
                            cel.fill = FILL_MORADO
                for rr in (f_aux1, f_aux2):
                    ws.cell(row=rr, column=col).border = CAJA
        # fila separadora entre los dos semestres (40): fondo como los bloques
        ws.cell(row=FILA_PRIMER_BLOQUE_2 - 1, column=4).fill = FILL_MES
        for col in range(COL_INICIO_CALENDARIO, COL_FIN_CALENDARIO + 1):
            ws.cell(row=FILA_PRIMER_BLOQUE_2 - 1,
                    column=col).fill = FILL_BLANCO

    # ------------------------------------------------------------------
    def _grupo_tripleto(self, indice: int) -> tuple[int, int, int]:
        c0 = COL_INICIO_ESTADISTICAS + 3 * indice
        return c0, c0 + 1, c0 + 2

    def _formulas_bloque(self, mes: int, criterio: str) -> tuple[str, str]:
        """Fórmulas 17 h y 24 h de un bloque (§6.2), construidas dinámicamente:
        runs de columnas laborables y runs de finde/festivos."""
        dias = [self.cal.por_fecha(d) for d in dias_del_mes(self.cal.anio, mes)]
        col0 = col_de_weekday(dias[0].weekday)
        pares17, pares24 = [], []
        for k, dia in enumerate(dias):
            col = col0 + k
            (pares17 if dia.es_17h else pares24).append(col)
        nf = name_fila_bloque(mes)
        r17 = self._countif_runs(runs(pares17), nf + 1, nf + 5, criterio)
        r24 = self._countif_runs(runs(pares24), nf + 2, nf + 5, criterio)
        return r17, r24

    @staticmethod
    def _countif_runs(grupos: list[tuple[int, int]], r1: int, r2: int,
                      criterio: str) -> str:
        if not grupos:
            return "0"
        partes = []
        for c1, c2 in grupos:
            partes.append(f"COUNTIF({_rng(c1, r1, c2, r2)},{criterio})")
        return "+".join(partes)

    def _estadisticas(self) -> None:
        ws = self.hoja
        nombres = self._nombres()
        # marco lateral continuo de cada tripleto en TODAS las filas del
        # cuerpo (2..76, separadoras incluidas): medio en el borde externo
        for i in range(len(nombres)):
            c0, _c1, c2 = self._grupo_tripleto(i)
            for rr in range(FILA_CODIGOS_ESTAD, FILA_INICIO_RESUMEN - 1):
                ws.cell(row=rr, column=c0).border = CAJA_IZQ
                ws.cell(row=rr, column=c2).border = CAJA_DER
            # fila de nombres de día: fondo blanco (plantilla)
            for col in (c0, _c1, c2):
                ws.cell(row=FILA_NOMBRES_DIA, column=col).fill = FILL_BLANCO
        for i, (nombre, _) in enumerate(nombres):
            c0, c1, c2 = self._grupo_tripleto(i)
            # letra combinada 3-en-3, font 20 bold, gris y con caja
            h_letra = ws.cell(row=FILA_CABECERA_ESTAD, column=c0, value=nombre)
            h_letra.font = FONT_LETRA_ESTAD
            h_letra.alignment = CENTRO_C
            h_letra.fill = FILL_FINDISM
            for col in (c0, c1, c2):
                ws.cell(row=FILA_CABECERA_ESTAD, column=col).border = CAJA
            ws.merge_cells(start_row=FILA_CABECERA_ESTAD, start_column=c0,
                           end_row=FILA_CABECERA_ESTAD, end_column=c2)
            for col_txt, col in (("17", c0), ("24", c1), ("T", c2)):
                cc = ws.cell(row=FILA_CODIGOS_ESTAD, column=col, value=col_txt)
                cc.font = FONT_ESTAD
                cc.alignment = CENTRO_C
            for mes in range(1, 13):
                nf = name_fila_bloque(mes)
                f_eq = nf + 2
                criterio = f"{get_column_letter(c0)}${FILA_CABECERA_ESTAD}"
                f17, f24 = self._formulas_bloque(mes, criterio)
                a = ws.cell(row=f_eq, column=c0, value=f"={f17}")
                b = ws.cell(row=f_eq, column=c1, value=f"={f24}")
                t = ws.cell(row=f_eq, column=c2,
                            value=f"={get_column_letter(c0)}{f_eq}*17"
                                  f"+{get_column_letter(c1)}{f_eq}*24")
                for cc in (a, b, t):
                    cc.font = FONT_ESTAD
                    cc.alignment = CENTRO_C
                # filas de fórmulas: además, borde horizontal medio (plantilla)
                for col in (c0, c1, c2):
                    cc = ws.cell(row=f_eq, column=col)
                    cc.border = Border(
                        left=BORDE_MED if col == c0 else None,
                        right=BORDE_MED if col == c2 else None,
                        top=BORDE_MED, bottom=BORDE_MED)
                t.fill = FILL_GRIS_T

    # ------------------------------------------------------------------
    def _resumen_anual(self, ) -> None:
        ws = self.hoja
        cab = FILA_INICIO_RESUMEN
        etiquetas = [("F", "L", 0), ("G", "M", 1), ("H", "X", 2), ("I", "J", 3),
                     ("J", "V", 4), ("K", "S", 5), ("L", "D", 6)]
        fest_cols = {"O": ("01.01", (1, 1)), "P": ("24.12", (12, 24)),
                     "Q": ("25.12", (12, 25)), "R": ("31.12", (12, 31)),
                     "N": ("F", None)}
        c = ws.cell(row=cab, column=COL_RESUMEN_NOMBRE - 1, value="NOMBRE")
        c.font = FONT_CAB_RESUMEN
        # bordes de cabecera: caja media en L..D, F y 31.12 (plantilla)
        bordes_cab = {
            "F": Border(left=BORDE_MED, right=BORDE_THIN,
                        top=BORDE_MED, bottom=BORDE_THIN),
            "G": CAJA_CAB, "H": CAJA_CAB, "I": CAJA_CAB, "J": CAJA_CAB,
            "K": CAJA_CAB,
            "L": Border(left=BORDE_THIN, right=BORDE_MED,
                        top=BORDE_MED, bottom=BORDE_THIN),
            "M": Border(top=BORDE_THIN, bottom=BORDE_THIN),
            "N": Border(left=BORDE_MED, right=BORDE_THIN,
                        top=BORDE_MED, bottom=BORDE_THIN),
            "O": CAJA_CAB, "P": CAJA_CAB, "Q": CAJA_CAB,
            "R": Border(left=BORDE_THIN, right=BORDE_MED,
                        top=BORDE_MED, bottom=BORDE_THIN),
            "T": CAJA, "U": Border(right=BORDE_THIN, top=BORDE_THIN,
                                   bottom=BORDE_THIN),
            "W": CAJA, "X": Border(right=BORDE_THIN, top=BORDE_THIN,
                                   bottom=BORDE_THIN),
        }
        fills_cab = {"M": FILL_BLANCO, "O": FILL_FINDISM, "Q": FILL_FINDISM,
                     "T": FILL_FINDISM, "W": FILL_FINDISM}
        for col_l, texto, _wd in etiquetas:
            cc = ws.cell(row=cab, column=get_column_index(col_l), value=texto)
            cc.font = FONT_CAB_RESUMEN
            cc.alignment = CENTRO_C
            cc.fill = FILL_FINDISM
        for col_l, (texto, _md) in fest_cols.items():
            cc = ws.cell(row=cab, column=get_column_index(col_l), value=texto)
            cc.font = FONT_CAB_RESUMEN
            cc.alignment = CENTRO_C
            if texto in ("F",):
                cc.fill = FILL_NARANJA
            elif texto in ("24.12", "31.12"):
                cc.fill = FILL_OSCURO
        for col_l, texto in (("T", "Horas"), ("W", "GUARDIAS")):
            cc = ws.cell(row=cab, column=get_column_index(col_l), value=texto)
            cc.font = FONT_CAB_RESUMEN
            cc.alignment = CENTRO_C
        for col_l, borde in bordes_cab.items():
            cc = ws.cell(row=cab, column=get_column_index(col_l))
            cc.border = borde
            if col_l in fills_cab:
                cc.fill = fills_cab[col_l]
        # Horas y GUARDIAS combinados con su columna vecina (plantilla)
        ws.merge_cells(start_row=cab, start_column=get_column_index("T"),
                       end_row=cab, end_column=get_column_index("U"))
        ws.merge_cells(start_row=cab, start_column=get_column_index("W"),
                       end_row=cab, end_column=get_column_index("X"))

        fila = cab + 1
        for nombre, grupo in self._nombres():
            cb = ws.cell(row=fila, column=COL_RESUMEN_NOMBRE, value=nombre)
            cb.font = FONT_RESUMEN
            cb.alignment = CENTRO_C
            cb.fill = FILL_FINDISM          # plantilla: B gris con caja
            cb.border = CAJA
            criterio = f"$B{fila}"
            # días de la semana (quirk: excluye las celdas de días festivos)
            for col_l, _texto, wd in etiquetas:
                partes = []
                for mes in range(1, 13):
                    nf = name_fila_bloque(mes)
                    dias = [self.cal.por_fecha(d) for d in dias_del_mes(self.cal.anio, mes)]
                    col0 = col_de_weekday(dias[0].weekday)
                    for dia in dias:
                        if dia.weekday != wd or dia.festivo:
                            continue
                        col = col0 + (dia.fecha.day - 1)
                        partes.append(f"COUNTIF({_rng(col, nf + 1, col, nf + 5)},"
                                      f"{criterio})")
                ws.cell(row=fila, column=get_column_index(col_l), 
                        value="=" + ("+".join(partes) if partes else "0"))
            # festivos (F: todos menos 24/12 y 31/12)
            partes_f = []
            fest_col_l: dict[tuple[int, int], str] = {}
            for mes in range(1, 13):
                nf = name_fila_bloque(mes)
                dias = [self.cal.por_fecha(d) for d in dias_del_mes(self.cal.anio, mes)]
                col0 = col_de_weekday(dias[0].weekday)
                for dia in dias:
                    if not dia.festivo:
                        continue
                    col = col0 + (dia.fecha.day - 1)
                    fest_col_l[(dia.fecha.month, dia.fecha.day)] = \
                        get_column_letter(col)
                    if (dia.fecha.month, dia.fecha.day) in ((12, 24), (12, 31)):
                        continue
                    partes_f.append(f"COUNTIF({_rng(col, nf + 1, col, nf + 5)},"
                                    f"{criterio})")
            ws.cell(row=fila, column=get_column_index("N"),
                    value="=" + ("+".join(partes_f) if partes_f else "0"))
            for col_l, (texto, md) in fest_cols.items():
                if md is None or texto == "F":
                    continue
                clave = md
                col = fest_col_l.get(md)
                if col:
                    nf = name_fila_bloque(md[0])
                    ci = get_column_index(col)
                    ws.cell(row=fila, column=get_column_index(col_l),
                            value=f"=COUNTIF({_rng(ci, nf + 1, ci, nf + 5)},"
                                  f"{criterio})")
                else:
                    ws.cell(row=fila, column=get_column_index(col_l), value=0)
                cc = ws.cell(row=fila, column=get_column_index(col_l))
                cc.font = FONT_RESUMEN
                cc.alignment = CENTRO_C
            ws.cell(row=fila, column=get_column_index("T"),
                    value=(f"=((F{fila}+G{fila}+H{fila}+I{fila}+J{fila})*17)"
                           f"+((K{fila}+L{fila}+N{fila}+P{fila}+R{fila})*24)"))
            ws.cell(row=fila, column=get_column_index("W"),
                    value=(f"=SUM(F{fila}:L{fila})+SUM(R{fila})"
                           f"+SUM(N{fila})+SUM(P{fila})"))
            # estilos de plantilla por columna (fills temáticos y bordes)
            borde_par = Border(right=BORDE_THIN, top=BORDE_THIN,
                               bottom=BORDE_THIN)
            estilos_fila = {
                "F": (FILL_BLANCO, CAJA_IZQ_FIN),
                "G": (None, CAJA), "H": (None, CAJA), "I": (None, CAJA),
                "J": (None, CAJA), "K": (FILL_BLANCO, CAJA),
                "L": (FILL_FINDISM, CAJA_DER_FIN),
                "M": (FILL_BLANCO, None),       # espaciadora (plantilla)
                "N": (FILL_NARANJA, CAJA_IZQ_FIN),
                "O": (None, CAJA), "P": (FILL_OSCURO, CAJA),
                "Q": (None, CAJA), "R": (FILL_OSCURO, CAJA_DER_FIN),
                "T": (None, CAJA), "U": (None, borde_par),
                "W": (None, CAJA), "X": (None, borde_par),
            }
            for col_l in "FGHIJKLMNOPQRTUWX":
                cc = ws.cell(row=fila, column=get_column_index(col_l))
                cc.font = FONT_RESUMEN
                cc.alignment = CENTRO_C
                fill, borde = estilos_fila[col_l]
                if fill is not None:
                    cc.fill = fill
                if borde is not None:
                    cc.border = borde
            fila += 1
        # fila SUMA
        fila_suma = fila + 1
        cs = ws.cell(row=fila_suma, column=COL_RESUMEN_NOMBRE, value="SUMA")
        cs.font = Font(name="Calibri", size=10, bold=True)
        cs.alignment = CENTRO_C
        cs.fill = FILL_FINDISM
        cs.border = CAJA
        for col_l in "FGHIJKLMNOPQRTUWX":
            i = get_column_index(col_l)
            cc = ws.cell(row=fila_suma, column=i)
            if col_l in "FGHIJKLNOPQRTW":
                cc.value = f"=SUM({col_l}{cab + 1}:{col_l}{fila - 1})"
            cc.alignment = CENTRO_C
            if col_l == "M":                # espaciadora: blanco, sin bordes
                cc.fill = FILL_BLANCO
            elif col_l in ("U", "X"):       # pareja del merge de cabecera
                cc.border = Border(right=BORDE_THIN, top=BORDE_THIN,
                                   bottom=BORDE_THIN)
            elif col_l in "FGHIJKLNOPQR":
                cc.border = Border(
                    left=BORDE_MED if col_l in ("F", "N") else BORDE_THIN,
                    right=BORDE_MED if col_l in ("L", "R") else BORDE_THIN,
                    top=BORDE_MED, bottom=BORDE_MED)
            else:                           # T, W
                cc.border = CAJA

    # ------------------------------------------------------------------
    def _anchos(self) -> None:
        ws = self.hoja
        ws.column_dimensions["B"].width = 4.25
        ws.column_dimensions["D"].width = 18.5
        for col in range(COL_INICIO_CALENDARIO, COL_FIN_CALENDARIO + 1):
            ws.column_dimensions[get_column_letter(col)].width = 5.375
        ws.column_dimensions[get_column_letter(COL_INICIO_ESTADISTICAS - 1)].width = 2.5
        end = COL_INICIO_ESTADISTICAS + 3 * (self.n_equipo + self.n_area) + 4
        for col in range(COL_INICIO_ESTADISTICAS, end):
            ws.column_dimensions[get_column_letter(col)].width = 4.0
        for col in "FGHIJKLNOPQRTW":
            ws.column_dimensions[col].width = 5.0

    # ------------------------------------------------------------------
    def _detalle(self, nombre: str, grupo: str) -> None:
        """Hoja de detalle D7: minapestas… mini-calendario del año + resumen."""
        ws = self.wb.create_sheet(f"Detalle {nombre}")
        fechas = set(self.eq_fechas.get(nombre, set())) if grupo == "eq" \
            else set(self.ar_fechas.get(nombre, set()))
        fest_de = {dd.fecha: dd for dd in self.cal.dias if dd.festivo}
        horas = sum(self.cal.por_fecha(f).horas for f in fechas)
        ws.cell(row=1, column=1,
                value=f"Guardias {nombre} — año {self.cal.anio} "
                      f"({horas} h, {len(fechas)} guardias)").font = \
            Font(name="Calibri", size=12, bold=True)
        # fila 2: números de día 1..31 compartidos por todos los meses
        cn_fila = 2
        for dia in range(1, 32):
            cn = ws.cell(row=cn_fila, column=1 + dia, value=dia)
            cn.font = Font(name="Calibri", size=9)
            cn.alignment = CENTRO_C
        fila = 3
        for mes, nombre_mes in meses_del_anio():
            ws.cell(row=fila, column=1, value=nombre_mes).font = \
                Font(name="Calibri", size=10, bold=True)
            dias = [self.cal.por_fecha(d) for d in dias_del_mes(self.cal.anio, mes)]
            for k, dia in enumerate(dias):
                c = ws.cell(row=fila, column=2 + k)
                if dia.fecha in fechas:
                    c.value = nombre
                    c.fill = PatternFill("solid", start_color="FFB7D9B7" if grupo == "eq"
                                         else "FFB7C9D9")
                elif dia.fecha in fest_de:
                    c.fill = PatternFill(
                        "solid",
                        start_color=NARANJA_FESTIVO_OSCURO if dia.especial
                        else NARANJA_FESTIVO)
            fila += 1
        # resumen
        fila += 1
        ws.cell(row=fila, column=1, value="Resumen").font = Font(size=10, bold=True)
        fila += 1
        cont = {"L": 0, "M": 0, "X": 0, "J": 0, "V": 0}
        for f in fechas:      # count por weekday (quirk §6.2: festivos aparte)
            dia = self.cal.por_fecha(f)
            if dia.es_17h and dia.weekday <= 4:
                cont["LMXJVR"[dia.weekday]] = cont.get(
                    "LMXJVR"[dia.weekday], 0) + 1
        sabs = [f for f in fechas if f.weekday() == 5]
        sabs_fest = [f for f in sabs if self.cal.por_fecha(f).festivo]
        doms = [f for f in fechas if f.weekday() == 6 and
                not self.cal.por_fecha(f).festivo]
        vies = [f for f in fechas if f.weekday() == 4 and
                not self.cal.por_fecha(f).festivo]
        fest_trab = sorted(f for f in fechas if self.cal.por_fecha(f).festivo)
        parejas = []
        for s in sabs:
            jt = s + datetime.timedelta(days=5)
            if jt in fechas:
                parejas.append(s)
        filas_resumen = [
            ("Horas", horas),
            ("Guardias", len(fechas)),
            ("Lunes", cont.get("L", 0)), ("Martes", cont.get("M", 0)),
            ("Miércoles", cont.get("X", 0)),
            ("Jueves (parejas)", sum(1 for f in fechas
                                     if self.cal.por_fecha(f).es_jueves
                                     and not self.cal.por_fecha(f).festivo)),
            ("Viernes", len(vies)),
            ("Sábados", f"{len(sabs)} ({len(sabs) - len(sabs_fest)} ordinarios + "
                        f"{len(sabs_fest)} festivo-sábado)"),
            ("Domingos", len(doms)),
            ("Festivos trabajados", ", ".join(f.isoformat() for f in fest_trab)),
            ("Parejas sáb→jue(+5)", ", ".join(f.isoformat() for f in parejas)),
            ("Bolsa «Vacío»", sum(1 for b in self.asign.bolsa
                                  if b["fecha"] in {f.isoformat() for f in fechas})),
        ]
        for etiqueta, valor in filas_resumen:
            ws.cell(row=fila, column=1, value=etiqueta).font = \
                Font(name="Calibri", size=10)
            ws.cell(row=fila, column=2, value=valor).font = \
                Font(name="Calibri", size=10)
            fila += 1


def columna_de(letra: str) -> int:
    from openpyxl.utils import column_index_from_string
    return column_index_from_string(letra)


def get_column_index(letra: str) -> int:
    from openpyxl.utils import column_index_from_string
    return column_index_from_string(letra)


# compat alias
def generar_libro(cal: Calendario, asign: Asignacion, n_equipo: int,
                  n_area: int, modulos: int) -> Workbook:
    return GeneradorExcel(cal, asign, n_equipo, n_area, modulos).construir()
