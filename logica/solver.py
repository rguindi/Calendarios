# -*- coding: utf-8 -*-
"""
M2 — Solver de asignación de guardias (§5 del PLAN.md, Rev. 2).

Port de `referencia/solver_2027.py` a módulo genérico con las diferencias
Rev. 2:

- pool de parejas = TODOS los sábados (incl. sábados-festivo, D11),
- bloqueos de 72 h alrededor de cada guardia de sábado en `libre()` (D11),
- cuotas fijas 6/6/6 con festivos `f` y relleno LMX por debajo del objetivo
  (D9/D10),
- compensación de parejas con jueves festivo (+1 jueves normal, §5-F4c).

Fases: F1 calendario (en `calendario.py`) · F3 cuotas (`cuotas.py`) ·
F4 equipo (parejas → resto de categorías → compensación) · F5 área ·
F6 bolsa. La validación F7 vive en `validar_resultado.py`.
"""

from __future__ import annotations

import datetime
import random
from dataclasses import dataclass, field

from .calendario import Calendario, Dia
from .cuotas import Cuotas, calcular_cuotas, factibilidad

LETRAS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


# ---------------------------------------------------------------------------
# Estado por enfermera
# ---------------------------------------------------------------------------

class Estado:
    """Contadores de cuotas y horas de UNA enfermera."""

    def __init__(self) -> None:
        self.fechas: set[datetime.date] = set()
        self.cont: dict[str, int] = {"S": 0, "D": 0, "V": 0, "J": 0, "F": 0, "LMX": 0}
        self.horas: int = 0

    @property
    def total(self) -> int:
        return sum(self.cont.values())

    def put(self, dia: Dia) -> None:
        """Registra una guardia y acumula su categoría de cuota (Rev. 2)."""
        self.fechas.add(dia.fecha)
        self.horas += dia.horas
        self.cont[categoria_dia(dia)] += 1


def categoria_dia(dia: Dia) -> str:
    """Categoría de cuota de un día (Rev. 2): sábado-festivo → 'S' (D11);
    festivo no sábado → 'F'; resto por weekday."""
    if dia.weekday == 5:
        return "S"                       # todo sábado, festivo o no, es un "sábado"
    if dia.festivo:
        return "F"
    if dia.weekday == 6:
        return "D"
    if dia.weekday == 4:
        return "V"
    if dia.weekday == 3:
        return "J"
    return "LMX"


def libre(estados: dict[str, Estado], nombre: str, fecha: datetime.date) -> bool:
    """¿Puede `nombre` tener guardia ese día? — descanso de 72 h alrededor de
    los sábados propios (D11) y no-consecutividad (§3.5), a nivel de día:

    - respecto de un SÁBADO propio existente: bloqueados −2, −1 y +1…+4
      (el jueves +5 es su pareja y está permitido),
    - respecto de un JUEVES propio existente: bloqueados −1, +1 y el sábado +2,
    - el resto de guardias existentes: bloqueados ±1 (no consecutivos).
    """
    st = estados[nombre]
    if fecha in st.fechas:
        return False
    for dd_ in st.fechas:
        k = (fecha - dd_).days
        wd = dd_.weekday()
        if wd == 5:                                   # sábado propio existente
            if k in (-2, -1, 1, 2, 3, 4):
                return False
        elif wd == 3:                                 # jueves propio existente
            if k in (-1, 1, 2):
                return False
        elif k in (-1, 1):                            # resto: no consecutivos
            return False
    return True


def elegir(candidatas: list[str], estados: dict[str, Estado], clave: str,
           fecha: datetime.date) -> str:
    """Enfermera con menos guardias de la categoría (empate: menos total y más
    días sin guardia) — heurística del modelo validado en 2027."""
    def orden(n: str) -> tuple:
        st = estados[n]
        gap = min((fecha - f).days for f in st.fechas) if st.fechas else 999
        return (st.cont[clave], st.total, gap, n)
    return min(candidatas, key=orden)


