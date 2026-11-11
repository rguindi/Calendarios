# -*- coding: utf-8 -*-
"""Genera el calendario de guardias 2027: 11 enfermeras equipo (A-K) + 3 de area (R1-R3)."""
import openpyxl, datetime, json
from openpyxl.utils import get_column_letter

MODELO = "/mnt/datos/Descargas/calendarios/MODELO CALENDARIO 2027  FESTIVOS ZAMORA - 12EAP 4AREA.xlsx"
wb = openpyxl.load_workbook(MODELO, data_only=False)
ws = wb.worksheets[0]

# ---------- 1. Parsear bloques de meses (fila del nombre en col D) ----------
MES = {'ENERO':1,'FEBRERO':2,'MARZO':3,'ABRIL':4,'MAYO':5,'JUNIO':6,'JULIO':7,'AGOSTO':8,
       'SEPTIEMBRE':9,'0CTUBRE':10,'NOVIEMBRE':11,'DICIEMBRE':12}
blocks = []
for r in range(1, 80):
    v = ws.cell(row=r, column=4).value
    if isinstance(v, str) and v.strip().upper() in MES:
        blocks.append((MES[v.strip().upper()], r))
blocks.sort()
day_list = []
for mon, name_row in blocks:
    numrow = name_row + 1
    cells = sorted((c, int(ws.cell(row=numrow, column=c).value)) for c in range(1, 60)
                   if isinstance(ws.cell(row=numrow, column=c).value, (int, float)))
    assert [d for _, d in cells] == list(range(1, len(cells) + 1)), MES[mon] if isinstance(mon,int) else mon
    for c, dnum in cells:
        day_list.append({'date': datetime.date(2027, mon, dnum), 'col': c, 'team_row': numrow + 1,
                         'area_row': numrow + 2, 'team': None, 'team2': None, 'area': None})
assert len(day_list) == 365
by_date = {dd['date']: dd for dd in day_list}

# ---------- 2. Categoria de recuento (segun las formulas del Excel) ----------
N_FEST = {(1,1),(1,6),(3,25),(3,26),(4,23),(5,1),(5,17),(10,12),(8,16),(6,29),(11,1),(12,6),(12,8),(12,25)}
ESP = {(1,1),(3,25),(3,26),(3,27),(3,28),(12,24),(12,25),(12,31)}
SAT_2020 = datetime.date(2027, 3, 20)          # su jueves+5 es 25/3 (festivo que SI cuenta como Jueves)
JUE_NO_PAIR = {datetime.date(2027,5,6), datetime.date(2027,12,30)}  # su sabado-5 no cuenta como Sabado
for dd in day_list:
    dt = dd['date']; md = (dt.month, dt.day); wd = dt.weekday()
    dd['esp'] = md in ESP
    if md in N_FEST or md == (12,24) or md == (12,31):
        dd['cat'], dd['h'] = 'F', 24
    elif wd == 6: dd['cat'], dd['h'] = 'D', 24
    elif wd == 5: dd['cat'], dd['h'] = 'K', 24
    elif wd == 4: dd['cat'], dd['h'] = 'V', 17
    elif wd == 3: dd['cat'], dd['h'] = 'I', 17
    else:         dd['cat'], dd['h'] = 'LMX', 17

# ---------- 3. EQUIPO (A-K): 6 Sab(emparejados Jue+5) + 6 Dom + 6 Vie + 6 Jue + 2 festivos + 20 LMX = 46 guardias, 880 h ----------
nurses = list('ABCDEFGHIJK')
QUOTA = {'K':6,'D':6,'V':6,'I':6,'F':2,'LMX':20}
state = {n: {'K':0,'D':0,'V':0,'I':0,'F':0,'LMX':0,'total':0} for n in nurses}
assigned = {n: set() for n in nurses}
N25 = None  # enfermera con la pareja especial 20/3 -> 25/3

def free(n, dt):
    return all(dt + datetime.timedelta(days=o) not in assigned[n] for o in (-1, 0, 1))

