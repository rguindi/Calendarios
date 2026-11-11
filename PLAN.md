# PLAN DE EJECUCIÓN — Generador de calendarios de guardias de enfermería

> **Este plan es autocontenido.** Una sesión nueva debe poder ejecutarlo sin más contexto.
> La lógica de negocio que describe está **extraída y validada** contra un calendario real
> (año 2027) construido con el mismo modelo Excel: cada regla de cómputo de este documento
> fue verificada emulando las fórmulas del propio modelo.
>
> **Rev. 2 (10/11/2026):** incorpora los ajustes del cliente (reglas R13, R14, R17, R21 y
> R23 del documento `REGLAS_NEGOCIO.md`): cuotas fijas 6/6/6, horas por debajo del
> objetivo, festivo en sábado emparejado + descanso de 72 h, y festivos en morado.
> Además, nuevo campo **Año** en el formulario con inicial = año siguiente al actual (D13).

---

## 0. Instrucciones para la sesión ejecutora

1. Lee este plan completo antes de escribir código.
2. Lee el código de referencia en `referencia/` (son scripts de una sola pieza, ya
   probados y hardcoded al año 2027; tu trabajo es **portarlos** a módulos genéricos):
   - `referencia/solver_2027.py` — algoritmo completo de asignación (parejas, reparto,
     área, compensaciones) validado con el caso 2027.
   - `referencia/verificar_2027.py` — emulador de las fórmulas de resumen del Excel
     (parsea los COUNTIF reales y los evalúa sobre la cuadrícula).
   - `referencia/writer_2027.py` — escritura del Excel preservando estilos.
   - `referencia/golden_2027.json` — asignación completa del año 2027 validada con las
     reglas **anteriores** a la Rev. 2; sirve de referencia de mecánica, pero el golden
     esperado debe **regenerarse** con las reglas actuales (§7).
3. Implementa en `logica/` según el roadmap (§10). **No toques `app.py`** (regla del README
   del proyecto): solo `logica/excel_logica.py`, `config/parametros.py` (declarativo,
   ver D13) y los módulos nuevos que crees.
4. Entorno: Python 3.12 con `.venv` del proyecto; dependencias `streamlit`, `openpyxl`
   (ya en `requirements.txt`). No se necesitan privilegios ni dependencias nuevas
   obligatorias (`holidays` es opcional, §2).

---

## 1. Qué hace la aplicación

Recibir del formulario de `app.py` (Streamlit) unos parámetros, y devolver un **libro
Excel del calendario anual de guardias** generado desde cero (cualquier año), con:

- la cuadrícula anual rellenada con las enfermeras (equipo: A, B, C… · área: R1, R2…),
- los **festivos pintados en morado** (especiales en morado oscuro),
- las celdas sin cubrir marcadas **"Vacío"** en naranja (**bolsa de horas manual**),
- estadísticas mensuales y bloque de resumen con fórmulas COUNTIF,
- **una hoja de detalle por enfermera** (su calendario y sus totales).

y un `mensaje` con el informe: horas sin cubrir, bolsa de horas, desvíos y avisos.

---

## 2. Entrada del formulario (formato ya fijado)

```python
{'enfermeras': 10, 'enfermeras_area': 2, 'modulos_guardia': 1,
 'horas_equipo': 1800, 'horas_area': 1900, 'anio': 2026,
 'festivos': ['2026-07-24', '2026-01-30']}
```

| Campo | Significado | Decisiones |
|---|---|---|
| `enfermeras` | nº de enfermeras de equipo | etiquetas A, B, C… |
| `enfermeras_area` | nº de enfermeras de área | etiquetas R1, R2… |
| `modulos_guardia` | enfermeras simultáneas de guardia = celdas/día | **siempre 1 o 2** (D1) |
| `horas_equipo` | horas objetivo por enfermera de equipo | **techo: nunca se supera** (D10); el desvío se informa |
| `horas_area` | horas objetivo por enfermera de área | se cubre con "el resto" de horas |
| `anio` | **año del calendario a generar** | campo nuevo en `config/parametros.py` (D13); inicial = **año siguiente al actual** |
| `festivos` | festivos **locales** (ISO) del año `anio` | se **suman** a los precargados (D2/D6) |

**Otras decisiones ya confirmadas (con el usuario):**

