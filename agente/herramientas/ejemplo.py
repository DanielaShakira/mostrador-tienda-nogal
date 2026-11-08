"""Herramienta de ejemplo: muestra el patrón completo de una herramienta."""
from typing import Literal

from pydantic import BaseModel, Field

from agente.herramientas.registro import ErrorDeHerramienta, herramienta
from agente.sesion import Sesion
from tienda import repositorio


class ArgsConsultarPolitica(BaseModel):
    tema: Literal["reclamos", "cancelaciones", "reembolsos", "escalamiento"] = Field(
        description="Tema de la política que se quiere consultar."
    )


@herramienta
def consultar_politica(sesion: Sesion, args: ArgsConsultarPolitica) -> dict:
    """Devuelve el texto de la política de la tienda sobre un tema."""
    # Cada sección de politicas.md empieza con "## Título".
    for seccion in repositorio.leer_politicas().split("\n## ")[1:]:
        titulo, _, texto = seccion.partition("\n")
        if titulo.strip().lower() == args.tema:
            return {"tema": args.tema, "texto": texto.strip()}
    raise ErrorDeHerramienta(f"No encontré una sección '{args.tema}' en la política.")
