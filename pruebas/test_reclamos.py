"""Pruebas deterministas del registro de reclamos, sin llamar al modelo."""

import json
from datetime import date

import pytest

from agente import herramientas  # noqa: F401  (registra las herramientas)
from agente.herramientas.registro import ejecutar
from agente.sesion import Sesion
from tienda import repositorio


def registrar(
    numero_pedido: str,
    cliente_id: str,
    motivo: str | None = "El producto llegó dañado.",
    tipo_motivo: str | None = "defectuoso",
    producto: str | None = None,
) -> dict:
    argumentos = {
        "numero_pedido": numero_pedido,
        "motivo": motivo,
        "tipo_motivo": tipo_motivo,
    }
    if producto is not None:
        argumentos["producto"] = producto
    return ejecutar("registrar_reclamo", json.dumps(argumentos), Sesion(cliente_id=cliente_id))


def cambiar_entrega(numero_pedido: str, fecha_entrega: date) -> None:
    pedidos = repositorio.leer_pedidos()
    pedido = next(pedido for pedido in pedidos if pedido.numero == numero_pedido)
    pedido.estado = "entregado"
    pedido.fecha_entrega = fecha_entrega
    repositorio.guardar_pedidos(pedidos)


def cantidad_reclamos(numero_pedido: str, estado: str | None = None) -> int:
    return sum(
        1
        for reclamo in repositorio.leer_reclamos()
        if reclamo.numero_pedido == numero_pedido
        and (estado is None or reclamo.estado == estado)
    )


def contenido_datos() -> dict[str, bytes]:
    return {
        archivo.name: archivo.read_bytes()
        for archivo in sorted(repositorio.DATOS.glob("*"))
    }


def test_pedido_propio_entregado_y_elegible_crea_reclamo():
    resultado = registrar("P-1002", "C-01")

    assert resultado["registrado"] is True
    assert resultado["categoria"] == "electronica"
    assert resultado["plazo_dias"] == 90
    assert cantidad_reclamos("P-1002", "abierto") == 1


def test_pedido_ajeno_e_inexistente_devuelven_la_misma_indisponibilidad():
    ajeno = registrar("P-1004", "C-01")
    inexistente = registrar("P-9999", "C-01")

    assert ajeno == {"error": "Pedido no disponible para esta sesión."}
    assert inexistente == ajeno


def test_pedido_no_entregado_se_rechaza():
    resultado = registrar("P-1001", "C-01")

    assert resultado == {
        "error": "Solo se pueden registrar reclamos de pedidos entregados."
    }
    assert cantidad_reclamos("P-1001") == 0


@pytest.mark.parametrize(
    ("numero", "cliente", "categoria", "fecha_entrega"),
    [
        ("P-1002", "C-01", "electronica", None),
        ("P-1004", "C-02", "ropa", None),
        ("P-1012", "C-05", "perecedero", None),
        ("P-1014", "C-05", "hogar", date(2026, 10, 20)),
    ],
)
def test_aplica_el_plazo_de_las_cuatro_categorias(
    numero: str,
    cliente: str,
    categoria: str,
    fecha_entrega: date | None,
):
    if fecha_entrega is not None:
        cambiar_entrega(numero, fecha_entrega)

    resultado = registrar(numero, cliente)

    assert resultado["registrado"] is True
    assert resultado["categoria"] == categoria


def test_cliente_regular_perecedero_tiene_tres_dias():
    cambiar_entrega("P-1003", date(2026, 10, 30))

    resultado = registrar("P-1003", "C-01")

    assert resultado["registrado"] is True
    assert resultado["plazo_dias"] == 3
    assert resultado["dias_transcurridos"] == 3


def test_dia_de_entrega_es_un_intervalo_valido():
    cambiar_entrega("P-1003", repositorio.HOY)

    resultado = registrar("P-1003", "C-01")

    assert resultado["registrado"] is True
    assert resultado["dias_transcurridos"] == 0


