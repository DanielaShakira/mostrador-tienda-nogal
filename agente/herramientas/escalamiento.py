"""Escalamiento seguro de casos a un asesor humano."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from agente.herramientas.pedidos import PEDIDO_NO_DISPONIBLE
from agente.herramientas.registro import ErrorDeHerramienta, herramienta
from agente.sesion import Sesion
from tienda import repositorio


CausalConversacional = Literal[
    "solicitud_asesor",
    "cobro_no_reconocido",
    "posible_fraude",
]

MOTIVO_REEMBOLSO_ALTO = "reembolso_superior_300000"
MOTIVO_TRES_INTENTOS = "tres_intentos_sin_resolver"
PLAZO_CONTACTO = "máximo un día hábil"


class ArgsEscalarAAsesor(BaseModel):
    """Datos del caso; la identidad siempre procede de la sesión."""

    model_config = ConfigDict(extra="forbid", strict=True)

    causal: CausalConversacional = Field(
        description=(
            "Causal expresada en la conversación: solicitud_asesor, "
            "cobro_no_reconocido o posible_fraude."
        )
    )
    resumen: str = Field(
        description="Resumen breve del caso para el asesor humano."
    )
    numero_pedido: str | None = Field(
        default=None,
        description="Pedido relacionado, si el caso corresponde a uno concreto.",
    )


def _normalizar(texto: str) -> str:
    return " ".join(texto.split()).casefold()


def _siguiente_id(escalamientos: list[repositorio.Escalamiento]) -> str:
    usados = {escalamiento.id for escalamiento in escalamientos}
    numero = 1
    while f"E-{numero:03d}" in usados:
        numero += 1
    return f"E-{numero:03d}"


def validar_cliente_y_pedido(sesion: Sesion, numero_pedido: str | None) -> None:
    cliente_valido = any(
        cliente.id == sesion.cliente_id for cliente in repositorio.leer_clientes()
    )
    if not cliente_valido:
        raise ErrorDeHerramienta("Cliente de sesión no disponible.")

    if numero_pedido is None:
        return

    pedido_autorizado = any(
        pedido.numero == numero_pedido and pedido.cliente_id == sesion.cliente_id
        for pedido in repositorio.leer_pedidos()
    )
    if not pedido_autorizado:
        raise ErrorDeHerramienta(PEDIDO_NO_DISPONIBLE)


def _registrar_o_reutilizar(
    sesion: Sesion,
    motivo: str,
    resumen: str,
    numero_pedido: str | None,
) -> dict:
    if not resumen.strip():
        raise ErrorDeHerramienta("El resumen del caso es obligatorio.")

    validar_cliente_y_pedido(sesion, numero_pedido)
    escalamientos = repositorio.leer_escalamientos()
    resumen_normalizado = _normalizar(resumen)

    existente = next(
        (
            escalamiento
            for escalamiento in escalamientos
            if escalamiento.cliente_id == sesion.cliente_id
            and escalamiento.numero_pedido == numero_pedido
            and escalamiento.motivo == motivo
            and _normalizar(escalamiento.resumen) == resumen_normalizado
        ),
        None,
    )
    if existente is not None:
        return {
            "escalamiento_id": existente.id,
            "nuevo": False,
            "plazo_contacto": PLAZO_CONTACTO,
        }

    escalamiento = repositorio.Escalamiento(
        id=_siguiente_id(escalamientos),
        cliente_id=sesion.cliente_id,
        numero_pedido=numero_pedido,
        fecha=repositorio.HOY,
        motivo=motivo,
        resumen=resumen,
    )
    repositorio.guardar_escalamientos([*escalamientos, escalamiento])
    return {
        "escalamiento_id": escalamiento.id,
        "nuevo": True,
        "plazo_contacto": PLAZO_CONTACTO,
    }


@herramienta
def escalar_a_asesor(sesion: Sesion, args: ArgsEscalarAAsesor) -> dict:
    """Escala a un asesor por solicitud del cliente, cobro desconocido o posible fraude."""
    # El Literal impide causales distintas, pero la correspondencia con lo expresado
    # por el cliente depende de la interpretación conversacional del modelo.
    return _registrar_o_reutilizar(
        sesion=sesion,
        motivo=args.causal,
        resumen=args.resumen,
        numero_pedido=args.numero_pedido,
    )


def escalar_reembolso_superior_al_tope(
    sesion: Sesion,
    numero_pedido: str,
    monto: int,
    resumen: str,
    *, acumulado: int | None = None,
) -> dict:
    """Registra una solicitud de aprobación humana para un reembolso superior al tope.

    Esta función no está decorada como herramienta: debe llamarla el módulo de
    reembolsos después de validar el monto y la procedencia del reembolso. Aquí se
    vuelve a comprobar el umbral y la titularidad, y nunca se aprueba ni se ejecuta
    un reembolso.
    """
    if isinstance(monto, bool) or not isinstance(monto, int):
        raise ErrorDeHerramienta("El monto del reembolso debe ser un número entero.")
    validar_cliente_y_pedido(sesion, numero_pedido)
    pedido = next(p for p in repositorio.leer_pedidos() if p.numero == numero_pedido and p.cliente_id == sesion.cliente_id)
    if monto <= 0 or monto > pedido.total:
        raise ErrorDeHerramienta("El monto no puede superar el total pagado ni ser no positivo.")
    if acumulado is not None:
        if type(acumulado) is not int:
            raise ErrorDeHerramienta("El acumulado debe ser un entero.")
        aprobado = sum(r.monto for r in repositorio.leer_reembolsos() if r.numero_pedido == numero_pedido and r.estado == "aprobado")
        if acumulado != aprobado + monto or acumulado > pedido.total:
            raise ErrorDeHerramienta("El acumulado no coincide con los movimientos reales o supera el total.")
    if (monto if acumulado is None else acumulado) <= 300_000:
        raise ErrorDeHerramienta(
            "Este escalamiento solo aplica a reembolsos superiores a $300.000."
        )

    return _registrar_o_reutilizar(
        sesion=sesion,
        motivo=MOTIVO_REEMBOLSO_ALTO,
        resumen=resumen,
        numero_pedido=numero_pedido,
    )


def escalar_por_tres_intentos(sesion: Sesion) -> dict:
    """Escala el caso activo al comprobar tres fallos guardados por Python.

    No es una herramienta del LLM: no recibe contador, identidad, pedido ni resumen.
    """
    caso = sesion.caso_soporte
    if caso is None:
        raise ErrorDeHerramienta("No existe un caso de soporte activo.")
    if caso.cliente_id != sesion.cliente_id:
        raise ErrorDeHerramienta("El caso de soporte no pertenece a esta sesión.")
    if caso.intentos_fallidos < 3:
        raise ErrorDeHerramienta(
            "El caso todavía no tiene tres intentos fallidos confirmados."
        )
    if caso.estado == "resuelto":
        raise ErrorDeHerramienta("El caso de soporte ya figura como resuelto.")

    validar_cliente_y_pedido(sesion, caso.numero_pedido)
    if caso.escalamiento_id is not None:
        caso.estado = "escalado"
        return {
            "escalamiento_id": caso.escalamiento_id,
            "nuevo": False,
            "plazo_contacto": PLAZO_CONTACTO,
        }

    resumen = (
        f"Caso {caso.caso_id}: problema sin resolver después de tres intentos. "
        f"Relato inicial: {caso.relato_inicial.strip()}"
    )
    resultado = _registrar_o_reutilizar(
        sesion=sesion,
        motivo=MOTIVO_TRES_INTENTOS,
        resumen=resumen,
        numero_pedido=caso.numero_pedido,
    )
    caso.escalamiento_id = resultado["escalamiento_id"]
    caso.estado = "escalado"
    return resultado
