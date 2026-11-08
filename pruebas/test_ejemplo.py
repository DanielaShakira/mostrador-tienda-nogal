"""Pruebas de ejemplo. No llaman al modelo: ejecutan las herramientas directamente.

Correr con:  python -m pytest
"""
import json

from agente import herramientas  # noqa: F401  (registra las herramientas)
from agente.herramientas.registro import ejecutar
from agente.sesion import Sesion


def test_consultar_politica_devuelve_la_seccion_pedida():
    resultado = ejecutar("consultar_politica", json.dumps({"tema": "reclamos"}), Sesion(cliente_id="C-01"))
    assert resultado["tema"] == "reclamos"
    assert "90 días" in resultado["texto"]


def test_argumento_invalido_vuelve_como_error_y_no_como_excepcion():
    resultado = ejecutar("consultar_politica", json.dumps({"tema": "garantias"}), Sesion(cliente_id="C-01"))
    assert "error" in resultado
