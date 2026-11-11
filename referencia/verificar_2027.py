# -*- coding: utf-8 -*-
"""Verifica el calendario guardado emulando las formulas reales del Excel (filas 79-98)."""
import openpyxl, re
from openpyxl.utils import column_index_from_string, get_column_letter

MODELO = "/mnt/datos/Descargas/calendarios/MODELO CALENDARIO 2027  FESTIVOS ZAMORA - 12EAP 4AREA.xlsx"
wb = openpyxl.load_workbook(MODELO, data_only=False)
ws = wb.worksheets[0]

def countif(rng, crit):
    m = re.match(r'\$?([A-Z]+)\$?(\d+):\$?([A-Z]+)\$?(\d+)', rng)
    c1, r1, c2, r2 = column_index_from_string(m.group(1)), int(m.group(2)), column_index_from_string(m.group(3)), int(m.group(4))
    n = 0
    for cc in range(min(c1, c2), max(c1, c2) + 1):
        for rr in range(min(r1, r2), max(r1, r2) + 1):
            v = ws.cell(row=rr, column=cc).value
            if v is not None and str(v).strip().upper() == str(crit).strip().upper():
                n += 1
    return n

print(f"{'':4s} {'L':>3s} {'M':>3s} {'X':>3s} {'J':>3s} {'V':>3s} {'S':>3s} {'D':>3s} {'Fest':>4s} {'01/1':>4s} {'24/12':>5s} {'25/12':>5s} {'31/12':>5s} {'HORAS':>6s} {'GUARD.':>6s}")
resultados = {}
for r in list(range(79, 91)) + list(range(92, 97)):
    nombre = ws.cell(row=r, column=2).value
    if nombre is None:
        continue
    vals = {}
    for col, key in (('F','L'),('G','M'),('H','X'),('I','J'),('J','V'),('K','S'),('L','D'),
                     ('N','F'),('O','01/1'),('P','24/12'),('Q','25/12'),('R','31/12')):
        f = ws[f'{col}{r}'].value
        crit = ws.cell(row=r, column=2).value
        vals[key] = sum(countif(rng, crit) for rng in re.findall(r'COUNTIF\(([^,]+),', f))
    horas = (vals['L']+vals['M']+vals['X']+vals['J']+vals['V'])*17 + (vals['S']+vals['D']+vals['F']+vals['24/12']+vals['31/12'])*24
    guardias = vals['L']+vals['M']+vals['X']+vals['J']+vals['V']+vals['S']+vals['D']+vals['F']+vals['24/12']+vals['31/12']
    festivos = vals['F']+vals['24/12']+vals['31/12']   # 01/1 y 25/12 ya estan dentro de F
    resultados[nombre] = (horas, guardias, vals, festivos)
    print(f"{nombre:4s} {vals['L']:3d} {vals['M']:3d} {vals['X']:3d} {vals['J']:3d} {vals['V']:3d} {vals['S']:3d} {vals['D']:3d} {vals['F']:4d} {vals['01/1']:4d} {vals['24/12']:5d} {vals['25/12']:5d} {vals['31/12']:5d} {horas:6d} {guardias:6d}")

ok = True
for n in 'ABCDEFGHIJK':
    h, g, v, fest = resultados[n]
    if not (v['S'] == 6 and v['D'] == 6 and v['V'] == 6 and v['J'] == 6 and fest == 2 and h == 880 and g == 46):
        ok = False; print("ERROR en", n, v)
tot_h = sum(resultados[n][0] for n in ('R1','R2','R3'))
print()
print("Equipo A-K correctos (6S 6D 6V 6J 2F, 46 guardias, 880h):", ok)
print("Area R1-R3 horas:", {n: resultados[n][0] for n in ('R1','R2','R3')}, "-> total", tot_h, "h, media", round(tot_h/3,1))
print("L/R4/R5 vacios:", all(resultados[n][1] == 0 for n in ('L','R4','R5')))
# parejas sabado->jueves(+5): cada sabado CONTABLE (no festivo) lleva su jueves +5
import datetime, json
data = json.load(open('/tmp/opencode/calendario.json'))
FEST_SAB = {datetime.date(2027,5,1), datetime.date(2027,12,25)}  # sabados que son festivo: cuentan como festivo
fallos = []
for n, ls in data['team'].items():
    fs = set(datetime.date.fromisoformat(d) for d in ls)
    for s in (d for d in fs if d.weekday() == 5 and d not in FEST_SAB):
        if s + datetime.timedelta(days=5) not in fs:
            fallos.append((n, s))
    if datetime.date(2027,3,20) in fs and datetime.date(2027,3,25) not in fs:
        fallos.append((n, 'pareja 20/3'))
    # sin guardias en dias consecutivos
    for d in fs:
        if d + datetime.timedelta(days=1) in fs:
            fallos.append((n, 'consecutivos', d.isoformat()))
print("Parejas sabado->jueves(+5) y no consecutivos:", not fallos, fallos)
print("Cubre festivos-sabado (1/5, 25/12) el equipo:", sorted(n for n, ls in data['team'].items()
      if '2027-05-01' in ls or '2027-12-25' in ls))
