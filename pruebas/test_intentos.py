"""Pruebas deterministas del seguimiento de intentos sin usar el LLM."""

import json
from uuid import UUID

import pytest

from agente import herramientas  # noqa: F401  (registra las herramientas)
from agente.herramientas.escalamiento import escalar_por_tres_intentos
from agente.herramientas.intentos import procesar_resultado_intento
from agente.herramientas.registro import ErrorDeHerramienta, HERRAMIENTAS, ejecutar
from agente.pendientes import procesar_operacion_pendiente
from agente.sesion import ResultadoIntentoPendiente, Sesion
from tienda import repositorio


def nueva_sesion(cliente_id: str = "C-01") -> Sesion:
    return Sesion(
        cliente_id=cliente_id,
        turnos=1,
        mensaje_actual="El pedido sigue presentando el mismo problema.",
    )


def preparar(
    sesion: Sesion,
    solucion: str = "Reinicia el dispositivo y vuelve a probarlo.",
    numero_pedido: str | None = "P-1002",
) -> dict:
    argumentos = {"solucion": solucion}
    if numero_pedido is not None:
        argumentos["numero_pedido"] = numero_pedido
    return ejecutar(
        "preparar_intento_resolucion",
        json.dumps(argumentos),
        sesion,
    )


def responder(sesion: Sesion, mensaje: str, avanzar_turno: bool = True):
    if avanzar_turno:
        sesion.turnos += 1
    sesion.mensaje_actual = mensaje
    return procesar_operacion_pendiente(sesion, mensaje)


def preparar_siguiente(sesion: Sesion, numero: int) -> dict:
    sesion.turnos += 1
    sesion.mensaje_actual = "Necesito otra alternativa para el mismo problema."
    return preparar(
        sesion,
        solucion=f"Prueba la alternativa concreta número {numero}.",
    )


def confirmar_fallos(sesion: Sesion, cantidad: int) -> list[dict]:
    resultados = []
    for numero in range(1, cantidad + 1):
        if numero == 1:
            preparado = preparar(sesion)
        else:
            preparado = preparar_siguiente(sesion, numero)
        assert preparado["intento_preparado"] is True
        resultados.append(responder(sesion, "sigue sin resolver"))
    return resultados


def contenido_datos() -> dict[str, bytes]:
    return {
        archivo.name: archivo.read_bytes()
        for archivo in sorted(repositorio.DATOS.glob("*"))
    }


def test_preparar_no_incrementa_ni_escribe():
    sesion = nueva_sesion()
    antes = contenido_datos()

    resultado = preparar(sesion)

    assert resultado["intento_preparado"] is True
    assert resultado["intentos_fallidos"] == 0
    assert sesion.caso_soporte.intentos_fallidos == 0
    assert sesion.resultado_intento_pendiente is not None
    assert contenido_datos() == antes


def test_solo_la_preparacion_es_herramienta_publica_del_llm():
    assert "preparar_intento_resolucion" in HERRAMIENTAS
    assert "escalar_por_tres_intentos" not in HERRAMIENTAS


def test_caso_e_intento_tienen_ids_unicos_generados_por_python():
    primera = nueva_sesion()
    segunda = nueva_sesion()

    preparar(primera)
    preparar(segunda)

    assert primera.caso_soporte.caso_id != segunda.caso_soporte.caso_id
    assert (
        primera.resultado_intento_pendiente.intento_id
        != segunda.resultado_intento_pendiente.intento_id
    )
    UUID(primera.caso_soporte.caso_id.removeprefix("CASO-"))
    UUID(primera.resultado_intento_pendiente.intento_id.removeprefix("INTENTO-"))


def test_primer_fallo_confirmado_incrementa_una_vez():
    sesion = nueva_sesion()
    preparar(sesion)

    resultado = responder(sesion, "sigue sin resolver")

    assert resultado["intentos_fallidos"] == 1
    assert sesion.caso_soporte.intentos_fallidos == 1
    assert sesion.operacion_pendiente is None
    assert repositorio.leer_escalamientos() == []


