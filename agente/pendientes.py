"""Enrutador único de operaciones que esperan una respuesta del cliente."""

from agente.herramientas.intentos import procesar_resultado_intento
from agente.herramientas.reclamos import procesar_seleccion_reclamo
from agente.sesion import ReclamoPendiente, ResultadoIntentoPendiente, FinanzasPendientes, Sesion
from agente.herramientas.finanzas import procesar_confirmacion_financiera
from tienda import repositorio


def procesar_operacion_pendiente(sesion: Sesion, mensaje: str) -> dict | None:
    """Da cada respuesta al protocolo activo y libera solicitudes sustantivas."""
    pendiente = sesion.operacion_pendiente
    if isinstance(pendiente, FinanzasPendientes):
        return procesar_confirmacion_financiera(sesion, mensaje)
    if isinstance(pendiente, ReclamoPendiente):
        with repositorio.transaccion():
            resultado = procesar_seleccion_reclamo(sesion, mensaje)
    elif isinstance(pendiente, ResultadoIntentoPendiente):
        with repositorio.transaccion():
            resultado = procesar_resultado_intento(sesion, mensaje)
    else:
        resultado = None

    if resultado is not None:
        return resultado

    # Transición explícita: el LLM puede pedirla, pero solo el texto real del
    # cliente abandona el caso y su contador.
    comando = " ".join(mensaje.split()).casefold()
    if comando == "nuevo caso" and sesion.caso_soporte is not None:
        sesion.operacion_pendiente = None
        sesion.caso_soporte = None
        return {
            "nuevo_caso_autorizado": True,
            "mensaje": (
                "Se cerró el seguimiento anterior. Describe el nuevo problema "
                "para iniciar un caso independiente."
            ),
        }
    return None
