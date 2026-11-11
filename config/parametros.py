"""
Definición declarativa de los parámetros del formulario.

Añadir un parámetro nuevo = añadir una línea a CAMPOS_NUMERICOS (o una
definición de campo nuevo). app.py no necesita cambios.
"""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class CampoNumero:
    """Parámetro numérico del formulario."""

    clave: str
    """Clave con la que viaja en el dict `parametros`."""

    etiqueta: str
    """Texto visible para el usuario."""

    ayuda: str = ""
    """Descripción mostrada debajo del campo."""

    minimo: int = 0
    maximo: int = 999
    inicial: int = 1


@dataclass(frozen=True)
class CampoFechas:
    """Parámetro compuesto: lista dinámica de fechas."""

    clave: str
    """Clave con la que viaja en el dict `parametros`."""

    etiqueta: str
    """Texto visible para el usuario."""

    ayuda: str = ""
    """Descripción mostrada debajo de la lista."""


CAMPOS_NUMERICOS: list[CampoNumero] = [
    CampoNumero(
        clave="anio",
        etiqueta="Año",
        ayuda="Año del calendario (los festivos deben ser de ese año).",
        minimo=2020,
        maximo=2100,
        inicial=date.today().year + 1,
    ),
    CampoNumero(
        clave="enfermeras",
        etiqueta="Enfermeras",
        ayuda="Total de enfermeras de la plantilla.",
        minimo=4,
        maximo=999,
        inicial=10,
    ),
    CampoNumero(
        clave="enfermeras_area",
        etiqueta="Enfermeras de área",
        ayuda="Enfermeras asignadas a un área concreta.",
        minimo=1,
        maximo=999,
        inicial=2,
    ),
    CampoNumero(
        clave="modulos_guardia",
        etiqueta="Módulos de guardia",
        ayuda="Número de módulos de guardia a cubrir (1 o 2).",
        minimo=1,
        maximo=2,
        inicial=1,
    ),
    CampoNumero(
        clave="horas_equipo",
        etiqueta="Horas objetivo Equipo",
        ayuda="Horas objetivo para el equipo.",
        minimo=1,
        maximo=2500,
        inicial=880,
    ),
    CampoNumero(
        clave="horas_area",
        etiqueta="Horas objetivo Área",
        ayuda="Horas objetivo para el área.",
        minimo=1,
        maximo=2500,
        inicial=1460,
    ),
]

CAMPO_FESTIVOS = CampoFechas(
    clave="festivos",
    etiqueta="Festivos locales",
    ayuda="Se añaden uno a uno con el botón «Añadir festivo».",
)


VALIDACIONES = []  # De momento no hay validaciones desde el front: las hará el back.
