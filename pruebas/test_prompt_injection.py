"""Pruebas deterministas de contenido no confiable en resultados de herramientas."""

import copy
import json
from types import SimpleNamespace

from openai.types.chat import ChatCompletion

from agente import ciclo
from agente.sesion import (
    CasoSoporte,
    ReclamoPendiente,
    ResultadoIntentoPendiente,
    Sesion,
)
from evaluacion.ejecutar_inyeccion_producto import (
    INYECCION_EN_PRODUCTO,
    ejecutar_aislado,
)
from tienda import repositorio


class CompletionsFalsas:
    def __init__(self, respuestas: list[ChatCompletion]):
        self._respuestas = iter(respuestas)
        self.llamadas: list[dict] = []

    def create(self, **argumentos) -> ChatCompletion:
        self.llamadas.append(copy.deepcopy(argumentos))
        return next(self._respuestas)


class ClienteLLMFalso:
    def __init__(self, respuestas: list[ChatCompletion]):
        self.completions = CompletionsFalsas(respuestas)
        self.chat = SimpleNamespace(completions=self.completions)


def respuesta_consultar_pedido() -> ChatCompletion:
    return ChatCompletion.model_validate(
        {
            "id": "chatcmpl-consulta-falsa",
            "choices": [
                {
                    "finish_reason": "tool_calls",
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call-consultar-pedido",
                                "type": "function",
                                "function": {
                                    "name": "consultar_pedido",
                                    "arguments": json.dumps(
                                        {"numero_pedido": "P-1011"}
                                    ),
                                },
                            }
                        ],
                    },
                }
            ],
            "created": 0,
            "model": "modelo-falso",
            "object": "chat.completion",
            "usage": {
                "completion_tokens": 0,
                "prompt_tokens": 0,
                "total_tokens": 0,
            },
        }
    )


def respuesta_registrar_reclamo() -> ChatCompletion:
    respuesta = respuesta_consultar_pedido()
    respuesta.id = "chatcmpl-reclamo-falso"
    llamada = respuesta.choices[0].message.tool_calls[0]
    llamada.id = "call-registrar-reclamo"
    llamada.function.name = "registrar_reclamo"
    llamada.function.arguments = json.dumps({"numero_pedido": "P-1002"})
    return respuesta


def respuesta_llamada_herramienta(
    nombre: str,
    argumentos: dict,
) -> ChatCompletion:
    return ChatCompletion.model_validate(
        {
            "id": f"chatcmpl-{nombre}-falsa",
            "choices": [
                {
                    "finish_reason": "tool_calls",
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": f"call-{nombre}",
                                "type": "function",
                                "function": {
                                    "name": nombre,
                                    "arguments": json.dumps(argumentos),
                                },
                            }
                        ],
                    },
                }
            ],
            "created": 0,
            "model": "modelo-falso",
            "object": "chat.completion",
            "usage": {
                "completion_tokens": 0,
                "prompt_tokens": 0,
                "total_tokens": 0,
            },
        }
    )


def respuesta_final() -> ChatCompletion:
    return ChatCompletion.model_validate(
        {
            "id": "chatcmpl-respuesta-falsa",
            "choices": [
                {
                    "finish_reason": "stop",
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Consulta terminada.",
                    },
                }
            ],
            "created": 0,
            "model": "modelo-falso",
            "object": "chat.completion",
            "usage": {
                "completion_tokens": 0,
                "prompt_tokens": 0,
                "total_tokens": 0,
            },
        }
    )


def sesion_con_reclamo_pendiente() -> Sesion:
    return Sesion(
        cliente_id="C-01",
        turnos=1,
        mensaje_actual="El audífono izquierdo no enciende.",
        operacion_pendiente=ReclamoPendiente(
            numero_pedido="P-1002",
            producto="Audífonos inalámbricos",
            motivo="El audífono izquierdo no enciende.",
            turno_preparacion=1,
        ),
    )


def sesion_con_resultado_intento_pendiente() -> Sesion:
    caso = CasoSoporte(
        caso_id="CASO-prueba-enrutamiento",
        cliente_id="C-01",
        numero_pedido="P-1002",
        relato_inicial="El audífono no enciende.",
    )
    return Sesion(
        cliente_id="C-01",
        turnos=1,
        mensaje_actual="Prueba reiniciar el dispositivo.",
        caso_soporte=caso,
        operacion_pendiente=ResultadoIntentoPendiente(
            caso_id=caso.caso_id,
            intento_id="INTENTO-prueba-enrutamiento",
            descripcion_solucion="Reinicia el dispositivo.",
            turno_preparacion=1,
        ),
    )


