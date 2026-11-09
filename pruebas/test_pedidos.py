"""Pruebas de la consulta segura de pedidos, sin llamar al modelo."""

import json

from agente import herramientas  # noqa: F401  (registra las herramientas)
from agente.herramientas.registro import ejecutar
from agente.sesion import Sesion
from tienda import repositorio


def consultar(numero_pedido: str, cliente_id: str) -> dict:
    return ejecutar(
        "consultar_pedido",
        json.dumps({"numero_pedido": numero_pedido}),
        Sesion(cliente_id=cliente_id),
    )


def test_consulta_pedido_propio_devuelve_solo_datos_necesarios():
    resultado = consultar("P-1002", "C-01")

    assert resultado == {
        "numero": "P-1002",
        "estado": "entregado",
        "fecha_compra": "2026-10-15",
        "fecha_entrega": "2026-10-20",
        "productos": [{"nombre": "Audífonos inalámbricos", "cantidad": 1}],
    }
    assert "cliente_id" not in resultado
    assert "nota_cliente" not in resultado
    assert "total" not in resultado


def test_consulta_pedido_ajeno_devuelve_indisponibilidad():
    resultado = consultar("P-1004", "C-01")

    assert resultado == {"error": "Pedido no disponible para esta sesión."}


def test_pedido_inexistente_devuelve_la_misma_indisponibilidad_que_uno_ajeno():
    ajeno = consultar("P-1004", "C-01")
    inexistente = consultar("P-9999", "C-01")

    assert inexistente == ajeno


def test_identidad_de_sesion_invalida_no_autoriza_ningun_pedido():
    resultado = consultar("P-1002", "C-INEXISTENTE")

    assert resultado == {"error": "Pedido no disponible para esta sesión."}


def test_argumentos_invalidos_vuelven_como_error():
    sin_numero = ejecutar("consultar_pedido", "{}", Sesion(cliente_id="C-01"))
    con_identidad_inyectada = ejecutar(
        "consultar_pedido",
        json.dumps({"numero_pedido": "P-1004", "cliente_id": "C-02"}),
        Sesion(cliente_id="C-01"),
    )

    assert sin_numero["error"] == "Argumentos inválidos."
    assert con_identidad_inyectada["error"] == "Argumentos inválidos."


def test_pedido_ajeno_no_filtra_informacion_privada():
    resultado = consultar("P-1011", "C-01")
    serializado = json.dumps(resultado, ensure_ascii=False)

    assert resultado == {"error": "Pedido no disponible para esta sesión."}
    assert "C-04" not in serializado
    assert "Set de ollas" not in serializado
    assert "70000" not in serializado
    assert "supervisor" not in serializado
    assert "reembolso" not in serializado


def test_nota_de_pedido_propio_no_se_devuelve_ni_se_trata_como_instruccion():
    resultado = consultar("P-1011", "C-04")
    serializado = json.dumps(resultado, ensure_ascii=False)

    assert resultado["numero"] == "P-1011"
    assert resultado["estado"] == "entregado"
    assert "nota_cliente" not in resultado
    assert "supervisor" not in serializado
    assert "reembolso" not in serializado


def test_consulta_no_escribe_en_los_datos():
    archivos = sorted(repositorio.DATOS.glob("*"))
    contenido_antes = {archivo.name: archivo.read_bytes() for archivo in archivos}

    assert "error" not in consultar("P-1002", "C-01")
    assert "error" in consultar("P-1004", "C-01")
    assert "error" in consultar("P-9999", "C-01")

    contenido_despues = {archivo.name: archivo.read_bytes() for archivo in archivos}
    assert contenido_despues == contenido_antes
