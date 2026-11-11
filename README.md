# Calendarios

Formulario web (Streamlit) para capturar parámetros y modificar un Excel.

## Estructura

```
Calendarios/
├── app.py                     # Formulario (front)
├── config/
│   └── parametros.py          # Parámetros definidos DECLARATIVAMENTE (incluye campo «anio»)
├── logica/
│   ├── excel_logica.py        # Contrato: validar() + procesar() → Resultado
│   ├── calendario.py          # M1: días del año, categorías, horas, Pascua (Butcher)
│   ├── cuotas.py              # M1: cuotas fijas 6/6/6 (R13), f/LMX, mitades de festivos
│   ├── solver.py              # M2: parejas sáb→jue+5, descanso 72 h, bolsa
│   ├── validar_resultado.py   # M3: comprobación de reglas sobre la asignación
│   ├── generador.py           # M4: libro Excel (maqueta, fórmulas, colores, detalles)
│   ├── verificar_libro.py     # Emulación de las fórmulas del libro (§9.4)
│   └── festivos_precarga.py   # M6: precarga de festivos Estado/CL + 24·12 y 31·12
├── referencia/                # Scripts validados del modelo 2027 + golden congelado
├── tests/                     # Golden 2027, límites §8 y parámetros (unittest)
├── .streamlit/
│   └── config.toml            # Tema y colores
├── requirements.txt
└── README.md
```

## Puesta en marcha

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Pruebas

```bash
.venv/bin/python -m unittest discover -s tests
```


## División de trabajo

- **Sesión Front (esta)**: formulario, parámetros, UX. Los parámetros se
  definen en `config/parametros.py` (campos numéricos, fechas dinámicas y
  validaciones cruzadas); añadir uno nuevo no requiere tocar `app.py`.
- **Sesión de lógica**: implementar `validar()` y `procesar()` en
  `logica/excel_logica.py`, devolviendo un `Resultado`.

La sesión de lógica NO debe tocar `app.py`; solo el módulo de lógica.