| | Decisión |
|---|---|
| D2 | Festivos nacionales/autonómicos **precargados automáticamente** (librería `holidays` país ES + Castilla y León, o API de festivos); la lista del formulario aporta los **locales**. El conjunto final = precargados + formulario, y es la fuente de verdad |
| D3 | `horas_equipo` y `horas_area` son **objetivos**; si sobran horas quedan libres |
| D4 | El libro se **genera por código para cualquier año** (no se rellena una plantilla fija) |
| D5 | Las celdas sin cubrir = **bolsa de horas para asignación manual**: "Vacío" en naranja, el solver **no** las rellena |
| D6 | La precarga de festivos (D2) se calcula **en la lógica (backend)** para el año elegido, no en el front: `app.py` sigue intacto |
| D7 | Hoja de detalle por enfermera en el Excel |
| D8 | Cuotas "XXXXX" **equitativas**: el mismo nº de guardias por enfermera — §4 |
| D9 *(Rev. 2, cliente)* | **Cuotas fijas: exactamente 6 viernes, 6 sábados y 6 domingos** por enfermera de equipo (no dependen del nº de enfermeras). Si con la plantilla indicada no cabe, la app **informa de la imposibilidad** y no genera — §4 |
| D10 *(Rev. 2, cliente)* | Si el objetivo de horas no es alcanzable exactamente, el resultado se queda **por debajo, nunca por encima**, informando del desvío — §4 |
| D11 *(Rev. 2, cliente)* | **Descanso de 72 h alrededor de cada guardia de sábado** del equipo: sin guardias el jueves (−2) ni el viernes (−1) anteriores, ni del domingo al miércoles (+1…+4) posteriores; la norma es **sábado → jueves siguiente (+5)** de la misma enfermera (la variante de descansar el jueves *anterior* solo se usa a mano en puentes). Un **festivo en sábado cuenta como uno de los 6 sábados**, su jueves anterior queda de descanso y arrastra su jueves +5 — §3.3 |
| D12 *(Rev. 2, cliente)* | **Festivos en morado** (especiales en morado oscuro); el **naranja queda reservado a la bolsa** ("Vacío") — §6.3 |
| D13 *(10/11/2026)* | **El año se elige en el formulario**: campo `anio` en `config/parametros.py` (declarativo; añadirlo NO requiere tocar `app.py` porque el front recorre `CAMPOS_NUMERICOS`), clave `anio` (sin ñ), inicial = `date.today().year + 1` — el calendario que se planifica es el del **año siguiente**. Rangos amplios (p. ej. 2020–2100). Con ese año la lógica precarga los nacionales/autonómicos (D2/D6) y `validar()` rechaza festivos fuera de él |

---

## 3. Reglas de cómputo (núcleo del dominio)

### 3.1 Horas de cada celda de guardia

| Tipo de día | Horas | Prioridad |
|---|---|---|
| **Festivo** (formulario + especiales) | **24 h** | 1ª — aunque sea sábado, domingo o laborable |
| **Sábado no festivo** | **24 h** | 2ª |
| **Domingo** | **24 h** | 2ª |
| **Laborable no festivo** (L–V) | **17 h** | 3ª |

Precedencia: `festivo > sábado/domingo > laborable`. Un festivo en sábado puntúa **solo
como festivo** en los contadores de horas (caso 2027: 1/5 y 25/12 → 24 h en la columna
Fest, nunca en la columna Sáb del resumen — quirk de §6.2). **OJO (Rev. 2):** a efectos
de **cuotas** sí cuenta como uno de los 6 sábados de la enfermera y se empareja con su
jueves +5 (§3.3); lo único "festivo" es cómo puntúa la celda.

### 3.2 Horas totales de una enfermera

```
horas = 17 × (L + M + X + J + V)  +  24 × (S + D + Festivos)
```

- `Festivos` = TODOS los festivos trabajados (1/1 y 25/12 incluidos una sola vez;
  24/12 y 31/12 también puntúan 24 h).
- Una pareja sábado→jueves(+5) sin festivos aporta 24 + 17 = **41 h**.

### 3.3 Parejas sábado → jueves (+5) y descanso de 72 h — regla emblemática (Rev. 2)

**Necesidad real del cliente:** cada guardia de sábado de una enfermera de equipo exige
**72 horas de descanso alrededor**. Con la guardia de 24 h, eso se traduce en:

- **Sin guardias** para esa enfermera el **jueves (−2)** ni el **viernes (−1)** previos,
  ni el **domingo, lunes, martes o miércoles (+1…+4)** posteriores.