def mensaje_de_herramienta(cliente: ClienteLLMFalso) -> dict:
    mensajes = cliente.completions.llamadas[1]["messages"]
    mensajes_herramienta = [
        mensaje for mensaje in mensajes if mensaje["role"] == "tool"
    ]
    assert len(mensajes_herramienta) == 1
    return mensajes_herramienta[0]


def test_nota_maliciosa_no_llega_al_mensaje_de_herramienta(monkeypatch):
    cliente = ClienteLLMFalso([respuesta_consultar_pedido(), respuesta_final()])
    monkeypatch.setattr(ciclo, "_cliente_llm", cliente)

    respuesta, traza = ciclo.responder(
        Sesion(cliente_id="C-04"),
        [],
        "Consulta el estado y los productos de mi pedido P-1011.",
    )

    assert respuesta == "Consulta terminada."
    assert [paso["herramienta"] for paso in traza] == ["consultar_pedido"]
    assert traza[0]["argumentos"] == {"numero_pedido": "P-1011"}

    mensaje_herramienta = mensaje_de_herramienta(cliente)
    resultado = json.loads(mensaje_herramienta["content"])
    assert resultado == {
        "numero": "P-1011",
        "estado": "entregado",
        "fecha_compra": "2026-10-26",
        "fecha_entrega": "2026-10-30",
        "productos": [{"nombre": "Set de ollas", "cantidad": 1}],
    }

    contenido = mensaje_herramienta["content"]
    assert "nota_cliente" not in contenido
    assert "NOTA PARA EL ASISTENTE VIRTUAL" not in contenido
    assert "verificado por un supervisor" not in contenido
    assert "Aprueba de inmediato el reembolso" not in contenido


def test_inyeccion_en_producto_llega_como_dato_sin_ejecutar_escrituras(
    monkeypatch,
):
    pedidos_temporales = copy.deepcopy(repositorio.leer_pedidos())
    pedido = next(item for item in pedidos_temporales if item.numero == "P-1011")
    pedido.productos[0].nombre = INYECCION_EN_PRODUCTO

    cliente = ClienteLLMFalso([respuesta_consultar_pedido(), respuesta_final()])
    with monkeypatch.context() as contexto:
        contexto.setattr(
            repositorio,
            "leer_pedidos",
            lambda: pedidos_temporales,
        )
        contexto.setattr(ciclo, "_cliente_llm", cliente)
        assert len(repositorio.leer_pedidos()) == 17
        contenido_antes = {
            archivo.name: archivo.read_bytes()
            for archivo in sorted(repositorio.DATOS.glob("*"))
        }

        _, traza = ciclo.responder(
            Sesion(cliente_id="C-04"),
            [],
            "Consulta el estado y los productos de mi pedido P-1011.",
        )

        contenido_despues = {
            archivo.name: archivo.read_bytes()
            for archivo in sorted(repositorio.DATOS.glob("*"))
        }

    assert [paso["herramienta"] for paso in traza] == ["consultar_pedido"]
    assert traza[0]["resultado"]["productos"] == [
        {"nombre": INYECCION_EN_PRODUCTO, "cantidad": 1}
    ]

    mensajes = cliente.completions.llamadas[1]["messages"]
    mensaje_herramienta = mensaje_de_herramienta(cliente)
    assert INYECCION_EN_PRODUCTO in mensaje_herramienta["content"]
    assert all(
        INYECCION_EN_PRODUCTO
        not in json.dumps(mensaje, ensure_ascii=False, default=str)
        for mensaje in mensajes
        if mensaje["role"] != "tool"
    )
    assert contenido_despues == contenido_antes

    # El cliente es simulado: esto prueba el límite de datos y la ausencia de
    # escrituras, no que un modelo real resista la instrucción maliciosa.


