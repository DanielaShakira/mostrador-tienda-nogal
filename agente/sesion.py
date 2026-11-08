"""Cliente autenticado del modelo y estado de la sesión de un cliente de la tienda."""
import os
from dataclasses import dataclass

from openai import OpenAI

# Alias del modelo en el intermediario. No depende del proveedor que haya detrás.
MODELO = "modelo-clase"


def crear_cliente_llm() -> OpenAI:
    """Cliente del SDK de OpenAI apuntando al intermediario de la clase.

    La credencial y la dirección se leen de los secretos de Codespaces, nunca del repositorio.
    """
    faltan = [v for v in ("LLM_API_KEY", "LLM_BASE_URL") if not os.environ.get(v)]
    if faltan:
        raise RuntimeError(f"Faltan los secretos {', '.join(faltan)}. Revisa la sección 2 de GUIA.md.")
    return OpenAI(api_key=os.environ["LLM_API_KEY"], base_url=os.environ["LLM_BASE_URL"])


@dataclass
class Sesion:
    """Estado de una conversación.

    cliente_id lo fija la interfaz (simula un cliente con sesión iniciada). Las herramientas
    lo leen de aquí; el modelo nunca lo recibe como argumento.
    Si necesitas recordar algo entre turnos, agrégalo como un campo nuevo.
    """
    cliente_id: str
    turnos: int = 0
    tokens_entrada: int = 0
    tokens_salida: int = 0
