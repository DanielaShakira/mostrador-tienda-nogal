"""Herramienta para registrar reclamos de pedidos autorizados."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from agente.herramientas.pedidos import PEDIDO_NO_DISPONIBLE
from agente.herramientas.registro import ErrorDeHerramienta, herramienta
from agente.sesion import Sesion
from tienda import repositorio


TipoMotivo = Literal["defectuoso", "incompleto", "diferente"]

PLAZOS_POR_CATEGORIA = {
    "perecedero": 3,
    "ropa": 30,
    "electronica": 90,
    "hogar": 15,
}


class ArgsRegistrarReclamo(BaseModel):
    """Datos aportados por el cliente; su identidad se toma siempre de la sesión."""

    model_config = ConfigDict(extra="forbid", strict=True)

    numero_pedido: str = Field(
        min_length=1,
        description="Número del pedido sobre el que el cliente desea reclamar.",
    )
    motivo: str | None = Field(
        default=None,
        description="Descripción textual del problema expresada por el cliente.",
    )
    tipo_motivo: TipoMotivo | None = Field(
        default=None,
        description=(
            "Causa identificada en lo dicho por el cliente: defectuoso, incompleto "
            "o diferente. Se deja vacío si hace falta aclararla."
        ),
    )
    producto: str | None = Field(
        default=None,
        description=(
            "Nombre del producto afectado. Es obligatorio cuando el pedido contiene "
            "productos de categorías distintas."
        ),
    )


def _aclaracion(campo: str, mensaje: str, opciones: list[str] | None = None) -> dict:
    resultado = {
        "registrado": False,
        "requiere_aclaracion": True,
        "campo": campo,
        "mensaje": mensaje,
    }
    if opciones:
        resultado["opciones"] = opciones
    return resultado


def _producto_afectado(pedido: repositorio.Pedido, nombre: str | None):
    if nombre is not None and nombre.strip():
        buscado = nombre.strip().casefold()
        return next(
            (producto for producto in pedido.productos if producto.nombre.casefold() == buscado),
            None,
        )
    return None


def _siguiente_id(reclamos: list[repositorio.Reclamo]) -> str:
    usados = {reclamo.id for reclamo in reclamos}
    numero = 1
    while f"R-{numero:03d}" in usados:
        numero += 1
    return f"R-{numero:03d}"


@herramienta
def registrar_reclamo(sesion: Sesion, args: ArgsRegistrarReclamo) -> dict:
    """Registra un reclamo elegible de un pedido perteneciente al cliente de la sesión."""
    pedido = next(
        (
            candidato
            for candidato in repositorio.leer_pedidos()
            if candidato.numero == args.numero_pedido
            and candidato.cliente_id == sesion.cliente_id
        ),
        None,
    )
    if pedido is None:
        raise ErrorDeHerramienta(PEDIDO_NO_DISPONIBLE)

    if pedido.estado != "entregado":
        raise ErrorDeHerramienta("Solo se pueden registrar reclamos de pedidos entregados.")

    reclamos = repositorio.leer_reclamos()
    abierto = next(
        (
            reclamo
            for reclamo in reclamos
            if reclamo.numero_pedido == pedido.numero
            and reclamo.cliente_id == sesion.cliente_id
            and reclamo.estado == "abierto"
        ),
        None,
    )
    if abierto is not None:
        return {
            "registrado": False,
            "reclamo_existente": {"id": abierto.id, "estado": abierto.estado},
        }

    categorias = {producto.categoria for producto in pedido.productos}
    producto = _producto_afectado(pedido, args.producto)

    if args.producto is not None and args.producto.strip() and producto is None:
        return _aclaracion(
            "producto",
            "El producto indicado no aparece en este pedido. Aclara cuál fue el afectado.",
            [item.nombre for item in pedido.productos],
        )

    if len(categorias) > 1 and producto is None:
        return _aclaracion(
            "producto",
            "Indica el producto afectado para determinar el plazo aplicable.",
            [item.nombre for item in pedido.productos],
        )

    if not pedido.productos:
        raise ErrorDeHerramienta("No se pudo determinar la categoría del producto.")

    categoria = producto.categoria if producto is not None else pedido.productos[0].categoria

    if args.motivo is None or not args.motivo.strip():
        return _aclaracion(
            "motivo",
            "Describe qué ocurrió con el producto antes de registrar el reclamo.",
        )

    if args.tipo_motivo is None:
        return _aclaracion(
            "tipo_motivo",
            "Aclara si el producto es defectuoso, está incompleto o es diferente al comprado.",
            ["defectuoso", "incompleto", "diferente"],
        )

    # El Literal limita los valores posibles, pero no demuestra que la causa elegida
    # sea coherente con el relato. Esa garantía requiere confirmación del cliente u
    # otro mecanismo externo al contrato actual.
    cliente = next(
        cliente
        for cliente in repositorio.leer_clientes()
        if cliente.id == sesion.cliente_id
    )
    plazo = PLAZOS_POR_CATEGORIA[categoria]
    if cliente.categoria == "preferente":
        plazo += 15

    dias_transcurridos = (repositorio.HOY - pedido.fecha_entrega).days
    if dias_transcurridos < 0:
        raise ErrorDeHerramienta(
            "La fecha de entrega no puede ser posterior a la fecha actual de la tienda."
        )
    if dias_transcurridos > plazo:
        raise ErrorDeHerramienta("El plazo para registrar el reclamo ya venció.")

    reclamo = repositorio.Reclamo(
        id=_siguiente_id(reclamos),
        numero_pedido=pedido.numero,
        cliente_id=sesion.cliente_id,
        fecha=repositorio.HOY,
        motivo=args.motivo,
        estado="abierto",
    )
    repositorio.guardar_reclamos([*reclamos, reclamo])

    return {
        "registrado": True,
        "reclamo": {
            "id": reclamo.id,
            "numero_pedido": reclamo.numero_pedido,
            "fecha": reclamo.fecha.isoformat(),
            "estado": reclamo.estado,
            "motivo": reclamo.motivo,
        },
        "producto": producto.nombre if producto is not None else None,
        "categoria": categoria,
        "plazo_dias": plazo,
        "dias_transcurridos": dias_transcurridos,
    }