- Su siguiente guardia tras el sábado es el **jueves +5** — norma **sábado → jueves
  posterior**, que la aplicación aplica **siempre** (descansar el jueves *anterior* solo
  se usa a mano en puentes; no se genera).

Consecuencias operativas:

- **Cada sábado que trabaja una enfermera de equipo —festivo o no— arrastra el jueves
  +5 para la misma enfermera.** Los sábados-festivo (1/5 y 25/12 en 2027) también
  emparejan: se llevan su jueves +5 (6/5 y 30/12), que vuelve al pool del equipo.
  **Ya no existen "jueves huérfanos"**.
- Cada sábado admite hasta `min(2, modulos_guardia)` enfermeras emparejadas.
- Recíproco: una guardia de **jueves** de una enfermera le **bloquea el sábado +2**
  (ese sábado no puede ser suyo).
- Si el jueves +5 es **festivo**: pareja válida pero puntúa como festivo (24 h) →
  pareja de 48 h. **Compensación**: dar a esa enfermera un jueves normal extra
  (caso 2027: sábado 20/3 → jueves 25/3 festivo, compensada con el jueves 20/5),
  ajustando su relleno L–M–X para no superar el objetivo (D10).

### 3.4 Festivos: mitad equipo / mitad área

- `m = modulos_guardia = 2`: cada festivo → 1 celda equipo + 1 celda área.
- `m = 1`: los festivos se reparten **alternos** entre equipo y área (empezando por equipo).
- *(Rev. 2)* Las celdas de festivo del equipo se reparten **por igual entre las
  enfermeras (±1)** y en conjunto aproximan **la mitad de las celdas festivas**.
  Precedente 2027: para acercarse al objetivo salió **f = 2 por enfermera** (22 de 32
  celdas) en vez de la mitad estricta (16); el cliente lo aceptó. Con las cuotas fijas
  6/6/6, `f` y el relleno L–M–X son las palancas para acercarse al objetivo **por
  debajo** (D10; prioridades en §4). **Excepción**: los **sábados-festivo** consumen la
  cuota de sábados (D11), no la de festivos `f`.
- **Festivos especiales** (reparto obligatorio mitad/mitad): 1 de enero, 24, 25 y 31 de
  diciembre, y Jueves–Viernes–Sábado–Domingo de **Semana Santa**. Las fechas de Semana
  Santa se **derivan del domingo de Pascua** (algoritmo de Butcher) — nunca fijar 25–28/3.

### 3.5 Restricciones de calidad (obligatorias)

- Ninguna enfermera de equipo con guardias en **días consecutivos** (separación mínima ±1).
- **Descanso de 72 h alrededor de cada guardia de sábado** (D11): bloqueos a nivel de día
  en −2 y −1, y +1…+4; la pareja +5 es su siguiente guardia (§3.3).
- Distribución **homogénea**: mismo nº de guardias y de horas por enfermera (±1 día);
  **horas siempre ≤ objetivo** (D10).
- Cobertura: cada día tiene exactamente `modulos_guardia` celdas entre (equipo + área +
  bolsa "Vacío").

---

## 4. Cuotas "XXXXX" — fijas 6/6/6 + relleno por debajo del objetivo (Rev. 2)

Las "XXXXX" de las condiciones **ya no se derivan del nº de enfermeras**: el cliente fija
**exactamente 6 viernes, 6 sábados y 6 domingos por enfermera de equipo** (R13/D9). Los
jueves no son una cuota aparte: salen de las parejas sábado→jueves +5 (§3.3). Procedimiento:

1. Contar el año: `S` sábados (cuentan TODOS, incluidos los festivos), `D`, `V`, `J`,
   `Fest`, `LMX` (laborables L–M–X).
2. **Factibilidad de 6/6/6 (R13):** exigir `6 × n_equipo ≤ m × S`, `≤ m × D`, `≤ m × V`
   y `≤ m × J` (las parejas consumen celdas de jueves). Con 52 sábados: `m = 2` admite
   hasta **17** enfermeras de equipo; `m = 1` hasta **8**. Si no se cumple,
   `validar()`/`procesar()` **informa la imposibilidad** (con el máximo de enfermeras
   admisibles) y **no genera** un calendario que rompa la regla.
3. **Cuota fija:** `s = d = v = 6` por enfermera. Los 6 sábados **pueden incluir
   sábados-festivo** (D11); los 6 jueves vienen emparejados con ellos.
