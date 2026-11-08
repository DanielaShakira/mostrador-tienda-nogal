"""Lectura, escritura y validación de los datos de la tienda.

Los datos viven en archivos JSON dentro de tienda/datos/. Puedes editarlos a mano
desde el editor: cada vez que se leen se valida su estructura y, si algo quedó mal,
se lanza ErrorDeDatos con un mensaje que dice qué archivo, qué elemento y qué campo.

Para volver a los datos originales:  python -m tienda.repositorio restablecer
"""
import json
import shutil
import sys
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

DATOS = Path(__file__).parent / "datos"
SEMILLA = Path(__file__).parent / "semilla"

# Fecha simulada de la tienda. Así los plazos no cambian con el calendario real
# y todos los grupos trabajan sobre la misma situación.
HOY = date(2026, 11, 2)


class Modelo(BaseModel):
    # extra="forbid": un campo mal escrito en el JSON se reporta en vez de ignorarse.
    model_config = ConfigDict(extra="forbid")


class Cliente(Modelo):
    id: str
    nombre: str
    correo: str
    categoria: Literal["regular", "preferente"]


class Producto(Modelo):
    nombre: str
    categoria: Literal["perecedero", "ropa", "electronica", "hogar"]
    cantidad: int
    precio_unitario: int


class Pedido(Modelo):
    numero: str
    cliente_id: str
    fecha_compra: date
    fecha_entrega: date | None = None
    estado: Literal["pagado", "en_preparacion", "enviado", "entregado", "cancelado"]
    productos: list[Producto]
    total: int
    nota_cliente: str | None = None

    @model_validator(mode="after")
    def revisar_coherencia(self):
        suma = sum(p.cantidad * p.precio_unitario for p in self.productos)
        if suma != self.total:
            raise ValueError(f"el total ({self.total}) no coincide con la suma de los productos ({suma})")
        if self.estado == "entregado" and self.fecha_entrega is None:
            raise ValueError("un pedido entregado necesita fecha_entrega")
        return self


class Reclamo(Modelo):
    id: str
    numero_pedido: str
    cliente_id: str
    fecha: date
    motivo: str
    estado: Literal["abierto", "cerrado"]


class Reembolso(Modelo):
    id: str
    numero_pedido: str
    cliente_id: str
    fecha: date
    monto: int
    motivo: str
    # "solicitado": espera la aprobación de un asesor. "aprobado": ya se puede pagar.
    estado: Literal["solicitado", "aprobado"]


class Escalamiento(Modelo):
    id: str
    cliente_id: str
    numero_pedido: str | None = None
    fecha: date
    motivo: str
    resumen: str


class ErrorDeDatos(Exception):
    """Los datos de un archivo no tienen la estructura esperada."""


def _leer(nombre: str, modelo: type[Modelo]) -> list:
    ruta = DATOS / nombre
    try:
        crudo = json.loads(ruta.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ErrorDeDatos(f"{nombre}: el JSON está mal formado en la línea {e.lineno}, columna {e.colno} ({e.msg})")
    elementos = []
    for i, item in enumerate(crudo):
        try:
            elementos.append(modelo.model_validate(item))
        except ValidationError as e:
            ident = item.get("numero") or item.get("id") if isinstance(item, dict) else None
            detalles = "; ".join(f"campo '{'.'.join(map(str, err['loc'])) or '-'}': {err['msg']}" for err in e.errors())
            raise ErrorDeDatos(f"{nombre}, elemento {i} ({ident or 'sin identificador'}): {detalles}")
    return elementos


def _guardar(nombre: str, elementos: list[Modelo]) -> None:
    datos = [e.model_dump(mode="json", exclude_none=True) for e in elementos]
    (DATOS / nombre).write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def leer_clientes() -> list[Cliente]:
    return _leer("clientes.json", Cliente)


def leer_pedidos() -> list[Pedido]:
    pedidos = _leer("pedidos.json", Pedido)
    ids = {c.id for c in leer_clientes()}
    for p in pedidos:
        if p.cliente_id not in ids:
            raise ErrorDeDatos(f"pedidos.json, pedido {p.numero}: el cliente '{p.cliente_id}' no existe en clientes.json")
    return pedidos


def leer_reclamos() -> list[Reclamo]:
    return _leer("reclamos.json", Reclamo)


def leer_reembolsos() -> list[Reembolso]:
    return _leer("reembolsos.json", Reembolso)


def leer_escalamientos() -> list[Escalamiento]:
    return _leer("escalamientos.json", Escalamiento)


def guardar_pedidos(pedidos: list[Pedido]) -> None:
    _guardar("pedidos.json", pedidos)


def guardar_reclamos(reclamos: list[Reclamo]) -> None:
    _guardar("reclamos.json", reclamos)


def guardar_reembolsos(reembolsos: list[Reembolso]) -> None:
    _guardar("reembolsos.json", reembolsos)


def guardar_escalamientos(escalamientos: list[Escalamiento]) -> None:
    _guardar("escalamientos.json", escalamientos)


def leer_politicas() -> str:
    return (DATOS / "politicas.md").read_text(encoding="utf-8")


def validar_todo() -> None:
    """Lee todos los archivos para detectar errores de estructura de una vez."""
    leer_clientes()
    leer_pedidos()
    leer_reclamos()
    leer_reembolsos()
    leer_escalamientos()


def restablecer() -> None:
    """Reemplaza tienda/datos/ con la copia original de tienda/semilla/."""
    for archivo in SEMILLA.iterdir():
        shutil.copy(archivo, DATOS / archivo.name)


if __name__ == "__main__":
    if sys.argv[1:] == ["restablecer"]:
        restablecer()
        print("Datos restablecidos desde tienda/semilla/")
    else:
        validar_todo()
        print("Los datos tienen la estructura correcta")
