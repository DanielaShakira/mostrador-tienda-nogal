"""Seguimiento verificable de intentos de resolución por caso."""

from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from agente.herramientas.escalamiento import (
    PLAZO_CONTACTO,
    escalar_por_tres_intentos,
    validar_cliente_y_pedido,
)
from agente.herramientas.registro import ErrorDeHerramienta, herramienta
from agente.sesion import CasoSoporte, ResultadoIntentoPendiente, Sesion


class ArgsPrepararIntentoResolucion(BaseModel):
    """Solución propuesta; identidad, caso y contador proceden de la sesión."""

    model_config = ConfigDict(extra="forbid", strict=True)

    solucion: str = Field(
        min_length=1,
        description="Acción concreta que el cliente debe probar para resolver el caso.",
    )
    numero_pedido: str | None = Field(
        default=None,
        description="Pedido propio relacionado con el caso, si corresponde.",
    )


def _nuevo_id(prefijo: str) -> str:
    return f"{prefijo}-{uuid4().hex}"


def _nuevo_caso(sesion: Sesion, numero_pedido: str | None) -> CasoSoporte:
    relato = (sesion.mensaje_actual or "").strip()
    if not relato:
        raise ErrorDeHerramienta(
            "No se puede iniciar un caso sin el relato del turno actual."
        )
    caso = CasoSoporte(
        caso_id=_nuevo_id("CASO"),
        cliente_id=sesion.cliente_id,
        numero_pedido=numero_pedido,
        relato_inicial=relato,
    )
    sesion.caso_soporte = caso
    return caso


def _caso_escalado(caso: CasoSoporte) -> dict:
    return {
        "intento_preparado": False,
        "caso_escalado": True,
        "escalamiento_id": caso.escalamiento_id,
        "plazo_contacto": PLAZO_CONTACTO,
        "mensaje": "El caso ya fue escalado y no se registrarán más intentos.",
    }


@herramienta
def preparar_intento_resolucion(
    sesion: Sesion,
    args: ArgsPrepararIntentoResolucion,
) -> dict:
    """Prepara una solución; solo el resultado posterior del cliente puede contar."""
    solucion = args.solucion.strip()
    if not solucion:
        raise ErrorDeHerramienta("La solución propuesta no puede estar vacía.")

    validar_cliente_y_pedido(sesion, args.numero_pedido)
    if sesion.operacion_pendiente is not None:
        raise ErrorDeHerramienta(
            "Hay una operación pendiente. Debe resolverse o descartarse antes."
        )

    caso = sesion.caso_soporte
    if caso is None or caso.estado == "resuelto":
        caso = _nuevo_caso(sesion, args.numero_pedido)
    elif caso.cliente_id != sesion.cliente_id:
        raise ErrorDeHerramienta("El caso activo no pertenece a esta sesión.")
    elif caso.estado == "escalado":
        return _caso_escalado(caso)
    elif caso.numero_pedido != args.numero_pedido:
        return {
            "intento_preparado": False,
            "requiere_nuevo_caso": True,
            "mensaje": (
                "El pedido no corresponde al caso activo. Si el cliente quiere "
                "abandonar ese seguimiento, pídele responder exactamente: nuevo caso."
            ),
        }

    pendiente = ResultadoIntentoPendiente(
        caso_id=caso.caso_id,
        intento_id=_nuevo_id("INTENTO"),
        descripcion_solucion=solucion,
        turno_preparacion=sesion.turnos,
    )
    sesion.operacion_pendiente = pendiente
    return {
        "intento_preparado": True,
        "requiere_resultado": True,
        "solucion": solucion,
        "intentos_fallidos": caso.intentos_fallidos,
        "mensaje": (
            "Explica la solución al cliente. Después de probarla debe responder "
            "en un turno nuevo exactamente 'resuelto', 'sigue sin resolver' o "
            "'cancelar seguimiento'. Todavía no se contabilizó ningún fallo."
        ),
    }


def _caso_del_pendiente(
    sesion: Sesion,
    pendiente: ResultadoIntentoPendiente,
) -> CasoSoporte:
    caso = sesion.caso_soporte
    if caso is None or caso.caso_id != pendiente.caso_id:
        raise ErrorDeHerramienta("El intento ya no corresponde al caso activo.")
    if caso.cliente_id != sesion.cliente_id:
        raise ErrorDeHerramienta("El caso activo no pertenece a esta sesión.")
    return caso


def procesar_resultado_intento(sesion: Sesion, mensaje: str) -> dict | None:
    """Procesa el resultado exacto de un intento desde un turno real del cliente."""
    pendiente = sesion.resultado_intento_pendiente
    if pendiente is None:
        return None

    respuesta = " ".join(mensaje.split()).casefold()
    if sesion.turnos <= pendiente.turno_preparacion:
        return {
            "resultado_procesado": False,
            "resultado_mismo_turno": True,
            "mensaje": "El resultado debe proceder de un turno posterior del cliente.",
        }

    if respuesta == "cancelar seguimiento":
        sesion.operacion_pendiente = None
        return {
            "resultado_procesado": False,
            "seguimiento_cancelado": True,
            "mensaje": "Se canceló el resultado pendiente sin contabilizar un fallo.",
        }

    if respuesta not in {"resuelto", "sigue sin resolver"}:
        sesion.operacion_pendiente = None
        return None

    # Consumir antes de mutar o escalar impide reutilizar la misma respuesta.
    sesion.operacion_pendiente = None
    try:
        caso = _caso_del_pendiente(sesion, pendiente)
        if respuesta == "resuelto":
            caso.estado = "resuelto"
            return {
                "resultado_procesado": True,
                "resuelto": True,
                "intentos_fallidos": caso.intentos_fallidos,
                "mensaje": "El caso se marcó como resuelto y no se escaló.",
            }

        if caso.estado == "escalado":
            return _caso_escalado(caso)
        caso.intentos_fallidos += 1
        if caso.intentos_fallidos < 3:
            return {
                "resultado_procesado": True,
                "resuelto": False,
                "intentos_fallidos": caso.intentos_fallidos,
                "mensaje": (
                    "El fallo fue confirmado por el cliente. El caso sigue activo "
                    "y todavía no cumple tres intentos fallidos."
                ),
            }

        escalamiento = escalar_por_tres_intentos(sesion)
        return {
            "resultado_procesado": True,
            "resuelto": False,
            "intentos_fallidos": caso.intentos_fallidos,
            **escalamiento,
            "mensaje": (
                f"El caso fue escalado con identificador "
                f"{escalamiento['escalamiento_id']}. Un asesor contactará al cliente "
                f"en un plazo {escalamiento['plazo_contacto']}."
            ),
        }
    except ErrorDeHerramienta as error:
        return {
            "resultado_procesado": False,
            "error": str(error),
            "mensaje": str(error),
        }