4. **Festivos `f` y relleno L–M–X (D10):** la base obligatoria es
   `6×24 + 6×24 + 6×17 + 6×17 = 492 h` (sáb+dom a 24 h, vie+jue a 17 h). Con ella, se
   eligen `f` (mitad de festivos, §3.4) y las guardias L–M–X para **maximizar las horas
   sin superar nunca `horas_equipo`**: `horas ≈ 492 + 24·f + 17·LMX (+ajustes por
   compensaciones) ≤ horas_equipo`.
5. Si la base 6/6/6 sola ya superara el objetivo (objetivo < 492 h), se informa de la
   incompatibilidad (la estructura 6/6/6 es obligatoria) y el relleno `f`/LMX queda en 0.
6. Devolver siempre el **desvío** final respecto a `horas_equipo` (p. ej. −4 h).

**Prioridad del solver:** 1ª) 6/6/6 exacto · 2ª) horas ≤ objetivo, maximizadas ·
3ª) equidad (mínima dispersión de horas entre enfermeras) · 4ª) mitad de festivos
aproximada (±1).

**Ejemplo validado (2027, 11 enfermeras de equipo, m=2, objetivo 884 h):**
52 sábados → capacidad 2×52 = 104 ≥ 6×11 ✓. Resultado:

| Por enfermera | Sáb | Dom | Vie | Jue (parejas) | Festivos | L–M–X | Guardias | Horas |
|---|---|---|---|---|---|---|---|---|
| cuota | 6 | 6 | 6 | 6 | 2 | 20 | **46** | **880** |

880 = 492 + 2×24 + 20×17, el máximo posible por debajo de 884 (no existe combinación de
sumandos 17/24 que dé 884). Se mantiene el precedente f=2 (§3.4). Los **totales** por
enfermera no cambian respecto a la Rev. 1; cambia **qué días** tocan: los sábados-festivo
1/5 y 25/12 entran en el pool de sábados y sus jueves 6/5 y 30/12 pasan a ser parejas de
equipo (ya no hay huérfanos).

**Ejemplo con la entrada del formulario (2026, 10 enfermeras, m=1, 1.800 h):**
6×10 = 60 sábados > 52 disponibles → **imposible por R13**: la app lo informa (máx. 8
enfermeras con m=1) y no genera. *A título orientativo, la oferta máxima de 2026 sería
259 laborables×17 + 106 (finde+festivos)×24 ≈ 6.947 h, también muy por debajo de la
demanda de 21.800 h.*

---

## 5. Algoritmo del solver (fases — ya validado en 2027)

```
F1. CALENDARIO: días del año `anio` (D13); por día → día_semana, ¿festivo? (locales del
    formulario + precargados de ese año), ¿especial? (Butcher sobre Pascua),
    horas de la celda (§3.1)
F2. FACTIBILIDAD: (a) regla R13 — 6×n_equipo ≤ m×min(S, D, V, J); si no, informar y NO
    generar (D9); (b) oferta vs demanda = horas_equipo×n_equipo + horas_area×n_área;
    avisos y máximos
F3. CUOTAS del equipo: s = d = v = 6 fijas (D9); f y LMX según D10 (§4)
F4. EQUIPO:
    a) PAREJAS sábado→jueves(+5): pool = TODOS los sábados, incluidos los festivo-sábado
       (D11). Para cada sábado asignar k enfermeras (k = 2 si es "doble", 1 si normal;
       los dobles se reparten uniformemente con índices int(round((k+0.5)·len(pool)/dobles)));
       elegir siempre la enfermera con menos sábados (empate: menos total, luego más
       días sin guardia).
       · BLOQUEOS 72 h — free(n, fecha) a nivel de día (D11): la enfermera no puede tener
         guardia el −2 ni el −1 respecto a su sábado, ni el +1…+4; y si tiene guardia un
         jueves, el sábado +2 no puede ser suyo.
       · pasada de REPARACIÓN: si a alguna enfermera le faltan sábados, completarla en
         sábados con hueco cuyo jueves (+5) esté libre, aunque haya que relajar un
         bloqueo del jueves (la guardia del sábado se mantiene)
    b) RESTO de categorías (domingos, viernes, festivos con la mitad de especiales, LMX):
       por categoría, 1 guardia por día + "dobles" repartidos uniformemente; elegir
       siempre la enfermera con menos de esa categoría (empate: menos total); nunca en
       un día ya lleno; respetar bloqueos 72 h y NO superar el objetivo en el relleno (D10)
    c) COMPENSACIÓN: enfermera con pareja en jueves-festivo → 1 jueves normal extra
       (2027: sáb 20/3 → jue 25/3, compensada con jue 20/5), ajustando su LMX para no
       pasar del objetivo
F5. ÁREA: recorrer los días; las celdas libres → elegir SIEMPRE la enfermera de área con
    MENOS horas acumuladas (empate: menos guardias, luego nombre); no repetir en el mismo
    día; evitar días consecutivos si es posible (con relajación si no hay candidata)
F6. BOLSA: celdas aún libres → "Vacío" (naranja). NO se rellenan (D5).
    Informe: nº de celdas y horas de la bolsa
F7. VALIDACIÓN (obligatoria antes de devolver): recorrer el resultado y comprobar
    · cobertura: cada día exactamente `modulos` celdas ocupadas+bolsa
    · equipo: exactamente 6 sábados (contando sábados-festivo), 6 domingos y 6 viernes
      por enfermera; 6 jueves vía parejas; f y LMX conforme a §4
    · parejas: TODO sábado con guardia de equipo (incluido el festivo-sábado) tiene su
      jueves +5 de la misma enfermera
    · descanso 72 h: ninguna guardia en −2/−1/+1…+4 de un sábado propio; un jueves
      propio nunca convive con su sábado +2
    · horas: TODAS las enfermeras ≤ objetivo; desvío conocido e informado
    · sin días consecutivos en equipo; área equitativa en horas (desviación mínima)
F8. SALIDA: generar el libro (§6) + Resultado(ok, mensaje, bytes, nombre)
```

