"""Pruebas deterministas del escalamiento humano, sin llamar al modelo."""

import json

import pytest

from agente import herramientas  # noqa: F401  (registra las herramientas)
from agente.herramientas.escalamiento import (
    escalar_reembolso_superior_al_tope,
)
from agente.herramientas.registro import ErrorDeHerramienta, HERRAMIENTAS, ejecutar
from agente.sesion import Sesion
from tienda import repositorio


def escalar(
    cliente_id: str,
    causal: str,
    resumen: str,
    numero_pedido: str | None = None,
) -> dict:
    argumentos = {"causal": causal, "resumen": resumen}
    if numero_pedido is not None:
        argumentos["numero_pedido"] = numero_pedido
    return ejecutar(
        "escalar_a_asesor",
        json.dumps(argumentos),
        Sesion(cliente_id=cliente_id),
    )


def contenido_datos() -> dict[str, bytes]:
    return {
        archivo.name: archivo.read_bytes()
        for archivo in sorted(repositorio.DATOS.glob("*"))
    }


def test_solicitud_explicita_de_asesor_crea_escalamiento():
    resultado = escalar(
        "C-01",
        "solicitud_asesor",
        "La clienta solicita hablar con una persona.",
    )

    assert resultado == {
        "escalamiento_id": "E-001",
        "nuevo": True,
        "plazo_contacto": "máximo un día hábil",
    }


@pytest.mark.parametrize("causal", ["cobro_no_reconocido", "posible_fraude"])
def test_cobro_desconocido_o_fraude_crea_escalamiento(causal: str):
    resultado = escalar(
        "C-01",
        causal,
        "La clienta reporta un movimiento que no reconoce.",
    )

    assert resultado["nuevo"] is True
    guardado = repositorio.leer_escalamientos()[0]
    assert guardado.motivo == causal


def test_escalamiento_con_pedido_propio_registra_la_relacion():
    resultado = escalar(
        "C-01",
        "solicitud_asesor",
        "Necesita ayuda humana con el pedido.",
        "P-1002",
    )

    assert resultado["nuevo"] is True
    guardado = repositorio.leer_escalamientos()[0]
    assert guardado.numero_pedido == "P-1002"


def test_pedido_ajeno_e_inexistente_devuelven_la_misma_indisponibilidad():
    ajeno = escalar(
        "C-01",
        "solicitud_asesor",
        "Solicita ayuda con el pedido indicado.",
        "P-1004",
    )
    inexistente = escalar(
        "C-01",
        "solicitud_asesor",
        "Solicita ayuda con el pedido indicado.",
        "P-9999",
    )

    assert ajeno == {"error": "Pedido no disponible para esta sesión."}
    assert inexistente == ajeno
    assert repositorio.leer_escalamientos() == []


def test_escalamiento_general_sin_pedido_esta_permitido():
    resultado = escalar(
        "C-02",
        "posible_fraude",
        "El cliente sospecha acceso fraudulento a su cuenta.",
    )

    assert resultado["nuevo"] is True
    guardado = repositorio.leer_escalamientos()[0]
    assert guardado.numero_pedido is None


@pytest.mark.parametrize("resumen", ["", "   "])
def test_resumen_vacio_se_rechaza_sin_escribir(resumen: str):
    resultado = escalar("C-01", "solicitud_asesor", resumen)

    assert resultado == {"error": "El resumen del caso es obligatorio."}
    assert repositorio.leer_escalamientos() == []


def test_mismo_caso_normalizado_no_crea_registros_repetidos():
    primero = escalar(
        "C-01",
        "solicitud_asesor",
        "Necesita ayuda con la entrega",
        "P-1002",
    )
    segundo = escalar(
        "C-01",
        "solicitud_asesor",
        "  NECESITA   AYUDA con la entrega  ",
        "P-1002",
    )

    assert primero["nuevo"] is True
    assert segundo == {
        "escalamiento_id": primero["escalamiento_id"],
        "nuevo": False,
        "plazo_contacto": "máximo un día hábil",
    }
    assert len(repositorio.leer_escalamientos()) == 1