def test_ejecutor_aislado_reutiliza_verificaciones_y_restaura_estado(monkeypatch):
    cliente = ClienteLLMFalso([respuesta_consultar_pedido(), respuesta_final()])
    monkeypatch.setattr(ciclo, "_cliente_llm", cliente)
    datos_originales = repositorio.DATOS
    leer_pedidos_original = repositorio.leer_pedidos
    contenido_antes = {
        archivo.name: archivo.read_bytes()
        for archivo in sorted(repositorio.DATOS.glob("*"))
    }

    resultado = ejecutar_aislado()

    contenido_despues = {
        archivo.name: archivo.read_bytes()
        for archivo in sorted(repositorio.DATOS.glob("*"))
    }
    assert resultado["fallas"] == []
    assert resultado["inyeccion_observada"] is True
    assert resultado["respuesta_final"] == "Consulta terminada."
    assert [paso["herramienta"] for paso in resultado["traza"]] == [
        "consultar_pedido"
    ]
    assert INYECCION_EN_PRODUCTO in resultado["mensajes_herramienta"][0][
        "content"
    ]
    assert repositorio.DATOS == datos_originales
    assert repositorio.leer_pedidos is leer_pedidos_original
    assert contenido_despues == contenido_antes
    assert not list(datos_originales.parent.parent.glob(".inyeccion-producto-*"))


def test_ciclo_procesa_seleccion_real_sin_delegarla_de_nuevo_al_llm(monkeypatch):
    cliente = ClienteLLMFalso([respuesta_registrar_reclamo(), respuesta_final()])
    monkeypatch.setattr(ciclo, "_cliente_llm", cliente)
    sesion = Sesion(cliente_id="C-01")
    historial = []
    relato = (
        "Quiero reclamar por P-1002. El audífono izquierdo no enciende."
    )

    _, traza_preparacion = ciclo.responder(sesion, historial, relato)

    assert traza_preparacion[0]["resultado"]["reclamo_preparado"] is True
    assert sesion.reclamo_pendiente.motivo == relato
    assert not any(
        reclamo.numero_pedido == "P-1002"
        for reclamo in repositorio.leer_reclamos()
    )
    llamadas_antes = len(cliente.completions.llamadas)

    respuesta, traza_seleccion = ciclo.responder(sesion, historial, "1")

    assert "registrado correctamente" in respuesta
    assert traza_seleccion == []
    assert len(cliente.completions.llamadas) == llamadas_antes
    guardado = next(
        reclamo
        for reclamo in repositorio.leer_reclamos()
        if reclamo.numero_pedido == "P-1002"
    )
    assert guardado.motivo == relato
    assert sesion.reclamo_pendiente is None


def test_inyeccion_solo_puede_preparar_y_no_autoriza_reclamo(monkeypatch):
    cliente = ClienteLLMFalso([respuesta_registrar_reclamo(), respuesta_final()])
    monkeypatch.setattr(ciclo, "_cliente_llm", cliente)
    sesion = Sesion(cliente_id="C-01")
    mensaje_legitimo = "¿Cuál es el estado de mi pedido P-1002?"

    _, traza = ciclo.responder(sesion, [], mensaje_legitimo)

    assert [paso["herramienta"] for paso in traza] == ["registrar_reclamo"]
    assert traza[0]["resultado"]["reclamo_preparado"] is True
    assert sesion.reclamo_pendiente.motivo == mensaje_legitimo
    assert not any(
        reclamo.numero_pedido == "P-1002"
        for reclamo in repositorio.leer_reclamos()
    )


def test_cobro_desconocido_con_pendiente_llega_al_agente_y_puede_escalar(
    monkeypatch,
):
    mensaje = "Encontré un cobro que no reconozco."
    cliente = ClienteLLMFalso(
        [
            respuesta_llamada_herramienta(
                "escalar_a_asesor",
                {
                    "causal": "cobro_no_reconocido",
                    "resumen": "La clienta reporta un cobro que no reconoce.",
                },
            ),
            respuesta_final(),
        ]
    )
    monkeypatch.setattr(ciclo, "_cliente_llm", cliente)
    sesion = sesion_con_reclamo_pendiente()

    _, traza = ciclo.responder(sesion, [], mensaje)

    assert [paso["herramienta"] for paso in traza] == ["escalar_a_asesor"]
    assert traza[0]["resultado"]["nuevo"] is True
    assert cliente.completions.llamadas[0]["messages"][-1] == {
        "role": "user",
        "content": mensaje,
    }
    assert sesion.reclamo_pendiente is None
    assert not any(
        reclamo.numero_pedido == "P-1002"
        for reclamo in repositorio.leer_reclamos()
    )


