"""
Formulario de captura de parámetros (Streamlit).

Aplicación para generar calendarios de enfermeras. Este módulo SOLO
recoge parámetros del usuario y llama a la interfaz definida en
`logica/excel_logica.py`; la implementación de la lógica se hace en
otra sesión de trabajo.

Los parámetros se definen declarativamente en `config/parametros.py`:
añadir/quitar campos no requiere tocar este archivo.
"""

from datetime import date

import streamlit as st

from config.parametros import CAMPOS_NUMERICOS, CAMPO_FESTIVOS
from logica.excel_logica import procesar

hoy = date.today()

# ---------------------------------------------------------------------------
# Página y estilo
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Calendarios · Enfermería",
    page_icon="🗓️",
    layout="centered",
    initial_sidebar_state="collapsed",
)

CSS = """
<style>
    /* AppBar: tarjeta principal más estrecha y con aire */
    .block-container { max-width: 720px; padding-top: 1.2rem; padding-bottom: 4rem; }

    /* Cabecera tipo hero */
    .hero {
        background: linear-gradient(135deg, #00695C 0%, #00897B 55%, #26A69A 100%);
        color: #FFFFFF;
        border-radius: 18px;
        padding: 1.6rem 2rem;
        margin-bottom: 1.4rem;
        box-shadow: 0 10px 28px rgba(0, 105, 92, 0.28);
    }
    .hero h1 { margin: 0 0 .35rem 0; font-size: 1.65rem; font-weight: 700; letter-spacing: .2px; }
    .hero p  { margin: 0; opacity: .88; font-size: .95rem; }

    /* Tarjetas (containers con borde) */
    [data-testid="stVerticalBlockBorderWrapper"] {
        background: #FFFFFF;
        border: 1px solid #DCEAE7 !important;
        border-radius: 16px !important;
        box-shadow: 0 3px 14px rgba(23, 51, 47, 0.06);
        padding: 1.2rem 1.4rem;
    }

    /* Etiquetas de campo ligeramente más compactas */
    [data-testid="stWidgetLabel"] p { font-weight: 600; color: #17332F; }

    /* Botón principal */
    button[kind="primary"] {
        border-radius: 12px;
        font-weight: 600;
        padding: .55rem 1.4rem;
        box-shadow: 0 4px 14px rgba(0, 105, 92, 0.25);
    }

    /* Botones secundarios (añadir / eliminar festivo) */
    button[kind="secondary"] { border-radius: 10px; }

    /* Resumen inferior */
    .resumen {
        text-align: center;
        color: #4F6B66;
        font-size: .88rem;
        margin-top: .2rem;
    }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Cabecera
# ---------------------------------------------------------------------------

st.markdown(
    """
    <div class="hero">
        <h1>🗓️ Generador de calendarios</h1>
        <p>Planificación de cuadrantes para el personal de enfermería</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Parámetros numéricos (declarativos)
# ---------------------------------------------------------------------------

st.markdown("#### ⚙️ Parámetros de la plantilla")

parametros: dict = {}

for campo in CAMPOS_NUMERICOS:
    parametros[campo.clave] = st.number_input(
        label=campo.etiqueta,
        min_value=campo.minimo,
        max_value=campo.maximo,
        value=campo.inicial,
        step=1,
        help=f"{campo.ayuda} (rango: {campo.minimo}–{campo.maximo})",
        key=f"num__{campo.clave}",
    )

# ---------------------------------------------------------------------------
# Festivos locales (lista dinámica de fechas)
# ---------------------------------------------------------------------------

st.markdown(f"#### 🎉 {CAMPO_FESTIVOS.etiqueta}")

if "festivos" not in st.session_state:
    st.session_state.festivos = []

festivos: list[date] = st.session_state.festivos

# Filas de festivos: un selector de fecha + botón de eliminar por fila
indice_a_borrar: int | None = None
for i in range(len(festivos)):
    col_fecha, col_borrar = st.columns([0.88, 0.12], vertical_alignment="bottom")
    with col_fecha:
        festivos[i] = st.date_input(
            f"Festivo {i + 1}",
            value=festivos[i],
            key=f"festivo__{i}",
            label_visibility="collapsed",
        )
    with col_borrar:
        if st.button("✕", key=f"festivo__del__{i}", help="Eliminar festivo"):
            indice_a_borrar = i

if indice_a_borrar is not None:
    del festivos[indice_a_borrar]
    # Recrear las claves de los widgets para que no hereden estados viejos
    claves_festivos = [k for k in st.session_state if k.startswith("festivo__")]
    for clave in claves_festivos:
        del st.session_state[clave]
    st.rerun()

st.caption(CAMPO_FESTIVOS.ayuda)

if st.button("➕ Añadir festivo", use_container_width=True):
    festivos.append(date(hoy.year, 1, 1))
    st.rerun()

# ---------------------------------------------------------------------------
# Envío
# ---------------------------------------------------------------------------

st.markdown("")

if st.button(
    "🗓️ Generar calendario",
    type="primary",
    use_container_width=True,
):
    parametros[CAMPO_FESTIVOS.clave] = [d.isoformat() for d in festivos]

    with st.spinner("Procesando..."):
        resultado = procesar(parametros)

    if resultado.ok:
        st.success(resultado.mensaje)
        if resultado.archivo:
            st.download_button(
                "⬇️ Descargar Excel generado",
                data=resultado.contenido,
                file_name=resultado.archivo,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
    else:
        st.error(resultado.mensaje)

total = parametros["enfermeras"]
de_area = parametros["enfermeras_area"]
modulos = parametros["modulos_guardia"]
horas_equipo = parametros["horas_equipo"]
horas_area = parametros["horas_area"]
st.markdown(
    f"""
    <p class="resumen">
        {total} enfermeras · {de_area} de área · {modulos} módulos de guardia ·
        {len(festivos)} festivos · {horas_equipo} h equipo / {horas_area} h área
    </p>
    """,
    unsafe_allow_html=True,
)
