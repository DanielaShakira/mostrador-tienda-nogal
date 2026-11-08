"""Pruebas deterministas del registro de reclamos, sin llamar al modelo."""

import json
from datetime import date

import pytest

from agente import herramientas  # noqa: F401  (registra las herramientas)
from agente.herramientas.reclamos import procesar_seleccion_reclamo
from agente.herramientas.registro import ejecutar
from agente.sesion import Sesion
from tienda import repositorio


SELECCION_POR_TIPO = {
    "defectuoso": "1",
    "incompleto": "2",
    "diferente": "3",
}


def preparar(
    numero_pedido: str,
    cliente_id: str,
    motivo: str | None = "El producto llegó dañado.",
    producto: str | None = None,
) -> tuple[dict, Sesion]:
    sesion = Sesion(
        cliente_id=cliente_id,
        turnos=1,
        mensaje_actual=motivo,
    )
    argumentos = {"numero_pedido": numero_pedido}
    if producto is not None:
        argumentos["producto"] = producto
    return ejecutar("registrar_reclamo", json.dumps(argumentos), sesion), sesion


def seleccionar(
    sesion: Sesion,
    seleccion: str,
    avanzar_turno: bool = True,
) -> dict | None:
    if avanzar_turno:
        sesion.turnos += 1
    return procesar_seleccion_reclamo(sesion, seleccion)


def registrar(
    numero_pedido: str,
    cliente_id: str,
    motivo: str | None = "El producto llegó dañado.",
    tipo_motivo: str | None = "defectuoso",
    producto: str | None = None,
) -> dict:
    preparado, sesion = preparar(numero_pedido, cliente_id, motivo, producto)
    if not preparado.get("reclamo_preparado") or tipo_motivo is None:
        return preparado
    seleccion = SELECCION_POR_TIPO.get(tipo_motivo, tipo_motivo)
    sesion.turnos += 1
    sesion.mensaje_actual = seleccion
    return procesar_seleccion_reclamo(sesion, seleccion)


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


def test_motivo_ambiguo_se_prepara_sin_escribir_y_pide_seleccion():
    resultado, sesion = preparar(
        "P-1002",
        "C-01",
        motivo="Los audífonos llegaron mal.",
    )

    assert resultado["reclamo_preparado"] is True
    assert resultado["requiere_seleccion"] is True
    assert resultado["opciones"]["1"] == "defectuoso"
    assert sesion.reclamo_pendiente.motivo == "Los audífonos llegaron mal."
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


@pytest.mark.parametrize(
    "campo_fabricado",
    [
        {"tipo_motivo": "defectuoso"},
        {"confirmado": True},
        {"confirmacion_cliente": "sí"},
    ],
)
def test_argumentos_fabricados_no_autorizan_reclamo(campo_fabricado: dict):
    sesion = Sesion(
        cliente_id="C-01",
        turnos=1,
        mensaje_actual="Ya no quiero el producto.",
    )
    argumentos = {"numero_pedido": "P-1002", **campo_fabricado}

    resultado = ejecutar(
        "registrar_reclamo",
        json.dumps(argumentos),
        sesion,
    )

    assert resultado["error"] == "Argumentos inválidos."
    assert sesion.reclamo_pendiente is None
    assert cantidad_reclamos("P-1002") == 0


def test_cambio_de_opinion_no_se_registra_sin_seleccion_real():
    resultado, sesion = preparar(
        "P-1002",
        "C-01",
        motivo="Ya no quiero el producto.",
    )

    assert resultado["reclamo_preparado"] is True
    assert resultado["registrado"] is False
    assert sesion.reclamo_pendiente.motivo == "Ya no quiero el producto."
    assert cantidad_reclamos("P-1002") == 0


@pytest.mark.parametrize(
    ("seleccion_cliente", "tipo"),
    [("1", "defectuoso"), ("2", "incompleto"), ("3", "diferente")],
)
def test_acepta_las_tres_selecciones_explicitas_de_la_politica(
    seleccion_cliente: str,
    tipo: str,
):
    preparado, sesion = preparar(
        "P-1002",
        "C-01",
        motivo=f"Descripción del producto {tipo}.",
    )

    resultado = seleccionar(sesion, seleccion_cliente)

    assert preparado["reclamo_preparado"] is True
    assert resultado["registrado"] is True
    assert resultado["tipo_motivo"] == tipo


