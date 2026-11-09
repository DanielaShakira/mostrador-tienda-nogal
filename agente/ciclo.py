"""Ciclo de herramientas: el corazón del agente.

1. Se envían al modelo las instrucciones, la conversación y la lista de herramientas.
2. Si el modelo pide herramientas, se ejecutan y sus resultados se agregan a la conversación.
3. Se repite hasta que el modelo responda con texto, o hasta MAX_ITERACIONES.
"""
import json
import re
from pathlib import Path

from agente import herramientas  # noqa: F401  (registra las herramientas)
from agente.herramientas.registro import ejecutar, esquemas
from agente.pendientes import procesar_operacion_pendiente
from agente.herramientas.reclamos import capturar_motivo
from agente.sesion import FinanzasPendientes
from agente.sesion import MODELO, Sesion, crear_cliente_llm

MAX_ITERACIONES = 8
INSTRUCCIONES = Path(__file__).parent / "instrucciones.md"

_cliente_llm = None


def _instrucciones() -> str:
    # Se lee en cada turno para que tus cambios apliquen sin reiniciar. Los comentarios <!-- --> se quitan.
    return re.sub(r"<!--.*?-->", "", INSTRUCCIONES.read_text(encoding="utf-8"), flags=re.S).strip()


def _como_json(texto: str):
    # El modelo a veces genera JSON inválido; en ese caso se guarda el texto tal cual.
    try:
        return json.loads(texto or "{}")
    except ValueError:
        return texto


def herramienta_prioritaria(mensaje: str) -> str | None:
    """Enruta solicitudes directas reales; NO autoriza escrituras ni confirma.

    Solo patrones conservadores de primera persona al inicio. Preguntas,
    negaciones, citas y datos devueltos por herramientas no activan esta ruta.
    """
    texto = " ".join(mensaje.split()).casefold()
    inicio = r"^(?:hola[,!. ]+)?"
    if re.search(inicio + r"(?:necesito|quiero|deseo|solicito)\s+(?:hablar|comunicarme|contactar)\s+con\s+(?:un[ao]?\s+)?(?:persona|asesor(?:a)?|humano|agente humano)\b", texto):
        return "escalar_a_asesor"
    if not re.search(r"\bp-\d+\b", texto) or "otro cliente" in texto:
        return None
    if re.search(inicio + r"(?:quiero|deseo|solicito)\s+cancelar\b", texto):
        return "cancelar_pedido"
    if re.search(inicio + r"(?:solicito|quiero|deseo|pido)\s+(?:un\s+)?reembolso\b", texto) and re.search(r"\bde\s+\$?\s*[\d.,]+\s*(?:pesos|cop)\b", texto):
        return "solicitar_reembolso"
    return None


def responder(sesion: Sesion, historial: list[dict], mensaje: str) -> tuple[str, list[dict]]:
    """Procesa un mensaje del cliente. Modifica `historial` y devuelve (respuesta, traza).

    La traza es la lista de herramientas ejecutadas en este turno, con sus argumentos y resultados.
    """
    global _cliente_llm
    sesion.turnos += 1
    sesion.mensaje_actual = mensaje
    capturar_motivo(sesion, mensaje)
    historial.append({"role": "user", "content": mensaje})
    traza = []

    era_financiera = isinstance(sesion.operacion_pendiente, FinanzasPendientes)
    resultado_pendiente = procesar_operacion_pendiente(sesion, mensaje)
    if resultado_pendiente is not None:
        respuesta_pendiente = resultado_pendiente["mensaje"]
        historial.append({"role": "assistant", "content": respuesta_pendiente})
        if era_financiera:
            traza.append({"herramienta": "confirmacion_financiera", "argumentos": {"mensaje_cliente": mensaje}, "resultado": resultado_pendiente})
        return respuesta_pendiente, traza

    _cliente_llm = _cliente_llm or crear_cliente_llm()

    prioritaria = herramienta_prioritaria(mensaje)
    for iteracion in range(MAX_ITERACIONES):
        instrucciones = _instrucciones()
        sistema = [{"role": "system", "content": instrucciones}] if instrucciones else []
        respuesta = _cliente_llm.chat.completions.create(
            model=MODELO,
            messages=sistema + historial,
            tools=esquemas() or None,
            **({"tool_choice": {"type": "function", "function": {"name": prioritaria}}}
               if iteracion == 0 and prioritaria else {}),
        )
        sesion.tokens_entrada += respuesta.usage.prompt_tokens
        sesion.tokens_salida += respuesta.usage.completion_tokens

        mensaje_modelo = respuesta.choices[0].message
        historial.append(mensaje_modelo.model_dump(exclude_none=True))
        if not mensaje_modelo.tool_calls:
            return mensaje_modelo.content or "", traza

        for llamada in mensaje_modelo.tool_calls:
            resultado = ejecutar(llamada.function.name, llamada.function.arguments, sesion)
            traza.append({
                "herramienta": llamada.function.name,
                "argumentos": _como_json(llamada.function.arguments),
                "resultado": resultado,
            })
            historial.append({
                "role": "tool",
                "tool_call_id": llamada.id,
                "content": json.dumps(resultado, ensure_ascii=False, default=str),
            })

        if isinstance(sesion.operacion_pendiente, FinanzasPendientes):
            from agente.herramientas.finanzas import _respuesta_preparada
            texto = _respuesta_preparada(sesion.operacion_pendiente)["mensaje"]
            historial.append({"role": "assistant", "content": texto})
            return texto, traza

    return "Lo siento, no pude completar tu solicitud. Intenta de nuevo con otras palabras.", traza