def test_fecha_de_entrega_futura_se_rechaza_sin_escribir():
    cambiar_entrega("P-1003", date(2026, 11, 3))
    antes = contenido_datos()

    resultado = registrar("P-1003", "C-01")

    assert resultado == {
        "error": (
            "La fecha de entrega no puede ser posterior a la fecha actual de la tienda."
        )
    }
    assert contenido_datos() == antes
    assert cantidad_reclamos("P-1003") == 0


def test_cliente_preferente_recibe_quince_dias_adicionales():
    cambiar_entrega("P-1012", date(2026, 10, 15))

    resultado = registrar("P-1012", "C-05")

    assert resultado["registrado"] is True
    assert resultado["plazo_dias"] == 18
    assert resultado["dias_transcurridos"] == 18


@pytest.mark.parametrize(
    ("fecha_entrega", "debe_registrar"),
    [
        (date(2026, 10, 30), True),
        (date(2026, 10, 29), False),
    ],
)
def test_ultimo_dia_regular_es_inclusivo_y_el_siguiente_se_rechaza(
    fecha_entrega: date,
    debe_registrar: bool,
):
    cambiar_entrega("P-1003", fecha_entrega)

    resultado = registrar("P-1003", "C-01")

    assert resultado.get("registrado", False) is debe_registrar
    if not debe_registrar:
        assert resultado == {"error": "El plazo para registrar el reclamo ya venció."}
        assert cantidad_reclamos("P-1003") == 0


@pytest.mark.parametrize(
    ("fecha_entrega", "debe_registrar"),
    [
        (date(2026, 10, 15), True),
        (date(2026, 10, 14), False),
    ],
)
def test_ultimo_dia_preferente_incluye_los_quince_dias_adicionales(
    fecha_entrega: date,
    debe_registrar: bool,
):
    cambiar_entrega("P-1012", fecha_entrega)

    resultado = registrar("P-1012", "C-05")

    assert resultado.get("registrado", False) is debe_registrar
    if not debe_registrar:
        assert resultado == {"error": "El plazo para registrar el reclamo ya venció."}


def test_reclamo_abierto_devuelve_estado_sin_crear_duplicado():
    antes = cantidad_reclamos("P-1007", "abierto")
    resultado = ejecutar(
        "registrar_reclamo",
        json.dumps({"numero_pedido": "P-1007"}),
        Sesion(cliente_id="C-03"),
    )

    assert resultado == {
        "registrado": False,
        "reclamo_existente": {"id": "R-001", "estado": "abierto"},
    }
    assert cantidad_reclamos("P-1007", "abierto") == antes


def test_reclamo_cerrado_no_impide_crear_uno_nuevo():
    resultado = registrar(
        "P-1004",
        "C-02",
        "La chaqueta nueva llegó incompleta.",
        "incompleto",
    )

    assert resultado["registrado"] is True
    assert cantidad_reclamos("P-1004", "cerrado") == 1
    assert cantidad_reclamos("P-1004", "abierto") == 1


def test_motivo_ausente_o_vacio_pide_aclaracion():
    ausente = registrar("P-1002", "C-01", motivo=None)
    vacio = registrar("P-1002", "C-01", motivo="   ")

    assert ausente["requiere_aclaracion"] is True
    assert ausente["campo"] == "motivo"
    assert vacio["requiere_aclaracion"] is True
    assert vacio["campo"] == "motivo"
    assert cantidad_reclamos("P-1002") == 0


def test_motivo_ambiguo_pide_identificar_una_causa_permitida():
    resultado = registrar(
        "P-1002",
        "C-01",
        motivo="Los audífonos llegaron mal.",
        tipo_motivo=None,
    )

    assert resultado["requiere_aclaracion"] is True
    assert resultado["campo"] == "tipo_motivo"
    assert resultado["opciones"] == ["defectuoso", "incompleto", "diferente"]
    assert cantidad_reclamos("P-1002") == 0


def test_tipo_de_motivo_no_permitido_es_argumento_invalido():
    resultado = ejecutar(
        "registrar_reclamo",
        json.dumps(
            {
                "numero_pedido": "P-1002",
                "motivo": "Ya no lo quiero.",
                "tipo_motivo": "arrepentimiento",
            }
        ),
        Sesion(cliente_id="C-01"),
    )

    assert resultado["error"] == "Argumentos inválidos."
    assert cantidad_reclamos("P-1002") == 0