def reparto_proporcional(conts: dict[str, dict[str, int]]) -> bool:
    """True si el reparto de categorías entre las enfermeras es proporcional:
    la menor ≥ 70 % de la mayor en cada categoría (atrapa el caso «23
    sábados y 10 domingos»); tolera categorías con pocas celdas libres
    (menos de 8 en total) y grupos de una sola enfermera."""
    for clave in ("S", "D", "V", "J", "F", "LMX"):
        valores = [c.get(clave, 0) for c in conts.values()]
        if max(valores) >= 8 and min(valores) * 10 < max(valores) * 7:
            return False
    return True


# ---------------------------------------------------------------------------
# Resultado
# ---------------------------------------------------------------------------

@dataclass
class Asignacion:
    """Salida del solver: celdas por enfermera + bolsa «Vacío» (D5)."""

    anio: int
    equipo: dict[str, list[str]]      # letra → fechas ISO ordenadas
    area: dict[str, list[str]]        # 'R1'… → fechas ISO ordenadas
    bolsa: list[dict]                 # [{'fecha': ISO, 'celda': i, 'horas': h}]
    festivos: list[str]               # festivos efectivos del año (ISO)
    informe: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Solver
# ---------------------------------------------------------------------------

class Solver:
    def __init__(self, cal: Calendario, n_equipo: int, n_area: int, modulos: int,
                 horas_equipo: int, cuotas: Cuotas, horas_area: int = 0):
        self.cal = cal
        self.n_equipo = n_equipo
        self.n_area = n_area
        self.modulos = modulos
        self.horas_equipo = horas_equipo
        self.horas_area = horas_area        # 0 = sin límite (cubren celdas libres)
        self.cuotas = cuotas
        # Orden aleatorio de los rellenos: reparte las celdas sin cubrir por
        # todo el año (no se acumulan al final). Semilla fija por año para
        # que el resultado sea reproducible.
        self.rng = random.Random(cal.anio)
        self.equipo = [LETRAS[i] for i in range(n_equipo)]
        self.area = [f"R{i + 1}" for i in range(n_area)]
        self.eq: dict[str, Estado] = {n: Estado() for n in self.equipo}
        self.ar: dict[str, Estado] = {n: Estado() for n in self.area}

        # celdas por fecha: lista de `modulos` casillas None ('eq', n) / ('ar', n)
        self.celdas: dict[datetime.date, list[tuple[str, str] | None]] = {
            dd.fecha: [None] * modulos for dd in cal.dias}

    # -- registro ----------------------------------------------------------
    def put(self, grupo: str, nombre: str, fecha: datetime.date) -> None:
        dia = self.cal.por_fecha(fecha)
        (self.eq if grupo == "eq" else self.ar)[nombre].put(dia)
        celdas = self.celdas[fecha]
        i = next(i for i, v in enumerate(celdas) if v is None)
        celdas[i] = (grupo, nombre)

    def equipo_en_dia(self, fecha: datetime.date) -> list[str]:
        return [c[1] for c in self.celdas[fecha] if c and c[0] == "eq"]

    def area_en_dia(self, fecha: datetime.date) -> list[str]:
        return [c[1] for c in self.celdas[fecha] if c and c[0] == "ar"]

    def hueco(self, fecha: datetime.date) -> bool:
        return any(v is None for v in self.celdas[fecha])

    # -- F4a: parejas sábado → jueves +5 ------------------------------------
    def parejas(self) -> None:
        """Pareja emblemática (§3.3): TODO sábado del pool lleva su jueves +5
        de la misma enfermera; los sábados-festivo también (D11)."""
        fin = datetime.date(self.cal.anio, 12, 31)
        pool = self.cal.dias_de("S")            # sábados emparejables
        pool = list(pool)
        self.rng.shuffle(pool)                  # reparte las no cubiertas
        npairs = self.cuotas.sabados * self.n_equipo
        dobles = max(0, npairs - len(pool))
        if self.modulos == 2 and dobles:
            paso = len(pool) / dobles
            con_doble_fmt = {int(round((k + 0.5) * paso)) for k in range(dobles)}
        else:
            con_doble_fmt = set()

        jueves_fest: dict[str, int] = {}
        for i, dd in enumerate(pool):
            sat = dd.fecha
            jt = sat + datetime.timedelta(days=5)
            if jt > fin:
                continue
            k = 2 if i in con_doble_fmt else 1
            k = min(k, self.modulos)
            cands = [n for n in self.equipo
                     if self.eq[n].cont["S"] < self.cuotas.sabados
                     and libre(self.eq, n, sat) and libre(self.eq, n, jt)]
            cands.sort(key=lambda n: (self.eq[n].cont["S"], self.eq[n].total, n))
            for n in cands[:k]:
                self.put("eq", n, sat)
                self.put("eq", n, jt)
                if self.cal.por_fecha(jt).festivo:
                    jueves_fest[n] = jueves_fest.get(n, 0) + 1

        self.parejas_reparacion(pool)
        self.compensar_jueves_festivo(jueves_fest)

    def parejas_reparacion(self, pool: list[Dia]) -> None:
        """Pasada de reparación: enfermeras con sábados pendientes → completar
        en sábados con hueco cuyo jueves +5 esté libre, aunque haya que relajar
        un bloqueo del jueves (la guardia del sábado se mantiene)."""
        fin = datetime.date(self.cal.anio, 12, 31)
        for n in self.equipo:
            while self.eq[n].cont["S"] < self.cuotas.sabados:
                sats_propios = {f for f in self.eq[n].fechas if f.weekday() == 5}
                libres = []
                for dd in pool:
                    s, jt = dd.fecha, dd.fecha + datetime.timedelta(days=5)
                    if (s > fin or s in sats_propios or s in self.eq[n].fechas
                            or jt > fin or jt in self.eq[n].fechas):
                        continue
                    if self.hueco(s) and self.hueco(jt):
                        libres.append(dd)
                if not libres:
                    break
                self.put("eq", n, libres[0].fecha)
                self.put("eq", n, libres[0].fecha + datetime.timedelta(days=5))

    def compensar_jueves_festivo(self, jueves_fest: dict[str, int]) -> None:
        """Pareja con jueves festivo → +1 jueves ORDINARIO para la misma
        enfermera (precedente 2027: sáb 20/3 → jue 25/3, compensada con
        otro jueves; §3.3 y §5-F4c).

        Se prefiere un jueves cuyos días vecinos NO sean festivos de pool F:
        un jueves junto a un festivo (p. ej. 30/12 → bloquearía el 31/12)
        quemaría la única celta festiva que le queda a la enfermera."""
        if not jueves_fest:
            return
        pool_f = {dd.fecha for dd in self.cal.dias_de("F")}
        orden = self.cal.dias_de("Jordinarios")
        for n, cuantos in jueves_fest.items():
            for _ in range(cuantos):
                if self.eq[n].cont["J"] >= self.cuotas.jueves:
                    break
                cands = [dd for dd in orden
                         if self.hueco(dd.fecha) and libre(self.eq, n, dd.fecha)]
                if not cands:
                    break

                def penal(dd: Dia) -> tuple:
                    vecinos = {dd.fecha + datetime.timedelta(days=o)
                               for o in (-2, -1, 1, 2)}
                    vecinos.add(dd.fecha + datetime.timedelta(days=2))
                    quema = sum(1 for f_ in vecinos if f_ in pool_f)
                    lejos = min((dd.fecha - f).days for f in self.eq[n].fechas)
                    return (quema, -abs(lejos), dd.fecha)

                dd = min(cands, key=penal)
                self.put("eq", n, dd.fecha)

    # -- F4b: resto de categorías -------------------------------------------
    def permitidas_equipo(self, dia: Dia) -> int:
        """Máximo de celdas de EQUIPO ese día: m; los festivos especiales son
        mitad/mitad → 1 (§3.4)."""
        if dia.especial:
            return 1
        return self.modulos

    def rellenar(self, clave: str, dias: list[Dia], metas: dict[str, int],
                 paridad_m1: bool = False) -> None:
        """Asigna 1 guardia por día (más 'dobles' repartidas uniformemente,
        heurística del modelo 2027) respetando metas por enfermera, celdas
        permitidas, bloqueos 72 h y no-consecutividad. Termina con una pasada
        de reparación para las metas pendientes."""
        necesidad = sum(metas.values()) - sum(self.eq[n].cont[clave]
                                              for n in self.equipo)
        dobles = max(0, necesidad - len(dias))
        con_doble: set[int] = set()
        if dobles > 0 and len(dias) > 0:
            paso = len(dias) / dobles
            con_doble = {int(round((k + 0.5) * paso)) for k in range(dobles)}
        dias = list(dias)
        self.rng.shuffle(dias)                  # reparte las celdas sin cubrir
        for i, dd in enumerate(dias):
            if paridad_m1 and i % 2 == 1:
                continue                      # festivos alternos empezando por equipo
            permitidas = min(self.permitidas_equipo(dd), self.modulos)
            k = 1 + (1 if i in con_doble else 0)
            for _ in range(k):
                if len(self.equipo_en_dia(dd.fecha)) >= permitidas:
                    break
                cands = [n for n in self.equipo
                         if self.eq[n].cont[clave] < metas.get(n, 0)
                         and libre(self.eq, n, dd.fecha)
                         and n not in self.equipo_en_dia(dd.fecha)]
                if not cands:
                    break
                self.put("eq", elegir(cands, self.eq, clave, dd.fecha), dd.fecha)
        self.reparar(clave, dias, metas, paridad_m1=paridad_m1)

    def reparar(self, clave: str, dias: list[Dia], metas: dict[str, int],
                paridad_m1: bool = False) -> None:
        """Enfermeras con meta pendiente: completarlas en días con hueco de
        equipo (mayor déficit primero). Se detiene si no hay progreso."""
        for _ in range(4 * len(dias) + 8):
            faltanos = [n for n in self.equipo
                        if self.eq[n].cont[clave] < metas.get(n, 0)]
            if not faltanos:
                return
            faltanos.sort(key=lambda n: (metas.get(n, 0) - self.eq[n].cont[clave], n),
                          reverse=True)
            progreso = False
            for n in faltanos:
                colocado = False
                for dd in dias:
                    if len(self.equipo_en_dia(dd.fecha)) >= min(
                            self.permitidas_equipo(dd), self.modulos):
                        continue
                    if n in self.equipo_en_dia(dd.fecha):
                        continue
                    if not libre(self.eq, n, dd.fecha):
                        continue
                    self.put("eq", n, dd.fecha)
                    colocado = True
                    progreso = True
                    break
                if progreso and colocado:
                    break                     # reevaluar el orden de déficit
            if not progreso:
                return

    def resto_categorias(self) -> None:
        """F4b: domingos, viernes, relleno LMX (D10) y festivos (§3.4)."""
        self.rellenar("D", self.cal.dias_de("D"),
                      {n: self.cuotas.domingos for n in self.equipo})
        self.rellenar("V", self.cal.dias_de("V"),
                      {n: self.cuotas.viernes for n in self.equipo})
        self.rellenar("F", self.cal.dias_de("F"), metas_festivos(self),
                      paridad_m1=(self.modulos == 1))
        self.rellenar("LMX", self.cal.dias_de("LMX"), metas_lmx(self))

    def libres_en(self, fecha: datetime.date) -> int:
        """Celdas sin nadie (equipo ni área) ese día."""
        return sum(1 for v in self.celdas[fecha] if v is None)

    # -- F5: área ------------------------------------------------------------
    def _pasada_area(self, dd: Dia, tope: int, dejar: int = 0) -> None:
        """Intenta cubrir celdas libres del día `dd` con enfermeras de área:
        se elige la de MENOS guardias de la categoría del día (reparto
        proporcional S/D/V/J/F/LMX), luego menos horas, menos guardias y
        nombre; nunca dos en el mismo día; NUNCA dos días seguidos (regla
        dura); con tope, solo si sigue por debajo del objetivo. `dejar`
        reserva celdas para la bolsa («Vacío»)."""
        ocupadas = self.area_en_dia(dd.fecha)
        # celdas libres para el área hoy, menos las reservadas para la bolsa
        cupo = max(0, self.libres_en(dd.fecha) - dejar)
        for _ in range(cupo):
            if not self.hueco(dd.fecha):
                break
            cabe = [a for a in self.area
                    if a not in ocupadas
                    and (not tope or self.ar[a].horas + dd.horas <= tope)]
            if not cabe:
                break                 # todas se pasarían → bolsa
            vecindad = {dd.fecha + datetime.timedelta(days=1),
                        dd.fecha - datetime.timedelta(days=1)}
            # regla dura: sin dos días seguidos (si nadie cabe → bolsa)
            cands = [a for a in cabe
                     if not (self.ar[a].fechas & vecindad)]
            if not cands:
                break
            cat = categoria_dia(dd)
            a = min(cands, key=lambda x: (self.ar[x].cont[cat],
                                          self.ar[x].horas,
                                          self.ar[x].total, x))
            self.put("ar", a, dd.fecha)
            ocupadas.append(a)            # evita duplicar en el mismo día

    def rellenar_area(self) -> None:
        """F5: cubre celdas libres con el área; las restantes van a la bolsa
        «Vacío».

        La bolsa, además de repartirse por todo el año (orden aleatorio),
        intenta que sus días NO queden seguidos: una pasada sonda mide la
        capacidad real del área y las celdas que quedará sin cubrir se
        reservan eligiendo días sin adyacencias (best effort: si la bolsa
        supera la mitad de los días, es imposible). Se hacen hasta 3 intentos
        y se queda el de menos bolsa."""
        tope = self.horas_area
        dias = list(self.cal.dias)

        # -- pasada sonda: ¿cuántas celdas puede cubrir el área de verdad? --
        sondeo = list(dias)
        self.rng.shuffle(sondeo)
        for dd in sondeo:
            self._pasada_area(dd, tope)
        cubiertas_sonda = sum(len(st.fechas) for st in self.ar.values())
        f_total = cubiertas_sonda + sum(self.libres_en(dd.fecha) for dd in dias)
        self._reset_area()

        # -- intentos: reservar la bolsa en días SIN adyacencias y cubrir el --
        # resto (los días reservados se intentan al final, por si sobra
        # capacidad real). Se queda el intento con menos bolsa y menos días
        # de bolsa seguidos.
        orden = list(dias)
        self.rng.shuffle(orden)
        pend = f_total - cubiertas_sonda          # celdas que quedará sin cubrir
        mejor = None                              # ((pares, bolsa), instantánea)
        for _ in range(3):
            saltar = self._reservar_bolsa(orden, pend)
            for dd in orden:
                self._pasada_area(dd, tope, saltar.get(dd.fecha, 0))
            for dd in orden:                      # último intento en reservados
                if dd.fecha in saltar:
                    self._pasada_area(dd, tope, 0)
            cubiertas = sum(len(st.fechas) for st in self.ar.values())
            bolsa = f_total - cubiertas
            clave = (self._pares_bolsa(), bolsa)
            if mejor is None or clave < mejor[0]:
                mejor = (clave, self._snapshot())
            if bolsa == 0:
                break
            pend = bolsa                          # reintentar con el nuevo objetivo
            self._reset_area()

        if mejor is not None:
            self._restaurar(mejor[1])
        self._reparar_pares()

    def _reparar_pares(self) -> None:
        """Post-optimización: rompe parejas de días de bolsa SEGUIDOS moviendo
        una guardia de área desde otro día cuyos vecinos quedan cubiertos
        hacia uno de los días del par. No cambia el total de celdas cubiertas
        y respeta el tope de horas y la no-consecutividad. Termina cuando
        ningún par es rompible (imposibilidad estructural)."""
        tope = self.horas_area
        fs = sorted(f for f, v in self.celdas.items()
                    if any(c is None for c in v))
        # los intercambios nunca crean pares nuevos (el día donante exige
        # vecinos cubiertos), así que basta una pasada por los pares iniciales
        for a, b in zip(fs, fs[1:]):
            if (b - a).days != 1:
                continue
            while True:                       # agota este par: cubre a y luego b
                if self._cubrir_con_swap(a, tope):
                    continue
                if self._cubrir_con_swap(b, tope):
                    continue
                break

    def _cubrir_con_swap(self, objetivo: datetime.date, tope: int) -> bool:
        """Intenta cubrir una celda de `objetivo` (día con celda en bolsa)
        moviendo una guardia de área: una enfermera deja un día `x` (cuyos
        vecinos quedan cubiertos, para no crear un par nuevo) y toma
        `objetivo`. Devuelve True si lo logra."""
        da = self.cal.por_fecha(objetivo)
        cat_obj = categoria_dia(da)
        bolsa_antes = {f for f, v in self.celdas.items()
                       if any(c is None for c in v)}
        misma_cat: list[tuple[str, datetime.date]] = []
        otras: list[tuple[int, str, datetime.date]] = []
        for n in self.area:
            st = self.ar[n]
            if objetivo in st.fechas:
                continue
            for x in sorted(st.fechas):
                if x == objetivo or x in bolsa_antes:
                    continue      # el donante debe estar totalmente cubierto
                dx = self.cal.por_fecha(x)
                if tope > 0 and st.horas - dx.horas + da.horas > tope:
                    continue                  # se pasaría del objetivo
                # sin dos días seguidos tras el movimiento (x ya no cuenta)
                resto = st.fechas - {x}
                if (objetivo + datetime.timedelta(days=1) in resto
                        or objetivo - datetime.timedelta(days=1) in resto):
                    continue
                # x queda sin esa guardia: vecinos deben seguir cubiertos
                if any(v in bolsa_antes and v != objetivo
                       for v in (x - datetime.timedelta(days=1),
                                 x + datetime.timedelta(days=1))):
                    continue
                if categoria_dia(dx) == cat_obj:
                    misma_cat.append((n, x))  # el reparto no cambia
                    continue
                # donante de otra categoría: solo si el reparto por
                # categorías sigue proporcional tras el movimiento
                cont_nuevo = {m: dict(self.ar[m].cont) for m in self.area}
                cat_x = categoria_dia(dx)
                cont_nuevo[n][cat_x] -= 1
                cont_nuevo[n][cat_obj] += 1
                if reparto_proporcional(cont_nuevo):
                    otras.append((st.cont[cat_x], n, x))
        if misma_cat:
            n, x = misma_cat[0]
        elif otras:
            _, n, x = max(otras)
        else:
            return False
        self._quitar_guardia(n, x)
        self.put("ar", n, objetivo)
        return True

    def _quitar_guardia(self, n: str, fecha: datetime.date) -> None:
        """Retira la guardia de área de `n` en `fecha` (estado y celda)."""
        st = self.ar[n]
        dia = self.cal.por_fecha(fecha)
        st.fechas.discard(fecha)
        st.horas -= dia.horas
        st.cont[categoria_dia(dia)] -= 1
        celdas = self.celdas[fecha]
        i = next(i for i, v in enumerate(celdas) if v == ("ar", n))
        celdas[i] = None

    def _pares_bolsa(self) -> int:
        """Nº de parejas de días CONSECUTIVOS con celdas en bolsa."""
        fs = sorted(f for f, v in self.celdas.items()
                    if any(c is None for c in v))
        return sum(1 for a, b in zip(fs, fs[1:]) if (b - a).days == 1)

    def _reservar_bolsa(self, orden: list[Dia], pend: int
                        ) -> dict[datetime.date, int]:
        """Elige `pend` celdas para dejar en bolsa, preferentemente en días
        sin adyacencias: 1.ª pasada greedy sin días seguidos; 2.ª completa
        con lo que falte (imposible cuando la bolsa > mitad de los días)."""
        saltar: dict[datetime.date, int] = {}     # fecha → celdas a dejar vacías
        for dd in orden:                          # 1.ª pasada: no adyacentes
            if pend <= 0:
                break
            libres_hoy = self.libres_en(dd.fecha)
            f = dd.fecha
            if libres_hoy == 0 or f in saltar:
                continue
            if (f + datetime.timedelta(days=1) in saltar
                    or f - datetime.timedelta(days=1) in saltar):
                continue
            n = min(libres_hoy, pend)
            saltar[f] = n
            pend -= n
        for dd in orden:                          # 2.ª pasada: como se pueda
            if pend <= 0:
                break
            libres_hoy = self.libres_en(dd.fecha)
            ya = saltar.get(dd.fecha, 0)
            n = min(libres_hoy - ya, pend)
            if n > 0:
                saltar[dd.fecha] = ya + n
                pend -= n
        return saltar

    def _snapshot(self) -> tuple:
        """Copia del estado del área (para conservar el mejor intento)."""
        ar = {n: (set(st.fechas), dict(st.cont), st.horas)
              for n, st in self.ar.items()}
        celdas = {f: list(v) for f, v in self.celdas.items()}
        return ar, celdas

    def _restaurar(self, snap: tuple) -> None:
        ar, celdas = snap
        for n, (fechas, cont, horas) in ar.items():
            st = Estado()
            st.fechas = set(fechas)
            st.cont = dict(cont)
            st.horas = horas
            self.ar[n] = st
        for f, v in celdas.items():
            self.celdas[f] = list(v)

    def _reset_area(self) -> None:
        """Deshace las guardias de área (quedan solo las del equipo)."""
        self.ar = {n: Estado() for n in self.area}
        for f, v in self.celdas.items():
            self.celdas[f] = [c if (c is not None and c[0] == "eq") else None
                              for c in v]

    # -- F6: bolsa -----------------------------------------------------------
    def celdas_bolsa(self) -> list[dict]:
        """Celdas sin cubrir → «Vacío» (bolsa de horas manual, D5)."""
        salida = []
        for dd in self.cal.dias:
            for i, v in enumerate(self.celdas[dd.fecha]):
                if v is None:
                    salida.append({"fecha": dd.fecha.isoformat(), "celda": i,
                                   "horas": dd.horas})
        return salida

    # -- resolución completa --------------------------------------------------
    def resolver(self) -> Asignacion:
        if self.n_equipo:
            self.parejas()
            self.resto_categorias()
        self.rellenar_area()
        return self._asignacion()

    def _asignacion(self) -> Asignacion:
        return Asignacion(
            anio=self.cal.anio,
            equipo={n: sorted(d.isoformat() for d in self.eq[n].fechas)
                    for n in self.equipo},
            area={n: sorted(d.isoformat() for d in self.ar[n].fechas)
                  for n in self.area},
            bolsa=self.celdas_bolsa(),
            festivos=sorted(d.isoformat() for d in self.cal.festivos),
        )


