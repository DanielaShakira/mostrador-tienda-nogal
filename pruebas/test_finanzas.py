"""Controles financieros directos y fallos simulados; no consumen modelo."""
import json
from dataclasses import replace
from datetime import timedelta

import pytest

from agente import herramientas
from agente.herramientas.registro import ejecutar, esquemas
from agente.herramientas.finanzas import procesar_confirmacion_financiera
from agente.pendientes import procesar_operacion_pendiente
from agente.sesion import Sesion, FinanzasPendientes
from tienda import repositorio as repo


def cambiar(numero="P-1001", *, estado="pagado", total=100000, dias=0, instante=None):
    pedidos = repo.leer_pedidos()
    pedido = next(p for p in pedidos if p.numero == numero)
    pedido.estado = estado
    pedido.fecha_compra = repo.HOY - timedelta(days=dias)
    pedido.instante_compra = instante
    pedido.productos = [repo.Producto(nombre="Producto de prueba", categoria="hogar", cantidad=1, precio_unitario=total)]
    pedido.total = total
    repo.guardar_pedidos(pedidos)
    return pedido


def preparar(accion="cancelar_pedido", numero="P-1001", monto=100000, cliente="C-01", extra=None):
    sesion = Sesion(cliente_id=cliente, turnos=1, mensaje_actual="Solicito la operación indicada.")
    args = {"numero_pedido": numero}
    if accion == "solicitar_reembolso":
        args["monto"] = monto
    args.update(extra or {})
    return ejecutar(accion, json.dumps(args), sesion), sesion


def confirmar(sesion, texto=None, avanzar=True):
    if avanzar:
        sesion.turnos += 1
    texto = texto or f"confirmar {sesion.operacion_pendiente.codigo}"
    sesion.mensaje_actual = texto
    return procesar_operacion_pendiente(sesion, texto)


def movimientos(monto, estado="aprobado", numero="P-1001"):
    repo.guardar_reembolsos([repo.Reembolso(id="D-previo", numero_pedido=numero, cliente_id="C-01", fecha=repo.HOY, monto=monto, motivo="Anterior", estado=estado)])


def contenido():
    return {p.name: p.read_bytes() for p in repo.DATOS.glob("*.json") if not p.name.startswith(".")}


def test_preparacion_no_escribe_y_confirmacion_cancela_devuelve_una_vez():
    cambiar()
    antes = contenido()
    resultado, s = preparar()
    assert resultado["preparado"] and not resultado["ejecutado"]
    assert contenido() == antes
    codigo = s.operacion_pendiente.codigo
    resultado = confirmar(s)
    assert resultado["ejecutado"]
    assert next(p for p in repo.leer_pedidos() if p.numero == "P-1001").estado == "cancelado"
    assert repo.leer_reembolsos()[0].monto == 100000
    assert repo.leer_reembolsos()[0].estado == "aprobado"
    assert repo.leer_reembolsos()[0].medio_pago == "tarjeta_original"
    assert s.operacion_pendiente is None
    assert procesar_confirmacion_financiera(s, f"confirmar {codigo}") is None
    assert len(repo.leer_reembolsos()) == 1


@pytest.mark.parametrize("estado", ["enviado", "entregado", "cancelado"])
def test_cancelacion_rechaza_estados_sin_escribir(estado):
    cambiar(estado=estado)
    antes = contenido()
    res, s = preparar()
    assert "error" in res
    assert contenido() == antes and s.operacion_pendiente is None


@pytest.mark.parametrize("horas,admite", [(0,True),(23.999,True),(24,True),(24.001,False),(48,False),(-1,False)])
def test_preparacion_limite_exacto_24_horas(horas, admite):
    instante = repo.AHORA - timedelta(hours=horas)
    cambiar(estado="en_preparacion", dias=(repo.HOY-instante.date()).days, instante=instante)
    res, s = preparar()
    assert bool(res.get("preparado")) is admite
    if not admite:
        assert not repo.leer_reembolsos()


@pytest.mark.parametrize("dias,admite", [(0,True),(1,False),(2,False),(-1,False)])
def test_fecha_sin_hora_no_inventa_24_horas(dias, admite):
    cambiar(estado="en_preparacion", dias=dias)
    res, _ = preparar()
    assert bool(res.get("preparado")) is admite


def test_pagado_no_tiene_limite_de_24_horas():
    cambiar(dias=10)
    res, _ = preparar()
    assert res["preparado"]


@pytest.mark.parametrize("total,estado", [(299999,"aprobado"),(300000,"aprobado"),(300001,"solicitado")])
def test_cancelacion_total_y_tope_inclusivo(total, estado):
    cambiar(total=total)
    _, s = preparar()
    res = confirmar(s)
    assert res["ejecutado"]
    assert repo.leer_reembolsos()[0].monto == total
    assert repo.leer_reembolsos()[0].estado == estado
    assert len(repo.leer_escalamientos()) == (estado == "solicitado")
    if estado == "solicitado":
        assert "máximo un día hábil" in res["mensaje"]
        assert repo.leer_escalamientos()[0].resumen


@pytest.mark.parametrize("accion", ["cancelar_pedido","solicitar_reembolso"])
def test_pedido_ajeno_e_inexistente_no_revelan_ni_escriben(accion):
    a,_ = preparar(accion, numero="P-1005")
    b,_ = preparar(accion, numero="P-9999")
    assert a == b == {"error": "Pedido no disponible para esta sesión."}
    assert not repo.leer_reembolsos()


