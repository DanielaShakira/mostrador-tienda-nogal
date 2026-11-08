"""Cómo se declara una herramienta y cómo se ejecuta.

Una herramienta es una función con esta forma:

    class ArgsMiHerramienta(BaseModel):
        numero: str = Field(description="Qué es este dato, para que el modelo lo entienda")

    @herramienta
    def mi_herramienta(sesion: Sesion, args: ArgsMiHerramienta) -> dict:
        '''Descripción que lee el modelo para decidir cuándo usarla.'''
        ...
        return {"lo_que": "quieras devolver"}

- El nombre de la función es el nombre de la herramienta.
- El docstring es la descripción que ve el modelo.
- El modelo de Pydantic de `args` define el esquema de argumentos y los valida.
- `sesion` la pasa el ciclo. El modelo no la ve ni puede cambiarla.
- Para rechazar una acción, lanza ErrorDeHerramienta("motivo"). El modelo recibe
  {"error": "motivo"} como resultado y puede explicárselo al cliente.
"""
import inspect
import json
from typing import Callable

from pydantic import BaseModel, ValidationError

from agente.sesion import Sesion

# nombre -> (función, modelo de argumentos)
HERRAMIENTAS: dict[str, tuple[Callable, type[BaseModel]]] = {}


class ErrorDeHerramienta(Exception):
    """La herramienta no puede hacer lo que se le pidió. El mensaje se le devuelve al modelo."""


def herramienta(funcion: Callable) -> Callable:
    """Decorador que registra una función como herramienta disponible para el agente."""
    modelo_args = inspect.signature(funcion).parameters["args"].annotation
    HERRAMIENTAS[funcion.__name__] = (funcion, modelo_args)
    return funcion


def esquemas() -> list[dict]:
    """Lista de herramientas en el formato que espera la API de chat."""
    return [
        {
            "type": "function",
            "function": {
                "name": nombre,
                "description": inspect.getdoc(funcion),
                "parameters": modelo_args.model_json_schema(),
            },
        }
        for nombre, (funcion, modelo_args) in HERRAMIENTAS.items()
    ]


def ejecutar(nombre: str, argumentos_json: str, sesion: Sesion) -> dict:
    """Ejecuta una herramienta. Nunca lanza excepciones: los errores vuelven como resultado."""
    if nombre not in HERRAMIENTAS:
        return {"error": f"No existe la herramienta '{nombre}'."}
    funcion, modelo_args = HERRAMIENTAS[nombre]
    try:
        args = modelo_args.model_validate_json(argumentos_json or "{}")
    except ValidationError as e:
        return {"error": "Argumentos inválidos.", "detalle": json.loads(e.json(include_url=False))}
    try:
        return funcion(sesion, args)
    except ErrorDeHerramienta as e:
        return {"error": str(e)}
    except Exception as e:
        # Un fallo inesperado en tu código también se le informa al modelo, y queda en la traza.
        return {"error": "Falla interna de la herramienta.", "detalle": f"{type(e).__name__}: {e}"}
