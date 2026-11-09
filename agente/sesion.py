"""Cliente autenticado del modelo y estado de la sesión de un cliente de la tienda."""
import os
from dataclasses import dataclass
from typing import Literal, TypeAlias

from openai import OpenAI

# Alias del modelo en el intermediario. No depende del proveedor que haya detrás.
MODELO = "modelo-clase"


@dataclass(frozen=True)
class ReclamoPendiente:
    """Datos inmutables que esperan una selección real del cliente."""

    numero_pedido: str
    producto: str | None
    motivo: str
    turno_preparacion: int


@dataclass
class CasoSoporte:
    """Seguimiento verificable de un problema durante la sesión actual."""

    caso_id: str
    cliente_id: str
    numero_pedido: str | None
    relato_inicial: str
    intentos_fallidos: int = 0
    estado: Literal["activo", "resuelto", "escalado"] = "activo"
    escalamiento_id: str | None = None


@dataclass(frozen=True)
class ResultadoIntentoPendiente:
    """Solución preparada que espera el resultado real del cliente."""

    caso_id: str
    intento_id: str
    descripcion_solucion: str
    turno_preparacion: int


@dataclass(frozen=True)
class FinanzasPendientes:
    """Autorización exacta; nunca forma parte de los argumentos del LLM."""

    cliente_id: str
    accion: Literal["cancelar", "reembolsar"]
    numero_pedido: str
    monto: int
    motivo: str
    turno_preparacion: int
    codigo: str
    huella: str
    requiere_asesor: bool


OperacionPendiente: TypeAlias = ReclamoPendiente | ResultadoIntentoPendiente | FinanzasPendientes


def crear_cliente_llm() -> OpenAI:
    """Cliente del SDK de OpenAI apuntando al intermediario de la clase.

    La credencial y la dirección se leen de los secretos de Codespaces, nunca del repositorio.
    """
    faltan = [v for v in ("LLM_API_KEY", "LLM_BASE_URL") if not os.environ.get(v)]
    if faltan:
        raise RuntimeError(f"Faltan los secretos {', '.join(faltan)}. Revisa la sección 2 de GUIA.md.")
    return OpenAI(api_key=os.environ["LLM_API_KEY"], base_url=os.environ["LLM_BASE_URL"], timeout=60.0, max_retries=1)


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
    mensaje_actual: str | None = None
    relato_reclamo: tuple[str, str | None, str, int] | None = None
    caso_soporte: CasoSoporte | None = None
    operacion_pendiente: OperacionPendiente | None = None

    @property
    def reclamo_pendiente(self) -> ReclamoPendiente | None:
        """Vista compatible del reclamo dentro del único estado pendiente."""
        if isinstance(self.operacion_pendiente, ReclamoPendiente):
            return self.operacion_pendiente
        return None

    @reclamo_pendiente.setter
    def reclamo_pendiente(self, valor: ReclamoPendiente | None) -> None:
        if valor is None:
            if isinstance(self.operacion_pendiente, ReclamoPendiente):
                self.operacion_pendiente = None
            return
        self.operacion_pendiente = valor

    @property
    def resultado_intento_pendiente(self) -> ResultadoIntentoPendiente | None:
        """Vista del resultado de intento dentro del estado pendiente único."""
        if isinstance(self.operacion_pendiente, ResultadoIntentoPendiente):
            return self.operacion_pendiente
        return None