def test_segundo_fallo_confirmado_no_escala():
    sesion = nueva_sesion()

    resultados = confirmar_fallos(sesion, 2)

    assert [item["intentos_fallidos"] for item in resultados] == [1, 2]
    assert sesion.caso_soporte.estado == "activo"
    assert repositorio.leer_escalamientos() == []


def test_tercer_fallo_escala_automaticamente_una_vez():
    sesion = nueva_sesion()

    resultados = confirmar_fallos(sesion, 3)

    tercero = resultados[-1]
    assert tercero["intentos_fallidos"] == 3
    assert tercero["escalamiento_id"] == "E-001"
    assert tercero["plazo_contacto"] == "máximo un día hábil"
    assert sesion.caso_soporte.estado == "escalado"
    assert sesion.caso_soporte.escalamiento_id == "E-001"
    assert len(repositorio.leer_escalamientos()) == 1
    guardado = repositorio.leer_escalamientos()[0]
    assert guardado.motivo == "tres_intentos_sin_resolver"
    assert sesion.caso_soporte.caso_id in guardado.resumen


def test_intento_de_cuarto_fallo_reutiliza_el_escalamiento():
    sesion = nueva_sesion()
    confirmar_fallos(sesion, 3)
    caso = sesion.caso_soporte
    sesion.turnos += 1
    sesion.operacion_pendiente = ResultadoIntentoPendiente(
        caso_id=caso.caso_id,
        intento_id="INTENTO-cuarto-controlado",
        descripcion_solucion="Otra solución que no debe volver a contabilizarse.",
        turno_preparacion=sesion.turnos,
    )

    resultado = responder(sesion, "sigue sin resolver")

    assert resultado["caso_escalado"] is True
    assert resultado["escalamiento_id"] == "E-001"
    assert caso.intentos_fallidos == 3
    assert len(repositorio.leer_escalamientos()) == 1


def test_resultado_en_mismo_turno_se_rechaza_sin_consumir():
    sesion = nueva_sesion()
    preparar(sesion)

    resultado = responder(sesion, "sigue sin resolver", avanzar_turno=False)

    assert resultado["resultado_mismo_turno"] is True
    assert sesion.caso_soporte.intentos_fallidos == 0
    assert sesion.resultado_intento_pendiente is not None


def test_resultado_consumido_no_puede_reutilizarse():
    sesion = nueva_sesion()
    preparar(sesion)

    primero = responder(sesion, "sigue sin resolver")
    segundo = responder(sesion, "sigue sin resolver")

    assert primero["intentos_fallidos"] == 1
    assert segundo is None
    assert sesion.caso_soporte.intentos_fallidos == 1


def test_respuesta_invalida_no_incrementa_y_libera_el_mensaje():
    sesion = nueva_sesion()
    preparar(sesion)

    resultado = responder(sesion, "Todavía estoy revisando otra cosa.")

    assert resultado is None
    assert sesion.operacion_pendiente is None
    assert sesion.caso_soporte.intentos_fallidos == 0
    assert repositorio.leer_escalamientos() == []


def test_cancelar_seguimiento_no_incrementa():
    sesion = nueva_sesion()
    preparar(sesion)

    resultado = responder(sesion, "cancelar seguimiento")

    assert resultado["seguimiento_cancelado"] is True
    assert sesion.caso_soporte.intentos_fallidos == 0
    assert sesion.operacion_pendiente is None


def test_resuelto_cierra_el_caso_sin_escalar():
    sesion = nueva_sesion()
    preparar(sesion)

    resultado = responder(sesion, "resuelto")

    assert resultado["resuelto"] is True
    assert sesion.caso_soporte.estado == "resuelto"
    assert repositorio.leer_escalamientos() == []


def test_nuevo_caso_no_hereda_el_contador():
    sesion = nueva_sesion()
    confirmar_fallos(sesion, 1)
    anterior = sesion.caso_soporte.caso_id

    transicion = responder(sesion, "nuevo caso")
    assert transicion["nuevo_caso_autorizado"] is True
    sesion.turnos += 1
    sesion.mensaje_actual = "Ahora necesito ayuda con un problema distinto."
    preparar(sesion, numero_pedido="P-1016")

    assert sesion.caso_soporte.caso_id != anterior
    assert sesion.caso_soporte.numero_pedido == "P-1016"
    assert sesion.caso_soporte.intentos_fallidos == 0


