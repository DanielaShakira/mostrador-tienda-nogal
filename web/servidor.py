"""Servidor local: sirve la página y conecta la interfaz con el agente.

Se ejecuta con:  python -m uvicorn web.servidor:app --port 8000

Guarda una sola conversación en memoria: es una herramienta de desarrollo para una persona.
"""
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agente.ciclo import responder
from agente.sesion import Sesion
from tienda import repositorio

app = FastAPI(title="Mostrador")
ESTATICOS = Path(__file__).parent / "estatico"
app.mount("/estatico", StaticFiles(directory=ESTATICOS), name="estatico")

conversacion = {"sesion": None, "historial": []}


class NuevaSesion(BaseModel):
    cliente_id: str


class Mensaje(BaseModel):
    texto: str


def _validar_datos():
    try:
        repositorio.validar_todo()
    except repositorio.ErrorDeDatos as e:
        raise HTTPException(status_code=422, detail=f"Hay un problema en los datos: {e}")


@app.get("/")
def pagina():
    return FileResponse(ESTATICOS / "index.html")


@app.get("/api/clientes")
def clientes():
    _validar_datos()
    return [{"id": c.id, "nombre": c.nombre} for c in repositorio.leer_clientes()]


@app.post("/api/sesion")
def nueva_sesion(datos: NuevaSesion):
    conversacion["sesion"] = Sesion(cliente_id=datos.cliente_id)
    conversacion["historial"] = []
    return {"cliente_id": datos.cliente_id}


@app.post("/api/mensaje")
def mensaje(datos: Mensaje):
    sesion = conversacion["sesion"]
    if sesion is None:
        raise HTTPException(status_code=400, detail="Primero elige un cliente.")
    _validar_datos()
    historial = conversacion["historial"]
    largo_previo = len(historial)
    try:
        texto, traza = responder(sesion, historial, datos.texto)
    except Exception as e:
        # Errores de conexión o de credencial con el intermediario: se deshace el turno
        # incompleto para poder reintentar, y el error se muestra en la interfaz.
        del historial[largo_previo:]
        raise HTTPException(status_code=502, detail=f"Error al hablar con el modelo: {e}")
    return {
        "respuesta": texto,
        "traza": traza,
        "turnos": sesion.turnos,
        "tokens": {"entrada": sesion.tokens_entrada, "salida": sesion.tokens_salida},
    }


@app.post("/api/restablecer")
def restablecer():
    repositorio.restablecer()
    if conversacion["sesion"]:
        nueva_sesion(NuevaSesion(cliente_id=conversacion["sesion"].cliente_id))
    return {"ok": True}
