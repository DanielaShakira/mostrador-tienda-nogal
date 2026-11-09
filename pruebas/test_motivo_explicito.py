import json
from agente import herramientas
from agente.herramientas.registro import ejecutar
from agente.herramientas.reclamos import capturar_motivo
from agente.pendientes import procesar_operacion_pendiente
from agente.sesion import Sesion
from tienda import repositorio


def test_peticion_generica_y_uno_no_registran_motivo_inventado():
    s=Sesion(cliente_id="C-01",turnos=1,mensaje_actual="Quiero registrar un reclamo de P-1002.")
    r=ejecutar("registrar_reclamo",json.dumps({"numero_pedido":"P-1002"}),s)
    assert r["campo"]=="motivo"
    s.turnos+=1
    r=procesar_operacion_pendiente(s,"1")
    assert r["requiere_aclaracion"]
    assert not any(x.numero_pedido=="P-1002" for x in repositorio.leer_reclamos())
    s.turnos+=1
    r=procesar_operacion_pendiente(s,"motivo:El audífono no enciende.")
    assert r["requiere_seleccion"]
    s.turnos+=1
    assert procesar_operacion_pendiente(s,"1")["registrado"]
    assert repositorio.leer_reclamos()[-1].motivo=="El audífono no enciende."


def test_descripcion_previa_sobrevive_al_numero_en_turno_siguiente():
    s=Sesion(cliente_id="C-01",turnos=1,mensaje_actual="motivo:El audífono izquierdo no enciende.")
    capturar_motivo(s,s.mensaje_actual)
    s.turnos+=1
    s.mensaje_actual="Mi número de pedido es P-1002."
    r=ejecutar("registrar_reclamo",json.dumps({"numero_pedido":"P-1002"}),s)
    assert r["requiere_seleccion"]
    assert s.reclamo_pendiente.motivo=="El audífono izquierdo no enciende."


def test_motivo_otro_pedido_no_se_reutiliza():
    s=Sesion(cliente_id="C-01",turnos=1,mensaje_actual="P-1016 motivo:El organizador está roto.")
    capturar_motivo(s,s.mensaje_actual)
    s.turnos+=1
    s.mensaje_actual="P-1002"
    r=ejecutar("registrar_reclamo",json.dumps({"numero_pedido":"P-1002"}),s)
    assert r["campo"]=="motivo"