Referencia de implementación: `referencia/solver_2027.py` (implementa F1–F6 para 2027
**con las reglas anteriores a la Rev. 2**: sábados-festivo sin pareja y `free()` solo ±1).
Al portarlo, aplicar las diferencias de este apartado: pool de sábados con festivos,
bloqueos 72 h en `free()`, cuotas fijas 6/6/6 y relleno por debajo del objetivo.

---

## 6. Especificación del libro Excel a generar

El libro se **genera por código con openpyxl**, replicando la maqueta de
`MODELOCALENDARIO2027.xlsx` (que queda como referencia visual y de fórmulas):

### 6.1 Maqueta

- **12 bloques de mes** (uno por fila de nombre en col D): filas de nombre
  4, 10, 16, 22, 28, 34, 41, 47, 53, 59, 65, 71 → 6 filas por bloque:
  nombre (+0), **números de día** (+1), **fila equipo** (+2), **fila área** (+3),
  2 filas auxiliares (+4, +5).
- Los días de cada mes se colocan según su día de la semana: las columnas E–AN son
  fijas por día de la semana (E=Miércoles, F=Jueves, G=Viernes, H=Sábado, I=Domingo,
  J=Lunes, K=Martes, y se repiten: L=Miércoles… hasta AN). El día 1 de cada mes cae en
  la columna de su weekday; un mes que empiece martes y tenga 31 días llega hasta la
  columna AN.
- **Estadísticas mensuales** a la derecha (cols AR en adelante), una tripleta por
  enfermera: cabecera en fila 1 (letra), fila 2 con `17`, `24`, `'T'`, y fórmulas en la
  **fila equipo de cada bloque** (+2).

### 6.2 Fórmulas (patrones reales de la plantilla — generalizar al año/festivos dados)

Para la enfermera con letra en `AR$1` y el bloque de ENERO (filas 5–9):

```
17 h (laborables):  =COUNTIF($M5:$N9,AR$1)+COUNTIF($Q5:$U9,AR$1)+COUNTIF($AE5:$AI9,AR$1)
                      +COUNTIF($J5:$J9,AR$1)+COUNTIF($K5:$K9,AR$1)+COUNTIF($X5:$AB9,AR$1)
24 h (finde+festivos): =COUNTIF($G6:$G9,AR$1)+COUNTIF($H6:$I9,AR$1)+COUNTIF($O6:$P9,AR$1)
                      +COUNTIF($AC6:$AD9,AR$1)+COUNTIF($V6:$W9,AR$1)+COUNTIF($AJ6:$AK9,AR$1)
                      +COUNTIF($L6:$L9,AR$1)
T:  =AR6*17+AS6*24
```

