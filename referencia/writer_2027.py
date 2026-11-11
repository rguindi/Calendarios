# -*- coding: utf-8 -*-
"""Escribe las guardias del JSON en el modelo 2027 y guarda in place."""
import openpyxl, json, datetime, shutil

MODELO = "/mnt/datos/Descargas/calendarios/MODELO CALENDARIO 2027  FESTIVOS ZAMORA - 12EAP 4AREA.xlsx"
BACKUP = "/tmp/opencode/MODELO_backup_sin_rellenar.xlsx"

data = json.load(open('/tmp/opencode/calendario.json'))
team_of = {n: set(datetime.date.fromisoformat(d) for d in v) for n, v in data['team'].items()}
area_of = {n: set(datetime.date.fromisoformat(d) for d in v) for n, v in data['area'].items()}
nurses = sorted(team_of)
area_n = sorted(area_of)

shutil.copy(MODELO, BACKUP)
wb = openpyxl.load_workbook(MODELO, data_only=False)
ws = wb.worksheets[0]

MES = {'ENERO':1,'FEBRERO':2,'MARZO':3,'ABRIL':4,'MAYO':5,'JUNIO':6,'JULIO':7,'AGOSTO':8,
       'SEPTIEMBRE':9,'0CTUBRE':10,'NOVIEMBRE':11,'DICIEMBRE':12}
blocks = []
for r in range(1, 80):
    v = ws.cell(row=r, column=4).value
    if isinstance(v, str) and v.strip().upper() in MES:
        blocks.append((MES[v.strip().upper()], r))
blocks.sort()

escritas = 0
for mon, name_row in blocks:
    numrow = name_row + 1
    for c in range(1, 60):
        dnum = ws.cell(row=numrow, column=c).value
        if not isinstance(dnum, (int, float)):
            continue
        dt = datetime.date(2027, mon, int(dnum))
        eq = sorted(n for n in nurses if dt in team_of[n])
        ar = sorted(n for n in area_n if dt in area_of[n])
        assert len(eq) + len(ar) == 2, (dt, eq, ar)
        celdas = [(numrow + 1, c), (numrow + 2, c)]      # fila equipo, fila area
        for (rr, cc), nombre in zip(celdas, eq + ar):
            cell = ws.cell(row=rr, column=cc)
            assert cell.value in (None, ''), (rr, cc, cell.value)
            cell.value = nombre
            escritas += 1

titulo = ws['D1'].value
ws['D1'] = 'CALENDARIO TIPO ZAMORA PROFESIONALES 11 EAP CON 3 PROF AREA AÑO 2027'
wb.save(MODELO)
print(f"OK: {escritas} celdas escritas (365 dias x 2)")
print("Titulo antes :", titulo)
print("Titulo ahora :", ws['D1'].value)
print("Backup sin rellenar en:", BACKUP)
