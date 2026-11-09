"""Preparación y registro seguro de reclamos con selección explícita."""

from dataclasses import dataclass, replace
import re

from pydantic import BaseModel, ConfigDict, Field

from agente.herramientas.pedidos import PEDIDO_NO_DISPONIBLE
from agente.herramientas.registro import ErrorDeHerramienta, herramienta
from agente.sesion import ReclamoPendiente, Sesion
from tienda import repositorio


PLAZOS_POR_CATEGORIA = {
    "perecedero": 3,
    "ropa": 30,
    "electronica": 90,
    "hogar": 15,
}

SELECCIONES_TIPO = {
    "1": "defectuoso",
    "2": "incompleto",
    "3": "diferente",
}


class ArgsRegistrarReclamo(BaseModel):
    """Pedido y producto; el relato y la selección proceden del turno real."""

    model_config = ConfigDict(extra="forbid", strict=True)

    numero_pedido: str = Field(
        min_length=1,
        description="Número del pedido sobre el que el cliente desea reclamar.",
    )
    producto: str | None = Field(
        default=None,
        description=(
            "Nombre del producto afectado. Es obligatorio cuando el pedido contiene "
            "productos de categorías distintas."
        ),
    )


@dataclass
class CasoValidado:
    pedido: repositorio.Pedido
    producto: repositorio.Producto | None
    categoria: str
    reclamos: list[repositorio.Reclamo]
    plazo: int
    dias_transcurridos: int


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


def _reclamo_existente(reclamo: repositorio.Reclamo) -> dict:
    return {
        "registrado": False,
        "reclamo_existente": {"id": reclamo.id, "estado": reclamo.estado},
    }