Lectura del patrón: para la columna de 17 h se agrupan **runs de columnas LMX
consecutivas** del bloque; para la de 24 h, runs de columnas de fin de semana **más cada
columna festiva** (1/1 en G, 6/1 en L). El generador debe construir estos grupos
dinámicamente según el año y los festivos.

Bloque de resumen anual (filas 78+), una fila por enfermera (equipo primero, luego área):

```
L (lunes):  COUNTIF sobre TODAS las columnas de lunes de todos los bloques (filas de guardia)
M, X, J, V, S, D: ídem con su día de la semana
F (festivos): COUNTIF por cada columna festiva del año — EXCLUYENDO 24/12 y 31/12
O (01.01): COUNTIF de la columna del 1 de enero   ·  P (24.12), Q (25.12), R (31.12): ídem
T: =((F+G+H+I+J)*17)+((K+L+N+P+R)*24)
W (guardias): =SUM(F:L)+SUM(R)+SUM(N)+SUM(P)
```

**QUIRK CRÍTICO (verificado):** un festivo que cae en día laborable **no se cuenta en la
columna de su día de la semana**. En la plantilla la fórmula de Jueves (col I) excluye
las filas del bloque de marzo para la columna AH (ahí está el 25/3, festivo). El
generador debe excluir del COUNTIF de cada día de la semana las celdas de los días
festivos de ese bloque.

### 6.3 Colores (Rev. 2 — convención del cliente, D12)

| Elemento | Color |
|---|---|
| Festivos "normales" | **morado claro** (p. ej. `FFC9A0DC`) en TODA la columna del día (las 5 filas del bloque) |
| Festivos **especiales** (1/1, Semana Santa, 24/12, 25/12, 31/12) | **morado oscuro** (p. ej. `FF7D3C98`) |
| Celdas "Vacío" (bolsa) | fondo **naranja** (`FFFFC000` de la plantilla) + texto "Vacío" |

- **El naranja queda reservado a la bolsa**: los festivos ya NO se pintan en naranja.
  Esto cambia la convención de la plantilla 2027 (theme 8 naranja, ámbar `FFC000` para
  17/5 y 29/6, theme 9 para 24/12 y 31/12) — el generador pinta morado siempre.
- El tono morado exacto puede ajustarse; lo innegociable es la **distinción festivo
  normal / especial** y que la bolsa sea lo único en naranja.

### 6.4 Hojas de detalle por enfermera (D7)

Una hoja por enfermera (equipo y área): mini-calendario del año (mes a mes, solo sus
guardias marcadas, festivos en morado) + tabla resumen: horas, guardias, L/M/X/J/V,
sábados (p. ej. **"6 sábados (5 ordinarios + 1 festivo)"**), domingos, viernes, festivos
trabajados, parejas sábado→jueves, y bolsa si la hay.

### 6.5 Título dinámico

Celda D1: `CALENDARIO TIPO ZAMORA PROFESIONALES <N> EAP CON <M> PROF AREA AÑO <año>`.

---

## 7. Golden test — año 2027 (entrada y salida esperadas)

**Entrada equivalente:**

```python
{'enfermeras': 11, 'enfermeras_area': 3, 'modulos_guardia': 2,
 'horas_equipo': 880, 'horas_area': 1460,
 'festivos': ['2027-01-01', '2027-01-06', '2027-03-25', '2027-03-26', '2027-04-23',
              '2027-05-01', '2027-05-17', '2027-06-29', '2027-08-16', '2027-10-12',
              '2027-11-01', '2027-12-06', '2027-12-08', '2027-12-24', '2027-12-25',
              '2027-12-31']}
```

**Salida esperada — ⚠️ REV. 2: REGENERAR.** Las tablas siguientes corresponden a las
reglas **anteriores** a la Rev. 2 (sábados-festivo sin pareja, jueves huérfanos). Se
conservan solo como referencia de mecánica del Excel. **El golden debe regenerarse con
las reglas actuales (R13 y D9–D12) y congelarse** (p. ej. `referencia/golden_2027_rev2.json`),
conservando esta misma entrada:

| Enf. | L | M | X | J | V | S | D | Fest | Horas | Guardias |
|---|---|---|---|---|---|---|---|---|---|---|
| A | 7 | 6 | 7 | 6 | 6 | 6 | 6 | 2 | 880 | 46 |
| B | 9 | 6 | 5 | 6 | 6 | 6 | 6 | 2 (31/12) | 880 | 46 |
| C | 7 | 7 | 6 | 6 | 6 | 6 | 6 | 2 | 880 | 46 |
| **D** | 5 | 7 | 8 | 6 | 6 | 6 | 6 | 2 | 880 | 46 |
| E | 8 | 5 | 7 | 6 | 6 | 6 | 6 | 2 (1/1) | 880 | 46 |
| F | 8 | 6 | 6 | 6 | 6 | 6 | 6 | 2 | 880 | 46 |
| G | 4 | 9 | 7 | 6 | 6 | 6 | 6 | 2 (24/12) | 880 | 46 |
| H | 4 | 8 | 8 | 6 | 6 | 6 | 6 | 2 | 880 | 46 |
| I | 7 | 6 | 7 | 6 | 6 | 6 | 6 | 2 | 880 | 46 |
| J | 5 | 8 | 7 | 6 | 6 | 6 | 6 | 2 (25/12) | 880 | 46 |
| K | 8 | 6 | 6 | 6 | 6 | 6 | 6 | 2 (31/12) | 880 | 46 |

| Área | L | M | X | J | V | S | D | Horas | Guardias |
|---|---|---|---|---|---|---|---|---|---|
| R1 | 8 | 7 | 8 | 11 | 12 | 12 | 13 | 1.454 | 74 |
| R2 | 4 | 7 | 8 | 16 | 7 | 12 | 17 | 1.458 | 73 |
| R3 | 12 | 12 | 10 | 9 | 11 | 10 | 8 | 1.470 | 77 |

**Propiedades que DEBE cumplir el golden regenerado (bajo Rev. 2):**

- Cada enfermera de equipo: **exactamente 6 sábados** (los sábados-festivo 1/5 y 25/12
  cuentan en esta cuota), **6 domingos, 6 viernes** y **6 jueves vía parejas**. Se espera
  que los totales sigan siendo 46 guardias / 880 h por enfermera (objetivo 880: se queda
  igual, nunca por encima).
- Los jueves **6/5 y 30/12** (antes "huérfanos") reciben las parejas de los
  sábados-festivo 1/5 y 25/12.
- Se cumple el **descanso de 72 h** (§3.3) y la pareja especial sáb 20/3 → jue 25/3
  festivo sigue compensándose con un jueves normal extra.
- 730 celdas cubiertas (365 × 2 módulos), bolsa 0.

**Criterio de aceptación del golden:** tras portar la lógica con las reglas Rev. 2,
todas las invariantes de §5-F7 deben cumplirse sobre el resultado 2027; congelar esa
asignación como `golden_2027_rev2.json` y usarla como test de regresión a partir de
entonces. (`referencia/golden_2027.json` queda SOLO como referencia de mecánica.)

---

## 8. Casos límite (catálogo real)

| # | Caso | Tratamiento |
|---|---|---|
| 1 | Festivo en sábado (1/5, 25/12) | Cuenta como uno de los 6 sábados; puntúa 24 h festivo (columna Fest, quirk §6.2); pareja con su jueves +5; su jueves −2 queda de descanso (D11) |
| 2 | Jueves festivo (25/3) | Pareja válida (48 h); compensar con un jueves normal extra |
| 3 | Más enfermeras que capacidad para 6/6/6 | R13 imposible → se informa y NO se genera. Con 52 sábados: m=1 admite máx. 8 de equipo; m=2, máx. 17 |
| 3b | Objetivo de horas < base obligatoria 6/6/6 (492 h) | La base 6/6/6 se mantiene (R13); relleno f+LMX a 0; se informa del exceso sobre el objetivo |
| 4 | Mes de 31 días que empieza martes | Llega hasta la columna 41 — dimensionar rangos correctamente |
| 5 | Demanda > oferta | Reparto equitativo de la oferta + informe de horas sin cubrir por grupo |
| 6 | Demanda < oferta | Celdas libres → bolsa "Vacío" (no se rellenan, D5) |
| 7 | Bisiesto / 53 sábados o domingos | La capacidad para el 6/6/6 se calcula sobre el calendario real del año, nunca a mano |
| 8 | `modulos_guardia` = 1 | Festivos alternos equipo/área (§3.4); 1 persona por pareja de sábado |
| 9 | Festivos repetidos o de años mezclados | `validar()` rechaza |
| 10 | Semana Santa por año | Derivar de Pascua (Butcher); nunca fijar 25–28/3 |
| 11 | Festivos cambian respecto a la plantilla | El generador pinta los que llegan y no hereda ninguno |