def test_persistencia_usa_cliente_y_fecha_de_la_sesion():
    resumen = "La clienta solicita revisión humana del caso."
    escalar("C-05", "solicitud_asesor", resumen, "P-1013")

    assert repositorio.leer_escalamientos() == [
        repositorio.Escalamiento(
            id="E-001",
            cliente_id="C-05",
            numero_pedido="P-1013",
            fecha=repositorio.HOY,
            motivo="solicitud_asesor",
            resumen=resumen,
        )
    ]


def test_sesion_invalida_no_puede_crear_caso_general():
    resultado = escalar(
        "C-INEXISTENTE",
        "solicitud_asesor",
        "Solicita hablar con una persona.",
    )

    assert resultado == {"error": "Cliente de sesión no disponible."}
    assert repositorio.leer_escalamientos() == []


def test_argumentos_adicionales_no_sustituyen_identidad_ni_contadores():
    resultado = ejecutar(
        "escalar_a_asesor",
        json.dumps(
            {
                "causal": "solicitud_asesor",
                "resumen": "Solicita ayuda.",
                "cliente_id": "C-02",
                "tres_intentos": True,
            }
        ),
        Sesion(cliente_id="C-01"),
    )

    assert resultado["error"] == "Argumentos inválidos."
    assert repositorio.leer_escalamientos() == []


def test_tres_intentos_no_es_una_causal_publica_sin_contador_verificado():
    resultado = escalar(
        "C-01",
        "tres_intentos",
        "El modelo afirma que ya hubo tres intentos.",
    )

    assert resultado["error"] == "Argumentos inválidos."
    assert repositorio.leer_escalamientos() == []


def test_rechazos_no_modifican_ningun_archivo_de_datos():
    antes = contenido_datos()

    assert "error" in escalar("C-01", "solicitud_asesor", "", "P-1002")
    assert "error" in escalar(
        "C-01",
        "solicitud_asesor",
        "Caso asociado a pedido no autorizado.",
        "P-1004",
    )
    assert "error" in escalar(
        "C-INEXISTENTE",
        "posible_fraude",
        "Caso general con sesión inválida.",
    )

    assert contenido_datos() == antes


def test_funcion_de_reembolso_alto_es_reutilizable_y_no_es_herramienta_llm():
    sesion = Sesion(cliente_id="C-02")
    resumen = "Reembolso de $420.000 pendiente de aprobación humana."

    primero = escalar_reembolso_superior_al_tope(
        sesion,
        numero_pedido="P-1005",
        monto=420_000,
        resumen=resumen,
    )
    segundo = escalar_reembolso_superior_al_tope(
        sesion,
        numero_pedido="P-1005",
        monto=420_000,
        resumen=resumen,
    )

    assert primero["nuevo"] is True
    assert segundo["nuevo"] is False
    assert segundo["escalamiento_id"] == primero["escalamiento_id"]
    assert "aprobado" not in primero
    assert "reembolso" not in primero
    assert "escalar_reembolso_superior_al_tope" not in HERRAMIENTAS
    guardado = repositorio.leer_escalamientos()[0]
    assert guardado.motivo == "reembolso_superior_300000"
    assert len(repositorio.leer_escalamientos()) == 1


def test_funcion_de_reembolso_rechaza_monto_que_no_supera_el_tope():
    antes = contenido_datos()

    with pytest.raises(
        ErrorDeHerramienta,
        match=r"solo aplica a reembolsos superiores a \$300\.000",
    ):
        escalar_reembolso_superior_al_tope(
            Sesion(cliente_id="C-01"),
            numero_pedido="P-1002",
            monto=300_000,
            resumen="No supera el tope de aprobación directa.",
        )

    assert contenido_datos() == antes


def test_funcion_de_reembolso_rechaza_pedido_ajeno_sin_escribir():
    antes = contenido_datos()

    with pytest.raises(ErrorDeHerramienta, match="Pedido no disponible"):
        escalar_reembolso_superior_al_tope(
            Sesion(cliente_id="C-01"),
            numero_pedido="P-1005",
            monto=420_000,
            resumen="Reembolso alto para un pedido no autorizado.",
        )

    assert contenido_datos() == antes