def _validar_caso(
    sesion: Sesion,
    numero_pedido: str,
    nombre_producto: str | None,
) -> CasoValidado | dict:
    pedido = next(
        (
            candidato
            for candidato in repositorio.leer_pedidos()
            if candidato.numero == numero_pedido
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
        return _reclamo_existente(abierto)

    categorias = {producto.categoria for producto in pedido.productos}
    producto = _producto_afectado(pedido, nombre_producto)

    if nombre_producto is not None and nombre_producto.strip() and producto is None:
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

    if producto is None and len(pedido.productos) == 1:
        producto = pedido.productos[0]
    categoria = producto.categoria if producto is not None else pedido.productos[0].categoria

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

    return CasoValidado(
        pedido=pedido,
        producto=producto,
        categoria=categoria,
        reclamos=reclamos,
        plazo=plazo,
        dias_transcurridos=dias_transcurridos,
    )


def capturar_motivo(sesion: Sesion, mensaje: str) -> None:
    """Conserva solo relato explícito del mensaje real, nunca argumentos del LLM."""
    coincidencia = re.search(r"(?is)\bmotivo:(.*)", mensaje)
    if coincidencia and coincidencia.group(1).strip():
        pedidos = re.findall(r"\bP-\d+\b", mensaje, flags=re.I)
        sesion.relato_reclamo = (sesion.cliente_id, pedidos[0].upper() if len(pedidos) == 1 else None,
                                coincidencia.group(1), sesion.turnos)


def _motivo_cliente(sesion, numero):
    # Los tests directos y el ciclo usan el mismo origen: mensaje_actual real.
    capturar_motivo(sesion, sesion.mensaje_actual or "")
    relato = sesion.relato_reclamo
    if relato and relato[0] == sesion.cliente_id and relato[1] in {None, numero} and 0 <= sesion.turnos - relato[3] <= 2:
        return relato[2]
    return ""


def _solicitud_seleccion(pendiente: ReclamoPendiente) -> dict:
    if not pendiente.motivo.strip():
        return {"registrado": False, "reclamo_preparado": True, "requiere_aclaracion": True,
                "numero_pedido": pendiente.numero_pedido, "campo": "motivo",
                "mensaje": "Antes de registrar, describe qué ocurrió con el producto en un mensaje nuevo que empiece por motivo:. Por ejemplo: motivo: el audífono izquierdo no enciende. Una solicitud de reclamo o una opción numérica no reemplazan esa descripción."}
    return {
        "registrado": False,
        "reclamo_preparado": True,
        "requiere_seleccion": True,
        "numero_pedido": pendiente.numero_pedido,
        "producto": pendiente.producto,
        "opciones": {
            "1": "defectuoso",
            "2": "incompleto",
            "3": "diferente al comprado",
            "cancelar": "no continuar con el reclamo",
        },
        "mensaje": (
            "El reclamo todavía no se ha registrado. Pide al cliente que responda "
            "en un turno nuevo con 1 si el producto es defectuoso, 2 si está "
            "incompleto, 3 si es diferente al comprado o cancelar para detenerse."
        ),
    }


def _registrar_validado(
    sesion: Sesion,
    pendiente: ReclamoPendiente,
    tipo_motivo: str,
    caso: CasoValidado,
) -> dict:
    reclamo = repositorio.Reclamo(
        id=_siguiente_id(caso.reclamos),
        numero_pedido=caso.pedido.numero,
        cliente_id=sesion.cliente_id,
        fecha=repositorio.HOY,
        motivo=pendiente.motivo,
        estado="abierto",
    )
    repositorio.guardar_reclamos([*caso.reclamos, reclamo])
    sesion.relato_reclamo = None
    return {
        "registrado": True,
        "tipo_motivo": tipo_motivo,
        "reclamo": {
            "id": reclamo.id,
            "numero_pedido": reclamo.numero_pedido,
            "fecha": reclamo.fecha.isoformat(),
            "estado": reclamo.estado,
            "motivo": reclamo.motivo,
        },
        "producto": caso.producto.nombre if caso.producto is not None else None,
        "categoria": caso.categoria,
        "plazo_dias": caso.plazo,
        "dias_transcurridos": caso.dias_transcurridos,
        "mensaje": f"El reclamo {reclamo.id} fue registrado correctamente.",
    }


@herramienta
def registrar_reclamo(sesion: Sesion, args: ArgsRegistrarReclamo) -> dict:
    """Valida y prepara un reclamo; una selección posterior del cliente lo registra."""
    if sesion.reclamo_pendiente is not None:
        return _solicitud_seleccion(sesion.reclamo_pendiente)
    if sesion.operacion_pendiente is not None:
        return _aclaracion(
            "operacion_pendiente",
            "Resuelve o descarta la operación pendiente antes de preparar el reclamo.",
        )

    validado = _validar_caso(sesion, args.numero_pedido, args.producto)
    if isinstance(validado, dict):
        return validado

    motivo = _motivo_cliente(sesion, validado.pedido.numero)

    pendiente = ReclamoPendiente(
        numero_pedido=validado.pedido.numero,
        producto=(
            validado.producto.nombre if validado.producto is not None else None
        ),
        motivo=motivo,
        turno_preparacion=sesion.turnos,
    )
    sesion.reclamo_pendiente = pendiente
    sesion.relato_reclamo = None
    return _solicitud_seleccion(pendiente)


def procesar_seleccion_reclamo(sesion: Sesion, mensaje: str) -> dict | None:
    """Procesa solo respuestas del protocolo pendiente, sin delegarlas al LLM.

    Un texto sustantivo no se interpreta como una selección inválida: descarta
    el pendiente y devuelve ``None`` para que el ciclo atienda la nueva solicitud.
    """
    pendiente = sesion.reclamo_pendiente
    if pendiente is None:
        return None

    seleccion = " ".join(mensaje.split()).casefold()
    if sesion.turnos <= pendiente.turno_preparacion:
        return {
            "registrado": False,
            "seleccion_mismo_turno": True,
            "mensaje": "La selección debe provenir de un turno posterior del cliente.",
        }

    if seleccion == "cancelar":
        sesion.reclamo_pendiente = None
        return {
            "registrado": False,
            "cancelado": True,
            "mensaje": "Se canceló la preparación del reclamo y no se creó ningún registro.",
        }

    if not pendiente.motivo.strip():
        coincidencia = re.fullmatch(r"(?is)motivo:(.*)", mensaje)
        if coincidencia and coincidencia.group(1).strip():
            sesion.relato_reclamo = None
            sesion.reclamo_pendiente = replace(pendiente, motivo=coincidencia.group(1), turno_preparacion=sesion.turnos)
            return _solicitud_seleccion(sesion.reclamo_pendiente)
        if seleccion.isdecimal() or coincidencia:
            return _solicitud_seleccion(pendiente)
        sesion.reclamo_pendiente = None
        return None

    tipo_motivo = SELECCIONES_TIPO.get(seleccion)
    if tipo_motivo is None:
        sesion.reclamo_pendiente = None
        if not seleccion.isdecimal():
            return None
        return {
            "registrado": False,
            "seleccion_invalida": True,
            "mensaje": (
                "La selección no es válida y no se registró el reclamo. "
                "Inicia nuevamente y elige 1, 2, 3 o cancelar."
            ),
        }

    # La autorización se consume antes de revalidar para impedir su reutilización.
    sesion.reclamo_pendiente = None
    try:
        validado = _validar_caso(
            sesion,
            pendiente.numero_pedido,
            pendiente.producto,
        )
    except ErrorDeHerramienta as error:
        return {
            "registrado": False,
            "error": str(error),
            "mensaje": str(error),
        }
    if isinstance(validado, dict):
        validado.setdefault("mensaje", "No fue posible registrar el reclamo.")
        return validado
    return _registrar_validado(sesion, pendiente, tipo_motivo, validado)