---

## 9. Pruebas

1. **Golden 2027** (§7): entrada equivalente → invariantes Rev. 2 + golden regenerado y
   congelado (`golden_2027_rev2.json`).
2. **Propiedades** (cualquier entrada): cobertura exacta de `modulos` celdas/día;
   **exactamente 6/6/6** (viernes/sábados/domingos) por enfermera de equipo — o rechazo
   por imposibilidad (R13); parejas sábado→jueves +5 de la misma enfermera **incluidos
   los sábados-festivo**; **descanso de 72 h** (sin guardias en −2/−1/+1…+4 de cada
   sábado propio); **horas ≤ objetivo siempre** (D10); sin consecutivos en equipo;
   mitades de festivos aproximadas; equidad de área; bolsa nunca rellena.
3. **Unitarios** de los casos límite §8 (año bisiesto, 53 sábados, m=1, festivo en
   sábado, festivo en jueves, plantilla > capacidad 6/6/6, objetivo < base 492 h,
   demanda > oferta, demanda < oferta).
4. **Validador interno**: cada generación debe pasar la emulación de contadores
   (port de `referencia/verificar_2027.py`) antes de devolver el libro.

---

## 10. Roadmap con criterios de aceptación

| Fase | Entregable | Hecho cuando… |
|---|---|---|
| **M1** | `logica/calendario.py` + `logica/cuotas.py` | Dado año + festivos: días categorizados, especiales por Pascua, horas/celda, **factibilidad 6/6/6 (R13)** y cuotas f/LMX correctas (test con 2027 y 2026) |
| **M2** | `logica/solver.py` | Port del algoritmo §5 con n, m∈{1,2}, cuotas fijas 6/6/6 + bloqueos 72 h; **golden 2027 regenerado bajo Rev. 2 y congelado** |
| **M3** | `logica/validar_resultado.py` | Emulación de contadores sobre el resultado; pasa en el golden |
| **M4** | `logica/generador.py` | Libro para cualquier año: maqueta, fórmulas dinámicas, festivos en morado (especiales oscuros), "Vacío" naranja, título, **hojas de detalle por enfermera** |
| **M5** | `logica/excel_logica.py` + campo `anio` en `config/parametros.py` | `validar()` + `procesar()` implementados con el contrato §11; el formulario genera y descarga el Excel; mensaje con horas sin cubrir y bolsa |
| **M6** | Extras | Precarga automática de festivos nacionales/autonómicos para el año `anio` (D2/D6), override manual de la bolsa con verificación de invariantes, vista previa web, históricos |

**Definición de "hecho" (app completa):** con cualquier entrada válida del formulario,
`procesar()` devuelve en < unos segundos un XLSX descargable que pasa todas las pruebas
de §9, más un mensaje con el informe de horas sin cubrir y bolsa. Sin tocar `app.py`.

---

## 11. Contrato a implementar (ya definido por el front — respetar firmas)

`logica/excel_logica.py`:

```python
@dataclass
class Resultado:
    ok: bool                  # True si el libro se generó (horas sin cubrir NO es error)
    mensaje: str              # informe: horas sin cubrir, bolsa, desvíos, avisos
    contenido: bytes | None   # XLSX resultante
    archivo: str | None       # nombre sugerido de descarga

def validar(parametros: dict) -> str | None:
    """None = OK; str = mensaje de error. Rechazar: festivos de años mezclados o fuera
    del año `anio` elegido (D13), fechas duplicadas, modulos_guardia fuera de {1,2},
    horas negativas, y plantilla incompatible con el 6/6/6
    (R13: 6×n_equipo > m×min(S,D,V,J) del año)."""

def procesar(parametros: dict) -> Resultado: ...
```

- Sin API HTTP: Streamlit llama a la lógica en el mismo proceso.
- Despliegue ya configurado: Apache con proxy WebSocket `/_stcore/stream` → :8501
  (`deploy/vane_apache_snippet.conf`).

---

## 12. Preguntas — todas cerradas

Respondidas por el usuario (D1–D13, incluidos los ajustes del cliente de la Rev. 2:
R13, R14, R17, R21 y R23, y el campo Año con inicial = año siguiente, D13). Decisiones
menores que la sesión ejecutora puede tomar sola: tono exacto de los morados (§6.3),
nombres de las hojas de detalle ("Detalle A"…), distribución exacta del texto del
mensaje, y momento de la precarga de festivos (M5 vs M6).
