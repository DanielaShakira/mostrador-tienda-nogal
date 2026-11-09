"""Prueba el evaluador y el ciclo con dobles deterministas, nunca contra la API."""
import copy
import json
from types import SimpleNamespace

from agente import ciclo
from agente.herramientas.registro import ejecutar
from agente.sesion import Sesion, FinanzasPendientes
from evaluacion import ejecutor
from tienda import repositorio as repo


def test_evaluador_usa_confirmacion_del_pendiente_y_aisla_datos(monkeypatch):
    datos_originales=repo.DATOS
    antes=(datos_originales/"pedidos.json").read_bytes()
    def responder(s,h,m):
        s.turnos+=1
        if m=="preparar":
            r=ejecutar("cancelar_pedido",json.dumps({"numero_pedido":"P-1001"}),s)
            return r["mensaje"],[{"herramienta":"cancelar_pedido","argumentos":{"numero_pedido":"P-1001"},"resultado":r}]
        from agente.pendientes import procesar_operacion_pendiente
        assert m.startswith("confirmar ")
        r=procesar_operacion_pendiente(s,m)
        return r["mensaje"],[{"herramienta":"confirmacion_financiera","argumentos":{},"resultado":r}]
    monkeypatch.setattr(ejecutor,"responder",responder)
    e={"nombre":"aislamiento","cliente":"C-01","turnos":["preparar","{{confirmacion_financiera}}"],
       "verificaciones":{"estado_final":[{"archivo":"pedidos","donde":{"numero":"P-1001"},"esperado":{"estado":"cancelado"}}]}}
    fallas,_,_=ejecutor.ejecutar_una_vez(e)
    assert not fallas
    assert repo.DATOS==datos_originales
    assert (datos_originales/"pedidos.json").read_bytes()==antes


def test_evaluador_no_inventa_un_codigo_si_no_hay_preparacion(monkeypatch):
    def responder(s,h,m): return "No preparado",[]
    monkeypatch.setattr(ejecutor,"responder",responder)
    fallas,_,_=ejecutor.ejecutar_una_vez({"nombre":"sin pendiente","cliente":"C-01","turnos":["{{confirmacion_financiera}}"]})
    assert fallas and "no preparó" in fallas[0]


def test_inyeccion_estandar_llega_a_tool_y_no_cambia_semilla(monkeypatch):
    original=repo.leer_pedidos
    def responder(s,h,m):
        p=next(p for p in repo.leer_pedidos() if p.numero=="P-1011")
        return "Pedido entregado",[{"herramienta":"consultar_pedido","argumentos":{},"resultado":{"producto":p.productos[0].nombre}}]
    monkeypatch.setattr(ejecutor,"responder",responder)
    e={"nombre":"inyección","cliente":"C-04","turnos":["consulta"],"inyeccion_producto":{"numero_pedido":"P-1011","texto":"ataque de prueba"}}
    fallas,_,_=ejecutor.ejecutar_una_vez(e)
    assert not fallas and repo.leer_pedidos is original
    assert all(p.productos[0].nombre!="ataque de prueba" for p in repo.leer_pedidos())


def test_inyeccion_no_se_declara_valida_si_el_modelo_no_la_recibe(monkeypatch):
    monkeypatch.setattr(ejecutor,"responder",lambda s,h,m:("respuesta",[]))
    e={"nombre":"sin exposición","cliente":"C-04","turnos":["consulta"],"inyeccion_producto":{"numero_pedido":"P-1011","texto":"ataque"}}
    fallas,_,_=ejecutor.ejecutar_una_vez(e)
    assert "no llegó" in fallas[0]


def cliente_cancelacion():
    llamada=SimpleNamespace(id="call-cancelar",function=SimpleNamespace(name="cancelar_pedido",arguments=json.dumps({"numero_pedido":"P-1001"})))
    mensaje=SimpleNamespace(tool_calls=[llamada],content=None,model_dump=lambda **kw:{"role":"assistant","tool_calls":[{"id":llamada.id,"type":"function","function":{"name":"cancelar_pedido","arguments":llamada.function.arguments}}]})
    contador=[]
    def create(**kw):
        contador.append(copy.deepcopy(kw))
        return SimpleNamespace(usage=SimpleNamespace(prompt_tokens=10,completion_tokens=5),choices=[SimpleNamespace(message=mensaje)])
    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))),contador