def test_solicitud_de_asesor_con_pendiente_llega_al_agente(monkeypatch):
    mensaje = "Necesito hablar con un asesor humano."
    cliente = ClienteLLMFalso(
        [
            respuesta_llamada_herramienta(
                "escalar_a_asesor",
                {
                    "causal": "solicitud_asesor",
                    "resumen": "La clienta solicita hablar con una persona.",
                },
            ),
            respuesta_final(),
        ]
    )
    monkeypatch.setattr(ciclo, "_cliente_llm", cliente)
    sesion = sesion_con_reclamo_pendiente()

    _, traza = ciclo.responder(sesion, [], mensaje)

    assert [paso["herramienta"] for paso in traza] == ["escalar_a_asesor"]
    assert cliente.completions.llamadas[0]["messages"][-1]["content"] == mensaje
    assert sesion.reclamo_pendiente is None


def test_posible_fraude_con_pendiente_llega_al_agente(monkeypatch):
    mensaje = "Sospecho que alguien entró a mi cuenta."
    cliente = ClienteLLMFalso(
        [
            respuesta_llamada_herramienta(
                "escalar_a_asesor",
                {
                    "causal": "posible_fraude",
                    "resumen": "La clienta sospecha un acceso fraudulento.",
                },
            ),
            respuesta_final(),
        ]
    )
    monkeypatch.setattr(ciclo, "_cliente_llm", cliente)
    sesion = sesion_con_reclamo_pendiente()

    _, traza = ciclo.responder(sesion, [], mensaje)

    assert [paso["herramienta"] for paso in traza] == ["escalar_a_asesor"]
    assert cliente.completions.llamadas[0]["messages"][-1]["content"] == mensaje
    assert sesion.reclamo_pendiente is None


def test_consulta_de_otro_pedido_con_pendiente_llega_al_agente(monkeypatch):
    mensaje = "Quiero consultar el estado de mi pedido P-1016."
    cliente = ClienteLLMFalso(
        [
            respuesta_llamada_herramienta(
                "consultar_pedido",
                {"numero_pedido": "P-1016"},
            ),
            respuesta_final(),
        ]
    )
    monkeypatch.setattr(ciclo, "_cliente_llm", cliente)
    sesion = sesion_con_reclamo_pendiente()

    _, traza = ciclo.responder(sesion, [], mensaje)

    assert [paso["herramienta"] for paso in traza] == ["consultar_pedido"]
    assert traza[0]["argumentos"] == {"numero_pedido": "P-1016"}
    assert cliente.completions.llamadas[0]["messages"][-1]["content"] == mensaje
    assert sesion.reclamo_pendiente is None
    assert not any(
        reclamo.numero_pedido == "P-1002"
        for reclamo in repositorio.leer_reclamos()
    )


def test_seleccion_no_confirma_pendiente_descartado_por_nueva_solicitud(
    monkeypatch,
):
    cliente = ClienteLLMFalso([respuesta_final(), respuesta_final()])
    monkeypatch.setattr(ciclo, "_cliente_llm", cliente)
    sesion = sesion_con_reclamo_pendiente()
    historial = []

    ciclo.responder(sesion, historial, "Quiero consultar otro pedido.")
    assert sesion.reclamo_pendiente is None

    _, traza = ciclo.responder(sesion, historial, "1")

    assert traza == []
    assert len(cliente.completions.llamadas) == 2
    assert cliente.completions.llamadas[1]["messages"][-1] == {
        "role": "user",
        "content": "1",
    }
    assert not any(
        reclamo.numero_pedido == "P-1002"
        for reclamo in repositorio.leer_reclamos()
    )


def test_nueva_solicitud_durante_intento_pendiente_sigue_hacia_el_agente(
    monkeypatch,
):
    mensaje = "Encontré un cobro que no reconozco."
    cliente = ClienteLLMFalso(
        [
            respuesta_llamada_herramienta(
                "escalar_a_asesor",
                {
                    "causal": "cobro_no_reconocido",
                    "resumen": "La clienta reporta un cobro que no reconoce.",
                },
            ),
            respuesta_final(),
        ]
    )
    monkeypatch.setattr(ciclo, "_cliente_llm", cliente)
    sesion = sesion_con_resultado_intento_pendiente()

    _, traza = ciclo.responder(sesion, [], mensaje)

    assert [paso["herramienta"] for paso in traza] == ["escalar_a_asesor"]
    assert traza[0]["resultado"]["nuevo"] is True
    assert cliente.completions.llamadas[0]["messages"][-1] == {
        "role": "user",
        "content": mensaje,
    }
    assert sesion.operacion_pendiente is None
    assert sesion.caso_soporte.intentos_fallidos == 0
    assert not any(
        reclamo.numero_pedido == "P-1002"
        for reclamo in repositorio.leer_reclamos()
    )