def test_dos_problemas_del_mismo_pedido_se_separan_por_transicion_explicita():
    sesion = nueva_sesion()
    confirmar_fallos(sesion, 1)
    anterior = sesion.caso_soporte.caso_id

    responder(sesion, "nuevo caso")
    sesion.turnos += 1
    sesion.mensaje_actual = "P-1002 presenta ahora un problema independiente."
    preparar(sesion, numero_pedido="P-1002")

    assert sesion.caso_soporte.caso_id != anterior
    assert sesion.caso_soporte.intentos_fallidos == 0


def test_llm_no_puede_inyectar_identidad_contador_caso_ni_resultado():
    sesion = nueva_sesion()
    argumentos = {
        "solucion": "Prueba una acción concreta.",
        "numero_pedido": "P-1002",
        "cliente_id": "C-02",
        "caso_id": "CASO-inventado",
        "intentos_fallidos": 3,
        "resultado": "sigue sin resolver",
    }

    resultado = ejecutar(
        "preparar_intento_resolucion",
        json.dumps(argumentos),
        sesion,
    )

    assert resultado["error"] == "Argumentos inválidos."
    assert sesion.caso_soporte is None
    assert repositorio.leer_escalamientos() == []


def test_pedido_ajeno_e_inexistente_son_indistinguibles():
    ajeno = preparar(nueva_sesion(), numero_pedido="P-1004")
    inexistente = preparar(nueva_sesion(), numero_pedido="P-9999")

    assert ajeno == {"error": "Pedido no disponible para esta sesión."}
    assert inexistente == ajeno


def test_no_reemplaza_un_reclamo_pendiente():
    sesion = nueva_sesion()
    reclamo = ejecutar(
        "registrar_reclamo",
        json.dumps({"numero_pedido": "P-1002"}),
        sesion,
    )

    intento = preparar(sesion)

    assert reclamo["reclamo_preparado"] is True
    assert intento == {
        "error": "Hay una operación pendiente. Debe resolverse o descartarse antes."
    }
    assert sesion.reclamo_pendiente is not None
    assert sesion.resultado_intento_pendiente is None


def test_consulta_exitosa_no_incrementa_intentos():
    sesion = nueva_sesion()
    preparar(sesion)
    responder(sesion, "sigue sin resolver")

    resultado = ejecutar(
        "consultar_pedido",
        json.dumps({"numero_pedido": "P-1002"}),
        sesion,
    )

    assert resultado["numero"] == "P-1002"
    assert sesion.caso_soporte.intentos_fallidos == 1


def test_escalamiento_interno_rechaza_contador_inferior_a_tres():
    sesion = nueva_sesion()
    confirmar_fallos(sesion, 2)

    with pytest.raises(ErrorDeHerramienta, match="todavía no tiene tres"):
        escalar_por_tres_intentos(sesion)

    assert repositorio.leer_escalamientos() == []


def test_escalamiento_interno_repetido_no_duplica():
    sesion = nueva_sesion()
    confirmar_fallos(sesion, 3)

    repetido = escalar_por_tres_intentos(sesion)

    assert repetido == {
        "escalamiento_id": "E-001",
        "nuevo": False,
        "plazo_contacto": "máximo un día hábil",
    }
    assert len(repositorio.leer_escalamientos()) == 1


def test_perdida_de_sesion_no_fabrica_intentos_previos():
    anterior = nueva_sesion()
    confirmar_fallos(anterior, 2)
    nueva = Sesion(cliente_id="C-01")

    assert nueva.caso_soporte is None
    assert nueva.operacion_pendiente is None
    with pytest.raises(ErrorDeHerramienta, match="No existe un caso"):
        escalar_por_tres_intentos(nueva)


def test_rechazos_no_escriben_archivos():
    antes = contenido_datos()
    sesion = nueva_sesion()

    assert "error" in preparar(sesion, solucion="   ")
    assert "error" in preparar(nueva_sesion(), numero_pedido="P-1004")
    with pytest.raises(ErrorDeHerramienta):
        escalar_por_tres_intentos(nueva_sesion())

    assert contenido_datos() == antes