def test_diagnostico_tipo_permitido_no_prueba_coherencia_con_el_relato():
    """Caracteriza una limitación vigente; no afirma que este reclamo sea válido."""
    motivo_discrepante = "Ya no quiero el producto."

    resultado = registrar(
        "P-1002",
        "C-01",
        motivo=motivo_discrepante,
        tipo_motivo="defectuoso",
    )

    assert resultado["registrado"] is True
    guardado = next(
        reclamo
        for reclamo in repositorio.leer_reclamos()
        if reclamo.numero_pedido == "P-1002"
    )
    assert guardado.motivo == motivo_discrepante


@pytest.mark.parametrize("tipo", ["defectuoso", "incompleto", "diferente"])
def test_acepta_solo_los_tres_tipos_de_motivo_de_la_politica(tipo: str):
    resultado = registrar(
        "P-1002",
        "C-01",
        motivo=f"Descripción del producto {tipo}.",
        tipo_motivo=tipo,
    )

    assert resultado["registrado"] is True


def test_pedido_mixto_exige_un_producto_que_pertenezca_al_pedido():
    sin_producto = registrar("P-1010", "C-04")
    producto_ajeno = registrar("P-1010", "C-04", producto="Televisor 55 pulgadas")

    assert sin_producto["requiere_aclaracion"] is True
    assert sin_producto["campo"] == "producto"
    assert producto_ajeno["requiere_aclaracion"] is True
    assert producto_ajeno["campo"] == "producto"
    assert cantidad_reclamos("P-1010") == 0


def test_pedido_mixto_obtiene_la_categoria_del_producto_real():
    resultado = registrar("P-1010", "C-04", producto="Caja de chocolates")

    assert resultado["registrado"] is True
    assert resultado["producto"] == "Caja de chocolates"
    assert resultado["categoria"] == "perecedero"
    assert resultado["plazo_dias"] == 3


def test_no_admite_identidad_ni_categoria_inyectadas_como_argumentos():
    resultado = ejecutar(
        "registrar_reclamo",
        json.dumps(
            {
                "numero_pedido": "P-1004",
                "cliente_id": "C-02",
                "categoria": "ropa",
                "motivo": "La prenda llegó incompleta.",
                "tipo_motivo": "incompleto",
            }
        ),
        Sesion(cliente_id="C-01"),
    )

    assert resultado["error"] == "Argumentos inválidos."
    assert cantidad_reclamos("P-1004", "abierto") == 0


def test_persistencia_conserva_identidad_fecha_y_motivo_del_cliente():
    motivo = "  El audífono izquierdo no emite sonido.  "
    resultado = registrar("P-1002", "C-01", motivo, "defectuoso")
    guardado = next(
        reclamo
        for reclamo in repositorio.leer_reclamos()
        if reclamo.numero_pedido == "P-1002"
    )

    assert resultado["reclamo"]["id"] == "R-003"
    assert guardado == repositorio.Reclamo(
        id="R-003",
        numero_pedido="P-1002",
        cliente_id="C-01",
        fecha=repositorio.HOY,
        motivo=motivo,
        estado="abierto",
    )


def test_rechazos_y_aclaraciones_no_escriben_en_los_datos():
    antes = contenido_datos()

    assert "error" in registrar("P-1004", "C-01")
    assert "error" in registrar("P-9999", "C-01")
    assert "error" in registrar("P-1001", "C-01")
    assert "error" in registrar("P-1003", "C-01")
    assert registrar("P-1002", "C-01", motivo=None)["requiere_aclaracion"] is True

    assert contenido_datos() == antes


def test_llamadas_repetidas_no_crean_duplicados():
    primero = registrar("P-1002", "C-01")
    segundo = registrar("P-1002", "C-01")

    assert primero["registrado"] is True
    assert segundo == {
        "registrado": False,
        "reclamo_existente": {"id": primero["reclamo"]["id"], "estado": "abierto"},
    }
    assert cantidad_reclamos("P-1002", "abierto") == 1
