"""Cada prueba opera sobre una copia temporal de la semilla."""
import pytest
from tienda import repositorio


@pytest.fixture(autouse=True)
def datos_limpios(tmp_path, monkeypatch):
    monkeypatch.setattr(repositorio, "DATOS", tmp_path)
    repositorio.restablecer()
    yield