def put(n, dt):
    dd = by_date[dt]
    if dd['team'] is None: dd['team'] = n
    else: dd['team2'] = n
    assigned[n].add(dt); state[n]['total'] += 1; state[n][dd['cat']] += 1

def pick(cands, key, dt):
    return min(cands, key=lambda n: (state[n][key], state[n]['total'],
                min((dt - d).days for d in assigned[n]) if assigned[n] else 999, n))

# 3a. Parejas sabado->jueves(+5)
sat_days = [dd for dd in day_list if dd['cat'] == 'K']          # 50 sabados "contables"
npairs = 6 * len(nurses)                                        # 66
doubles = npairs - len(sat_days)                                # 16
dbl = {int(round((k + 0.5) * len(sat_days) / doubles)) for k in range(doubles)}
sat_pairs = {}
N25 = None
for i, dd in enumerate(sat_days):
    dt = dd['date']; jt = dt + datetime.timedelta(days=5)
    k = 0
    if dt == SAT_2020: k = 1                                    # pareja especial -> jueves 25/3
    elif jt <= datetime.date(2027,12,31) and jt not in JUE_NO_PAIR:
        k = 2 if i in dbl else 1
    cands = [n for n in nurses if state[n]['K'] < 6 and free(n, dt) and free(n, jt)]
    cands.sort(key=lambda n: (state[n]['K'], state[n]['total'], n))
    for n in cands[:k]:
        put(n, dt); put(n, jt)          # sabado y su jueves +5
        if dt == SAT_2020: N25 = n
# 3a-reparacion: completar parejas pendientes (relajando la separacion del jueves)
for n in [x for x in nurses if state[x]['K'] < 6]:
    while state[n]['K'] < 6:
        hechas = [(dd['date']) for dd in sat_days if n in (dd['team'], dd['team2'])]
        libres = [dd for dd in sat_days if len([x for x in (dd['team'], dd['team2']) if x]) < 2
                  and dd['date'] not in assigned[n]
                  and dd['date'] + datetime.timedelta(days=5) <= datetime.date(2027,12,31)
                  and dd['date'] + datetime.timedelta(days=5) not in JUE_NO_PAIR
                  and dd['date'] + datetime.timedelta(days=5) not in assigned[n]
                  and len([x for x in (by_date[dd['date']+datetime.timedelta(days=5)]['team'],
                                       by_date[dd['date']+datetime.timedelta(days=5)]['team2']) if x]) < 2]
        # preferir sabados con hueco y jueves libre aunque esten pegados a otras guardias propias
        dd = libres[0]
        put(n, dd['date']); put(n, dd['date'] + datetime.timedelta(days=5))
        if dd['date'] == SAT_2020: N25 = n

for n in nurses:
    exp = 5 if n == N25 else 6          # la pareja 20/3->25/3 cuenta como festivo, no como jueves "I"
    assert state[n]['K'] == 6 and state[n]['I'] == exp, (n, state[n], N25)

# 3b. Resto de categorias: 1 por dia + dobles repartidos
def fill(cat, key, skip_esp_con_team=False):
    pool = [dd for dd in day_list if dd['cat'] == cat]
    if skip_esp_con_team:
        # especiales con equipo ya cubierto (25/3 con la pareja): les sobra cupo -> se compensa con dobles en el resto
        pool = [dd for dd in pool if not (dd['esp'] and dd['team'])]
    need = QUOTA[key] * len(nurses) - sum(state[n][key] for n in nurses)
    doubles = need - len(pool)
    if doubles > 0:
        step = len(pool) / doubles
        dbl = {int(round((k + 0.5) * step)) for k in range(doubles)}
    else:
        dbl = set()
    for i, dd in enumerate(pool):
        k = 2 if i in dbl else 1
        for _ in range(k):
            if dd['team'] is not None and dd['team2'] is not None: break   # dia lleno
            cands = [n for n in nurses if state[n][key] < QUOTA[key] and free(n, dd['date'])
                     and dd['team'] != n and dd['team2'] != n]
            if not cands: break
            put(pick(cands, key, dd['date']), dd['date'])

