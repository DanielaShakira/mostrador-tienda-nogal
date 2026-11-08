"""Herramientas de consulta segura de pedidos."""

from pydantic import BaseModel, ConfigDict, Field

from agente.herramientas.registro import ErrorDeHerramienta, herramienta
from agente.sesion import Sesion
from tienda import repositorio


PEDIDO_NO_DISPONIBLE = "Pedido no disponible para esta sesión."


class ArgsConsultarPedido(BaseModel):
    """Argumentos públicos de la consulta; la identidad proviene de la sesión."""

    model_config = ConfigDict(extra="forbid")

    numero_pedido: str = Field(
        min_length=1,
        description="Número del pedido que el cliente quiere consultar.",
    )


@herramienta
def consultar_pedido(sesion: Sesion, args: ArgsConsultarPedido) -> dict:
    """Consulta el estado de un pedido perteneciente al cliente de la sesión."""
    pedido = next(
        (
            candidato
            for candidato in repositorio.leer_pedidos()
            if candidato.numero == args.numero_pedido
            and candidato.cliente_id == sesion.cliente_id
        ),
        None,
    )

    # Se usa el mismo resultado para pedidos inexistentes, ajenos y sesiones sin acceso.
    if pedido is None:
        raise ErrorDeHerramienta(PEDIDO_NO_DISPONIBLE)

    # nota_cliente se omite deliberadamente: es texto no confiable y no es necesario
    # para explicar el estado del pedido.
    return {
        "numero": pedido.numero,
        "estado": pedido.estado,
        "fecha_compra": pedido.fecha_compra.isoformat(),
        "fecha_entrega": pedido.fecha_entrega.isoformat() if pedido.fecha_entrega else None,
        "productos": [
            {"nombre": producto.nombre, "cantidad": producto.cantidad}
            for producto in pedido.productos
        ],
    }
