# REGLAS DE NEGOCIO — Generador de calendarios de guardias

> Documento para el cliente. Cada regla tiene un código (**R1, R2, …**) para poder pedir
> cambios concretos: *"modifica la R7"*.
>
> **Rev. 2 — 10/11/2026:** R6, R13, R14, R17, R21 y R23 ajustadas tras reunión con el cliente.
> **Rev. 3:** R1 y R2 con mínimos (4 de equipo, 1 de área); R11 y R12 con los festivos especiales
> (Navidad y Semana Santa repartidos aparte).

---

## 1. Datos que se piden en el formulario

- **R1.** Nº de enfermeras de equipo (**mínimo 4**). Se les asignan letras: A, B, C, D…
- **R2.** Nº de enfermeras de área (**mínimo 1**). Se les asigna: R1, R2, R3…
- **R3.** Módulos de guardia: **1 o 2**. Es el número de personas de guardia el mismo día.
- **R4.** Horas objetivo por enfermera de equipo (**mínimo 1**).
- **R5.** Horas objetivo por enfermera de área (**mínimo 1**).
- **R6.** El formulario incluye el **año** del calendario (por defecto, **el siguiente al
  actual**). Los festivos nacionales y autonómicos de ese año se precargan
  automáticamente, y el usuario añade los **festivos locales**; el conjunto de ambos es
  el que usa la aplicación.

El calendario se genera para **cualquier año**.

---

## 2. Cuántas horas vale cada guardia

- **R7.** Día laborable de lunes a viernes (no festivo): **17 horas**.
- **R8.** Sábado (no festivo): **24 horas**.
- **R9.** Domingo: **24 horas**.
- **R10.** Festivo (cualquiera): **24 horas**, aunque caiga en sábado, domingo o laborable.
  **El festivo prevalece sobre el día de la semana.**

---

## 3. Festivos especiales

- **R11.** Son festivos especiales: **1 de enero**, **24, 25 y 31 de diciembre** y el
  **jueves y viernes santo** (Semana Santa). Las fechas cambian cada año y se calculan
  automáticamente. Sábado y domingo de Pascua **no** son especiales.
- **R12.** De cada festivo **no especial**, **la mitad de las guardias son para el equipo
  y la otra mitad para el área**. Si hay un solo módulo de guardia, los festivos se
  alternan entre equipo y área.
- **R12b.** Los festivos especiales se reparten **aparte** de los demás: **la mitad para el
  equipo y la mitad para el área**. Con un solo módulo, equipo y área se alternan por día,
  empezando por el equipo; los sábados y jueves de especial son siempre del equipo.
- **R12c.** Las enfermeras de equipo se dividen en dos grupos fijos: **Navidad** y **Semana
  Santa**. Un miembro del equipo hace **uno u otro** grupo, nunca ambos. Un miembro de área
  puede hacer **los dos**. El reparto entre grupos es **aleatorio**, mitad y mitad (con
  semilla fija por año, así el mismo formulario genera siempre el mismo calendario).

---

## 4. Reglas para el equipo (las letras)

- **R13.** Cada enfermera de equipo hace **exactamente 6 viernes, 6 sábados y 6 domingos**
  (número fijo, no depende del nº de enfermeras). Si con el nº de enfermeras del
  formulario no fuera posible (p. ej., plantillas muy grandes), la aplicación lo informa.
- **R14.** **Cada sábado de guardia lleva el jueves siguiente (+5 días) a la misma
  enfermera.** La necesidad real es que la enfermera descanse **72 horas alrededor de cada
  sábado**: no trabaja el **jueves y viernes anteriores**, ni del **domingo al miércoles
  posteriores** — por eso su siguiente guardia tras el sábado es el jueves. Esta es la
  norma que la aplicación aplica **siempre** (la variante de guardar el jueves *anterior*
  solo se usa a mano cuando hay puente).
- **R15.** Ninguna enfermera de equipo tiene **dos guardias seguidas** (días consecutivos).
- **R16.** El resto de días laborables (lunes, martes y miércoles) se reparte también
  equitativamente, hasta aproximarse a las horas objetivo.
- **R17.** Si las horas pedidas no se alcanzan **exactamente**, el reparto se queda **por
  debajo del objetivo, nunca por encima**, y el resultado informa del desvío
  (p. ej. 880 h frente a 884 pedidas).

---

## 5. Reglas para el personal de área

- **R18.** Las enfermeras de área cubren las guardias que el equipo no ocupa, y las horas
  se reparten de forma **equitativa** entre todas (mismo total aproximado para cada una).

---

## 6. Cuándo no se alcanzan las horas

- **R19.** Si se alcanza el objetivo de todas y **sobran** guardias por cubrir, esas celdas
  se marcan **"Vacío" con fondo naranja**: son una **bolsa de horas** para asignar
  manualmente. La aplicación no las rellena.
- **R20.** Si el año **no da para más** (se piden más horas de las que existen), se reparte
  lo máximo posible de forma equitativa y el resultado informa de las **horas sin cubrir**.

---

## 7. Casos particulares del calendario

- **R21.** Si un festivo cae en **sábado**, puntúa como festivo (24 h) y **cuenta como uno
  de los 6 sábados** de esa enfermera. Como todo sábado de guardia, **su jueves anterior
  queda de descanso** y **trabaja el jueves siguiente (+5 días)**, que lleva a la misma
  enfermera (misma regla de 72 h que la R14).
- **R22.** Si un festivo cae en **jueves** y ese jueves viene de una pareja de sábado, la
  pareja puntúa como festivo y a esa enfermera se le **compensa** con un jueves normal más,
  para no perder guardias respecto a sus compañeras.

---

## 8. Qué contiene el Excel generado

- **R23.** **Hoja principal**: calendario del año completo (12 meses), con las letras del
  equipo en su fila y el personal de área en la suya. Los festivos llevan **fondo morado**
  (los especiales —1/1, Semana Santa, 24, 25 y 31/12— en **morado más oscuro**), y las
  celdas de la bolsa de horas ponen **"Vacío" con fondo naranja** (el naranja queda
  reservado a la bolsa, para no confundirse con los festivos).
- **R24.** **Estadísticas mensuales** por enfermera (horas laborables / horas de fin de
  semana y festivos / total) y **resumen anual**: lunes a domingo, festivos, horas y número
  de guardias.
- **R25.** **Una hoja por enfermera**: su calendario del año resumido (solo con sus
  guardias) y el resumen de sus horas, festivos trabajados, etc.
- **R26.** Título del calendario con el número de profesionales y el año elegido.

---

*Para pedir un cambio, indique el código de la regla. Ejemplo: "la R17 quiero que avise
en rojo en lugar de informar del desvío".*