fill('D', 'D'); fill('V', 'V'); fill('LMX', 'LMX'); fill('F', 'F', skip_esp_con_team=True)
for n in nurses:
    s = state[n]
    if n == N25: assert s['I'] == 5 and s['F'] == 2, (n, s)
    else: assert all(s[k] == v for k, v in QUOTA.items()), (n, s)
    if n == N25: assert s['total'] == 45   # 46 "guardias" contadas: el 25/3 puntua como Jueves y como festivo
    else: assert s['total'] == 46, (n, s)
sin_team = [dd['date'].isoformat() for dd in day_list if dd['team'] is None]
assert sin_team == ['2027-05-06', '2027-12-30'], sin_team  # imposible emparejar: su sabado-5 es festivo no contable

# Compensacion N25: el jueves de su pareja (25/3) es festivo y el modelo lo cuenta solo
# como festivo (24 h), no como jueves (17 h). Recibe un jueves normal mas -> 46 guardias / 880 h.
jueves_libres = [dd for dd in day_list if dd['cat'] == 'I'
                 and dd['team'] is not None and dd['team2'] is None
                 and free(N25, dd['date'])]
assert jueves_libres
ddj = max(jueves_libres, key=lambda dd: min(abs((dd['date'] - d).days) for d in assigned[N25]))
put(N25, ddj['date'])
assert state[N25]['I'] == 6 and state[N25]['F'] == 2 and state[N25]['total'] == 46
print("N25 compensada con jueves extra:", ddj['date'].isoformat())
d2 = sum(1 for dd in day_list if dd['team2'])
print("EQUIPO OK (46 guardias x 11 = 506; dias con 2 equipo:", d2, "; sin equipo:", sin_team, ")")

# ---------- 4. AREA (R1-R3): rellena la celda libre de cada dia, horas equilibradas ----------
area_n = ['R1', 'R2', 'R3']
astate = {n: {'h': 0, 'total': 0} for n in area_n}
aassigned = {n: set() for n in area_n}
for dd in day_list:
    dt = dd['date']
    huecos = 2 - sum(1 for x in (dd['team'], dd['team2']) if x)   # celdas libres (2 si no hay equipo)
    for _ in range(huecos):
        cands = [n for n in area_n if all(dt + datetime.timedelta(days=o) not in aassigned[n] for o in (-1, 0))]
        if not cands: cands = [n for n in area_n if dt not in aassigned[n]]
        n = min(cands, key=lambda n: (astate[n]['h'], astate[n]['total'], n))   # siempre el menos cargado
        if dd['area'] is None: dd['area'] = n
        else: dd['team2'] = n          # segundo area en el dia sin equipo
        astate[n]['h'] += dd['h']   # 25/3 puntua solo como festivo (24 h): sin compensacion de jueves
        astate[n]['total'] += 1
        aassigned[n].add(dt)
print("AREA:", {n: (astate[n]['total'], astate[n]['h']) for n in area_n})

# ---------- 5. VALIDACION ----------
for n in nurses:
    fechas = list(assigned[n])
    assert len(fechas) == len(set(fechas))
for dd in day_list:
    eq = [n for n in nurses if dd['date'] in assigned[n]]
    ar = [n for n in area_n if dd['date'] in aassigned[n]]
    assert len(eq) + len(ar) == 2 and len(eq) <= 2 and len(ar) <= 2, (dd['date'], eq, ar)
    assert not (set(eq) & set(ar))
tot = sum(astate[n]['h'] for n in area_n)
print("AREA total:", tot, "h ->", round(tot/3, 1), "h/enfermera; celdas:", sum(astate[n]['total'] for n in area_n))

json.dump({'team': {n: sorted(d.isoformat() for d in assigned[n]) for n in nurses},
           'area': {n: sorted(d.isoformat() for d in aassigned[n]) for n in area_n},
           'N25': N25}, open('/tmp/opencode/calendario.json', 'w'))
print("Guardado /tmp/opencode/calendario.json")
