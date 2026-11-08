"""Configuración común de las pruebas. pytest carga este archivo automáticamente."""
import pytest

from tienda import repositorio


@pytest.fixture(autouse=True)
def datos_limpios():
    # Cada prueba empieza con los datos originales. Así, si una prueba cancela un pedido,
    # la siguiente no lo encuentra cancelado y el resultado no depende del orden.
    repositorio.restablecer()
    yield
    repositorio.restablecer()