@pytest.mark.parametrize("extra", [{"confirmado":True},{"cliente_id":"C-02"},{"confirmacion_cliente":"sí"},{"codigo":"falso"}])
def test_modelo_no_puede_inyectar_confirmacion(extra):
    cambiar()
    res,s = preparar(extra=extra)
    assert res["error"] == "Argumentos inválidos."
    assert s.operacion_pendiente is None and not repo.leer_reembolsos()


@pytest.mark.parametrize("texto", ["sí","no confirmar","confirmar falso","1","Quiero hablar con un asesor","Ahora cancela P-1005"])
def test_otra_respuesta_no_autoriza_y_descarta(texto):
    cambiar()
    _,s = preparar()
    antes = contenido()
    confirmar(s,texto)
    assert s.operacion_pendiente is None and contenido() == antes


def test_mismo_turno_no_confirma():
    cambiar()
    _,s = preparar()
    res=confirmar(s,avanzar=False)
    assert not res["ejecutado"] and isinstance(s.operacion_pendiente,FinanzasPendientes)
    assert not repo.leer_reembolsos()


def test_cambio_cliente_consume_sin_autorizar():
    cambiar()
    _,s=preparar()
    s.cliente_id="C-02"
    res=confirmar(s)
    assert not res["ejecutado"] and s.operacion_pendiente is None
    assert not repo.leer_reembolsos()


def test_cambio_datos_obliga_nueva_confirmacion():
    cambiar()
    _,s=preparar()
    cambiar(total=200000)
    res=confirmar(s)
    assert not res["ejecutado"] and not repo.leer_reembolsos()


def test_dos_sesiones_no_duplican_cancelacion():
    cambiar()
    _,a=preparar()
    _,b=preparar()
    assert confirmar(a)["ejecutado"]
    assert not confirmar(b)["ejecutado"]
    assert len(repo.leer_reembolsos())==1


@pytest.mark.parametrize("monto", [0,-1,True,1.5,"100000"])
def test_monto_invalido_es_rechazado(monto):
    cambiar(estado="cancelado")
    res,s=preparar("solicitar_reembolso",monto=monto)
    assert res["error"] == "Argumentos inválidos."
    assert s.operacion_pendiente is None


def test_reembolso_sin_procedencia_no_se_prepara():
    cambiar()
    res,_=preparar("solicitar_reembolso")
    assert "error" in res and not repo.leer_reembolsos()


def test_reembolso_reclamo_abierto_y_no_cerrado():
    # P-1007 tiene reclamo abierto; P-1004 solo cerrado.
    res,s=preparar("solicitar_reembolso",numero="P-1007",monto=300000,cliente="C-03")
    assert res["preparado"] and confirmar(s)["ejecutado"]
    res,_=preparar("solicitar_reembolso",numero="P-1004",monto=10000,cliente="C-02")
    assert "error" in res


def test_saldo_acumulado_impide_superar_total():
    cambiar(estado="cancelado",total=400000)
    movimientos(200000)
    antes=contenido()
    res,_=preparar("solicitar_reembolso",monto=200001)
    assert "saldo" in res["error"] and contenido()==antes


def test_fraccionar_no_salta_tope_autonomo():
    cambiar(estado="cancelado",total=400000)
    movimientos(200000)
    res,s=preparar("solicitar_reembolso",monto=150000)
    assert res["requiere_asesor"]
    assert confirmar(s)["ejecutado"]
    assert repo.leer_reembolsos()[-1].monto==150000
    assert repo.leer_reembolsos()[-1].estado=="solicitado"
    assert len(repo.leer_escalamientos())==1


def test_solicitud_pendiente_reserva_saldo_y_no_duplica():
    cambiar(estado="cancelado",total=500000)
    movimientos(350000,"solicitado")
    antes=contenido()
    res,_=preparar("solicitar_reembolso",monto=100000)
    assert "pendiente" in res["error"] and contenido()==antes


def test_cancelacion_con_movimiento_previo_no_duplica_total():
    cambiar(total=200000)
    movimientos(10000)
    res,_=preparar()
    assert "error" in res


def test_una_operacion_pendiente_no_puede_reemplazarse():
    cambiar()
    _,s=preparar()
    anterior=s.operacion_pendiente
    res=ejecutar("cancelar_pedido",json.dumps({"numero_pedido":"P-1001"}),s)
    assert "error" in res and s.operacion_pendiente is anterior


def test_error_persistencia_restaura_cancelacion_escalamiento_y_reembolso(monkeypatch):
    cambiar(total=350000)
    _,s=preparar()
    antes=contenido()
    def fallo(_):
        raise OSError("Disco simulado no disponible")
    monkeypatch.setattr(repo,"guardar_reembolsos",fallo)
    res=confirmar(s)
    assert not res["ejecutado"]
    assert contenido()==antes
    assert s.operacion_pendiente is None


def test_recuperacion_tras_interrupcion_antes_de_leer():
    cambiar()
    antes=contenido()
    diario={k:v.decode("utf-8") for k,v in antes.items()}
    (repo.DATOS/".nogal-transaccion.json").write_text(json.dumps(diario),encoding="utf-8")
    pedidos=json.loads((repo.DATOS/"pedidos.json").read_text(encoding="utf-8"))
    pedidos[0]["estado"]="cancelado"
    (repo.DATOS/"pedidos.json").write_text(json.dumps(pedidos),encoding="utf-8")
    repo.leer_pedidos()
    assert contenido()==antes
    assert not (repo.DATOS/".nogal-transaccion.json").exists()


def test_ninguna_herramienta_llm_confirma():
    nombres={s["function"]["name"] for s in esquemas()}
    assert "cancelar_pedido" in nombres and "solicitar_reembolso" in nombres
    assert "confirmacion_financiera" not in nombres