def test_preparacion_vincula_pedido_producto_y_relato_sin_escribir():
    motivo = "El audífono izquierdo no enciende."

    resultado, sesion = preparar("P-1002", "C-01", motivo=motivo)

    assert resultado["reclamo_preparado"] is True
    assert resultado["registrado"] is False
    assert sesion.reclamo_pendiente.numero_pedido == "P-1002"
    assert sesion.reclamo_pendiente.producto == "Audífonos inalámbricos"
    assert sesion.reclamo_pendiente.motivo == motivo
    assert sesion.reclamo_pendiente.turno_preparacion == 1
    assert cantidad_reclamos("P-1002") == 0


def test_seleccion_invalida_no_escribe_y_descarta_el_pendiente():
    _, sesion = preparar("P-1002", "C-01")

    resultado = seleccionar(sesion, "4")

    assert resultado["seleccion_invalida"] is True
    assert resultado["registrado"] is False
    assert sesion.reclamo_pendiente is None
    assert cantidad_reclamos("P-1002") == 0


def test_cambio_de_pedido_en_turno_de_seleccion_no_escribe():
    _, sesion = preparar("P-1002", "C-01")

    resultado = seleccionar(sesion, "Ahora quiero reclamar por P-1016")

    assert resultado is None
    assert sesion.reclamo_pendiente is None
    assert cantidad_reclamos("P-1002") == 0
    assert cantidad_reclamos("P-1016") == 0


def test_seleccion_sin_pendiente_no_autoriza_ninguna_escritura():
    sesion = Sesion(cliente_id="C-01", turnos=2, mensaje_actual="1")

    resultado = procesar_seleccion_reclamo(sesion, "1")

    assert resultado is None
    assert cantidad_reclamos("P-1002") == 0


def test_seleccion_en_el_mismo_turno_se_rechaza_sin_consumir_pendiente():
    _, sesion = preparar("P-1002", "C-01")

    resultado = seleccionar(sesion, "1", avanzar_turno=False)

    assert resultado["seleccion_mismo_turno"] is True
    assert resultado["registrado"] is False
    assert sesion.reclamo_pendiente is not None
    assert cantidad_reclamos("P-1002") == 0


def test_autorizacion_consumida_no_se_puede_reutilizar():
    _, sesion = preparar("P-1002", "C-01")

    primero = seleccionar(sesion, "1")
    segundo = seleccionar(sesion, "1")

    assert primero["registrado"] is True
    assert segundo is None
    assert sesion.reclamo_pendiente is None
    assert cantidad_reclamos("P-1002", "abierto") == 1


def test_llm_no_puede_reemplazar_el_pedido_de_un_pendiente():
    _, sesion = preparar("P-1002", "C-01")
    sesion.mensaje_actual = "Intenta usar otro pedido."

    resultado = ejecutar(
        "registrar_reclamo",
        json.dumps({"numero_pedido": "P-1016"}),
        sesion,
    )

    assert resultado["reclamo_preparado"] is True
    assert resultado["numero_pedido"] == "P-1002"
    assert sesion.reclamo_pendiente.numero_pedido == "P-1002"
    assert cantidad_reclamos("P-1002") == 0
    assert cantidad_reclamos("P-1016") == 0


def test_seleccion_revalida_el_estado_y_consume_el_pendiente():
    _, sesion = preparar("P-1002", "C-01")
    pedidos = repositorio.leer_pedidos()
    pedido = next(item for item in pedidos if item.numero == "P-1002")
    pedido.estado = "enviado"
    repositorio.guardar_pedidos(pedidos)

    resultado = seleccionar(sesion, "1")

    assert resultado == {
        "registrado": False,
        "error": "Solo se pueden registrar reclamos de pedidos entregados.",
        "mensaje": "Solo se pueden registrar reclamos de pedidos entregados.",
    }
    assert sesion.reclamo_pendiente is None
    assert cantidad_reclamos("P-1002") == 0


def test_cliente_puede_cancelar_el_pendiente_sin_escribir():
    _, sesion = preparar("P-1002", "C-01")

    resultado = seleccionar(sesion, "cancelar")

    assert resultado["cancelado"] is True
    assert resultado["registrado"] is False
    assert sesion.reclamo_pendiente is None
    assert cantidad_reclamos("P-1002") == 0


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