# ---------------------------------------------------------------------------
# Metas dinámicas (D9/D10)
# ---------------------------------------------------------------------------

def metas_festivos(solver: Solver) -> dict[str, int]:
    """Meta f por enfermera (regla de tope sobre el contador total):
    los festivos que baja de las parejas (jueves festivos) ya cuentan hacia
    la misma cuota, así que el relleno completa hasta f en total."""
    return {n: solver.cuotas.festivos for n in solver.equipo}


def metas_lmx(solver: Solver) -> dict[str, int]:
    """Relleno LMX: nunca por encima del objetivo de horas (D10). Por
    enfermera: restar del objetivo las horas ya comprometidas (incluida la
    base 6/6/6) y los festivos que aún puede recibir (24 h cada uno)."""
    if not solver.n_equipo:
        return {}
    metas_f = metas_festivos(solver)
    salida = {}
    for n in solver.equipo:
        horas_actuales = solver.eq[n].horas
        pendiente_fest = max(0, metas_f[n] - solver.eq[n].cont["F"])
        reserva_fest = 24 * pendiente_fest
        hueco_horas = solver.horas_equipo - horas_actuales - reserva_fest
        salida[n] = max(0, min(solver.cuotas.lmx, hueco_horas // 17))
    return salida


# ---------------------------------------------------------------------------
# Orquestación F2..F6
# ---------------------------------------------------------------------------

def resolver_plan(cal: Calendario, n_equipo: int, n_area: int, modulos: int,
                  horas_equipo: int, horas_area: int = 0
                  ) -> tuple[Asignacion | None, str, Cuotas]:
    """Devuelve (asignación, error, cuotas): error ≠ "" ⇒ no se genera (R13)."""
    cuotas = calcular_cuotas(cal, n_equipo, modulos, horas_equipo)
    ok, msg = factibilidad(cal, n_equipo, modulos)
    if not ok:
        return None, msg, cuotas
    solver = Solver(cal, n_equipo, n_area, modulos, horas_equipo, cuotas,
                    horas_area)
    asign = solver.resolver()
    asign.informe["cuotas_f"] = cuotas.festivos
    asign.informe["cuotas_lmx"] = cuotas.lmx
    asign.informe["avisos"] = list(cuotas.avisos)
    asign.informe["desvio"] = cuotas.desvio
    return asign, "", cuotas