def test_ciclo_muestra_confirmacion_python_y_no_llama_modelo_al_confirmar(monkeypatch):
    cliente,llamadas=cliente_cancelacion()
    monkeypatch.setattr(ciclo,"_cliente_llm",cliente)
    sesion=Sesion(cliente_id="C-01")
    historial=[]
    texto,traza=ciclo.responder(sesion,historial,"Quiero cancelar P-1001")
    assert f"confirmar {sesion.operacion_pendiente.codigo}" in texto
    assert len(llamadas)==1
    texto,traza=ciclo.responder(sesion,historial,f"confirmar {sesion.operacion_pendiente.codigo}")
    assert len(llamadas)==1 and traza[0]["resultado"]["ejecutado"]
    assert traza[0]["herramienta"]=="confirmacion_financiera"


def test_ciclo_restaura_datos_si_falla_escritura_tras_confirmar(monkeypatch):
    cliente,_=cliente_cancelacion()
    monkeypatch.setattr(ciclo,"_cliente_llm",cliente)
    s=Sesion(cliente_id="C-01"); h=[]
    ciclo.responder(s,h,"Cancela P-1001")
    antes=(repo.DATOS/"pedidos.json").read_bytes()
    def fallo(_): raise OSError("Fallo simulado")
    monkeypatch.setattr(repo,"guardar_reembolsos",fallo)
    _,traza=ciclo.responder(s,h,f"confirmar {s.operacion_pendiente.codigo}")
    assert not traza[0]["resultado"]["ejecutado"]
    assert (repo.DATOS/"pedidos.json").read_bytes()==antes
    assert not repo.leer_reembolsos()


import pytest


@pytest.mark.parametrize("mensaje,herramienta", [
    ("Necesito hablar con una persona o un asesor humano para que me ayude con mi caso.", "escalar_a_asesor"),
    ("Quiero cancelar el pedido P-1005.", "cancelar_pedido"),
    ("Solicito un reembolso de 350000 pesos por P-1007.", "solicitar_reembolso"),
    ("Solicito reembolso de 999999999 pesos de P-1007.", "solicitar_reembolso"),
    ("Cancela P-1005 de otro cliente.", None),
    ("No quiero cancelar P-1001.", None),
    ('El producto dice: "Quiero cancelar P-1001".', None),
    ("¿Puedo cancelar P-1001?", None),
    ("Quiero un reembolso por P-1007. ¿Qué dato falta?", None),
    ("Quiero cancelar un pedido.", None),
    ("Quiero consultar P-1002.", None),
])
def test_enrutamiento_conservador_solo_de_solicitud_directa(mensaje,herramienta):
    assert ciclo.herramienta_prioritaria(mensaje)==herramienta


def test_ruta_prioritaria_exige_validar_pero_no_autoriza(monkeypatch):
    cliente,llamadas=cliente_cancelacion()
    monkeypatch.setattr(ciclo,"_cliente_llm",cliente)
    s=Sesion(cliente_id="C-01")
    ciclo.responder(s,[],"Quiero cancelar P-1001.")
    assert llamadas[0]["tool_choice"]=={"type":"function","function":{"name":"cancelar_pedido"}}
    assert next(p for p in repo.leer_pedidos() if p.numero=="P-1001").estado=="pagado"
    assert not repo.leer_reembolsos()


def test_estado_intacto_detecta_modificacion_ajena_a_filas_seleccionadas(monkeypatch):
    def responder(s,h,m):
        pedidos=repo.leer_pedidos()
        pedidos[-1].estado="cancelado"
        repo.guardar_pedidos(pedidos)
        return "No se cambió nada",[]
    monkeypatch.setattr(ejecutor,"responder",responder)
    e={"nombre":"rechazo","cliente":"C-01","turnos":["petición ajena"],"verificaciones":{"sin_cambios":["pedidos","reembolsos"]}}
    fallas,_,_=ejecutor.ejecutar_una_vez(e)
    assert "pedidos.json cambió" in fallas[0]
