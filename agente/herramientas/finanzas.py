"""Preparación sin efectos y confirmación financiera fuera del control del LLM."""
import hashlib
import json
import secrets
from datetime import timedelta

from pydantic import BaseModel, ConfigDict, Field

from agente.herramientas.escalamiento import escalar_reembolso_superior_al_tope, validar_cliente_y_pedido
from agente.herramientas.pedidos import PEDIDO_NO_DISPONIBLE
from agente.herramientas.registro import ErrorDeHerramienta, herramienta
from agente.sesion import FinanzasPendientes, Sesion
from tienda import repositorio

TOPE = 300_000


class ArgsCancelarPedido(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    numero_pedido: str = Field(min_length=1, description="Pedido propio a cancelar; la devolución automática será del total.")


class ArgsSolicitarReembolso(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    numero_pedido: str = Field(min_length=1)
    monto: int = Field(gt=0, description="Pesos COP enteros solicitados por el cliente; nunca un monto inventado.")


def _pedido(sesion, numero):
    validar_cliente_y_pedido(sesion, numero)
    pedido = next((p for p in repositorio.leer_pedidos() if p.numero == numero and p.cliente_id == sesion.cliente_id), None)
    if pedido is None:
        raise ErrorDeHerramienta(PEDIDO_NO_DISPONIBLE)
    return pedido


def _validar_cancelacion(pedido):
    if pedido.fecha_compra > repositorio.HOY:
        raise ErrorDeHerramienta("La fecha de compra está en el futuro; no se puede cancelar.")
    if pedido.estado == "enviado":
        raise ErrorDeHerramienta("El pedido fue enviado y no puede cancelarse. Puedes rechazar la entrega en la puerta o reclamar después de recibirlo.")
    if pedido.estado not in {"pagado", "en_preparacion"}:
        raise ErrorDeHerramienta("La cancelación no aplica a pedidos entregados o ya cancelados.")
    if pedido.instante_compra is not None:
        horas = repositorio.AHORA - pedido.instante_compra
        if horas < timedelta(0):
            raise ErrorDeHerramienta("La hora de compra está en el futuro.")
    else:
        horas = None
    if pedido.estado == "en_preparacion":
        if horas is not None:
            if horas > timedelta(hours=24):
                raise ErrorDeHerramienta("Han pasado más de 24 horas desde la compra.")
        else:
            dias = (repositorio.HOY - pedido.fecha_compra).days
            if dias > 1:
                raise ErrorDeHerramienta("Han pasado más de 24 horas desde la compra.")
            if dias == 1:
                raise ErrorDeHerramienta("Falta la hora verificada de compra para comprobar las 24 horas; no se autoriza la cancelación con una hora declarada por el modelo o el cliente.")


def _estado(sesion, numero, accion, monto):
    pedido = _pedido(sesion, numero)
    if type(monto) is not int or monto <= 0:
        raise ErrorDeHerramienta("El monto debe ser un entero positivo en pesos.")
    devoluciones = [r for r in repositorio.leer_reembolsos() if r.numero_pedido == numero]
    if any(r.cliente_id != sesion.cliente_id or r.monto <= 0 for r in devoluciones):
        raise ErrorDeHerramienta("Hay datos de reembolsos inconsistentes; no se puede actuar.")
    aprobados = sum(r.monto for r in devoluciones if r.estado == "aprobado")
    reservados = sum(r.monto for r in devoluciones if r.estado == "solicitado")
    reclamos = [r for r in repositorio.leer_reclamos() if r.numero_pedido == numero and r.cliente_id == sesion.cliente_id and r.estado == "abierto"]
    if accion == "cancelar":
        _validar_cancelacion(pedido)
        if monto != pedido.total or devoluciones:
            raise ErrorDeHerramienta("La cancelación debe devolver el total una sola vez; existen movimientos o el total cambió.")
    elif pedido.estado != "cancelado" and not reclamos:
        raise ErrorDeHerramienta("El reembolso solo procede con pedido cancelado o reclamo abierto.")
    if monto + aprobados + reservados > pedido.total:
        raise ErrorDeHerramienta("El monto supera el saldo disponible del valor pagado.")
    if reservados:
        raise ErrorDeHerramienta("Ya existe una solicitud pendiente para este pedido; no se duplicará.")
    contenido = {"pedido": pedido.model_dump(mode="json"), "reembolsos": [r.model_dump(mode="json") for r in devoluciones],
                 "reclamos": [r.model_dump(mode="json") for r in reclamos], "acumulado": aprobados + monto}
    huella = hashlib.sha256(json.dumps(contenido, sort_keys=True).encode()).hexdigest()
    return pedido, aprobados + monto, huella


def _respuesta_preparada(pendiente):
    revision = "solicitado, sujeto a aprobación de un asesor" if pendiente.requiere_asesor else "aprobado para su devolución"
    accion = "cancelar el pedido y devolver automáticamente" if pendiente.accion == "cancelar" else "solicitar el reembolso de"
    frase = f"confirmar {pendiente.codigo}"
    return {"preparado": True, "ejecutado": False, "numero_pedido": pendiente.numero_pedido, "monto": pendiente.monto,
            "requiere_asesor": pendiente.requiere_asesor, "confirmacion": frase,
            "mensaje": f"Vas a {accion} ${pendiente.monto:,} COP del pedido {pendiente.numero_pedido}, al medio de pago original. El reembolso quedará {revision}. Para autorizar ambas consecuencias responde en un turno nuevo exactamente: {frase}. Para desistir: no confirmar. Aún no se hizo ningún cambio."}


def _preparar(sesion, accion, numero, monto):
    if sesion.operacion_pendiente is not None:
        raise ErrorDeHerramienta("Hay otra operación pendiente; no se reemplaza ni se confirma desde una herramienta.")
    pedido, acumulado, huella = _estado(sesion, numero, accion, monto)
    pendiente = FinanzasPendientes(cliente_id=sesion.cliente_id, accion=accion, numero_pedido=pedido.numero,
        monto=monto, motivo=("Cancelación y devolución automática del total." if accion == "cancelar" else "Reembolso solicitado por el cliente con procedencia validada."),
        turno_preparacion=sesion.turnos, codigo=secrets.token_hex(4), huella=huella, requiere_asesor=acumulado > TOPE)
    sesion.operacion_pendiente = pendiente
    return _respuesta_preparada(pendiente)


@herramienta
def cancelar_pedido(sesion: Sesion, args: ArgsCancelarPedido) -> dict:
    """Prepara cancelación y devolución del total; solo un mensaje posterior real autoriza."""
    return _preparar(sesion, "cancelar", args.numero_pedido, _pedido(sesion, args.numero_pedido).total)


@herramienta
def solicitar_reembolso(sesion: Sesion, args: ArgsSolicitarReembolso) -> dict:
    """Prepara devolución de monto explícito; no escribe sin confirmación posterior real."""
    return _preparar(sesion, "reembolsar", args.numero_pedido, args.monto)


def procesar_confirmacion_financiera(sesion: Sesion, mensaje: str) -> dict | None:
    pendiente = sesion.operacion_pendiente
    if not isinstance(pendiente, FinanzasPendientes):
        return None
    if sesion.turnos <= pendiente.turno_preparacion:
        return {"ejecutado": False, "mensaje": "La confirmación debe llegar en un turno posterior del cliente."}
    respuesta = " ".join(mensaje.split()).casefold()
    if respuesta != f"confirmar {pendiente.codigo}":
        sesion.operacion_pendiente = None
        if respuesta in {"no confirmar", "cancelar", "no", "si", "sí"} or respuesta.startswith("confirmar "):
            return {"ejecutado": False, "mensaje": "No se autorizó ninguna operación. Para continuar debes solicitar una nueva preparación y confirmar su código exacto."}
        return None
    # Consumir antes de escribir: ni el modelo ni un reintento pueden repetirla.
    sesion.operacion_pendiente = None
    try:
        with repositorio.transaccion():
            if sesion.cliente_id != pendiente.cliente_id:
                raise ErrorDeHerramienta("La autorización no pertenece al cliente de esta sesión.")
            pedido, acumulado, huella = _estado(sesion, pendiente.numero_pedido, pendiente.accion, pendiente.monto)
            if huella != pendiente.huella:
                raise ErrorDeHerramienta("Los datos o las condiciones cambiaron; prepara y confirma nuevamente.")
            devoluciones = repositorio.leer_reembolsos()
            usados = {r.id for r in devoluciones}
            i = 1
            while f"D-{i:03d}" in usados:
                i += 1
            reembolso = repositorio.Reembolso(id=f"D-{i:03d}", numero_pedido=pedido.numero, cliente_id=sesion.cliente_id,
                fecha=repositorio.HOY, monto=pendiente.monto, motivo=pendiente.motivo,
                estado="solicitado" if acumulado > TOPE else "aprobado", medio_pago=pedido.medio_pago or "original")
            if pendiente.accion == "cancelar":
                pedidos = repositorio.leer_pedidos()
                for item in pedidos:
                    if item.numero == pedido.numero:
                        item.estado = "cancelado"
                repositorio.guardar_pedidos(pedidos)
            escalamiento = {}
            if acumulado > TOPE:
                escalamiento = escalar_reembolso_superior_al_tope(sesion, pedido.numero, pendiente.monto,
                    f"Pedido {pedido.numero}: solicitud {reembolso.id} de ${pendiente.monto:,} COP; acumulado ${acumulado:,}. Requiere aprobación humana. {pendiente.motivo}", acumulado=acumulado)
            repositorio.guardar_reembolsos([*devoluciones, reembolso])
        texto = ("Pedido cancelado y " if pendiente.accion == "cancelar" else "")
        texto += f"reembolso {reembolso.id} de ${reembolso.monto:,} COP {reembolso.estado}, al medio original."
        if escalamiento:
            texto += f" Caso {escalamiento['escalamiento_id']}: un asesor te contactará en máximo un día hábil. No se ha aprobado ni pagado el reembolso."
        else:
            texto += " Se registró la aprobación; esta aplicación simula el trámite, no ejecuta pagos bancarios."
        return {"ejecutado": True, "accion": pendiente.accion, "reembolso": reembolso.model_dump(mode="json"),
                **escalamiento, "mensaje": texto}
    except Exception as error:
        return {"ejecutado": False, "error": str(error), "mensaje": f"No se realizó la operación: {error}. La autorización fue descartada; solicita una nueva preparación."}
