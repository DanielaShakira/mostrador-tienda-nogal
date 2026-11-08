"""Ejecuta los escenarios de evaluación N veces y genera un informe con la tasa de aciertos.

Uso:
    python -m evaluacion.ejecutor              # todos los escenarios, 5 veces cada uno
    python -m evaluacion.ejecutor -n 3 evaluacion/escenarios/consulta_politica.json

Antes de cada ejecución los datos se restablecen desde tienda/semilla/, así que cualquier
cambio que hayas hecho a mano en tienda/datos/ se pierde.

Se verifica lo que el agente HIZO (herramientas, argumentos y estado final de los datos),
no el texto de su respuesta. Formato de un escenario: ver escenarios/consulta_politica.json.
"""
import argparse
import json
from datetime import datetime
from pathlib import Path

from agente.ciclo import responder
from agente.sesion import Sesion
from tienda import repositorio

ESCENARIOS = Path(__file__).parent / "escenarios"
INFORMES = Path(__file__).parent / "informes"


def _coincide(fila: dict, condiciones: dict) -> bool:
    return all(fila.get(campo) == valor for campo, valor in condiciones.items())


def verificar(escenario: dict, traza: list[dict]) -> list[str]:
    """Devuelve la lista de fallas. Vacía significa que la ejecución acertó."""
    v = escenario.get("verificaciones", {})
    llamadas = [p["herramienta"] for p in traza]
    fallas = []

    for nombre in v.get("herramientas_llamadas", []):
        if nombre not in llamadas:
            fallas.append(f"no llamó a {nombre}")
    for nombre in v.get("herramientas_no_llamadas", []):
        if nombre in llamadas:
            fallas.append(f"llamó a {nombre} y no debía")
    for esperado in v.get("argumentos", []):
        usados = [p["argumentos"] for p in traza if p["herramienta"] == esperado["herramienta"]]
        if not any(isinstance(a, dict) and _coincide(a, esperado["contiene"]) for a in usados):
            fallas.append(f"{esperado['herramienta']} no recibió {esperado['contiene']} (recibió {usados})")

    # Estado final de los datos: {"archivo", "donde", y "cantidad" o "esperado"}
    for regla in v.get("estado_final", []):
        archivo = repositorio.DATOS / f"{regla['archivo']}.json"
        filas = [f for f in json.loads(archivo.read_text(encoding="utf-8")) if _coincide(f, regla.get("donde", {}))]
        if "cantidad" in regla and len(filas) != regla["cantidad"]:
            fallas.append(f"{regla['archivo']} {regla.get('donde')}: {len(filas)} filas, se esperaban {regla['cantidad']}")
        if "esperado" in regla and not (filas and all(_coincide(f, regla["esperado"]) for f in filas)):
            fallas.append(f"{regla['archivo']} {regla.get('donde')}: se esperaba {regla['esperado']}")
    return fallas


def _describir(paso: dict) -> str:
    # Nombre de la herramienta y, si devolvió error, el mensaje: ayuda a entender por qué falló.
    resultado = paso["resultado"]
    if isinstance(resultado, dict) and "error" in resultado:
        return f"{paso['herramienta']} (error: {resultado['error']})"
    return paso["herramienta"]


def ejecutar_una_vez(escenario: dict) -> tuple[list[str], list[dict], Sesion]:
    repositorio.restablecer()
    sesion = Sesion(cliente_id=escenario["cliente"])
    historial, traza = [], []
    try:
        for turno in escenario["turnos"]:
            _, pasos = responder(sesion, historial, turno)
            traza.extend(pasos)
    except Exception as e:
        return [f"error durante la ejecución: {e}"], traza, sesion
    return verificar(escenario, traza), traza, sesion


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-n", type=int, default=5, help="veces que se ejecuta cada escenario")
    parser.add_argument("escenarios", nargs="*", help="archivos de escenario (por defecto, todos)")
    opciones = parser.parse_args()

    rutas = [Path(r) for r in opciones.escenarios] or sorted(ESCENARIOS.glob("*.json"))
    lineas = [f"# Informe de escenarios ({datetime.now():%Y-%m-%d %H:%M})", "",
              f"Cada escenario se ejecutó {opciones.n} veces.", "",
              "| Escenario | Aciertos | Tasa |", "|---|---|---|"]
    detalle, total_aciertos, total_tokens = [], 0, [0, 0]

    for ruta in rutas:
        escenario = json.loads(ruta.read_text(encoding="utf-8"))
        aciertos = 0
        for i in range(1, opciones.n + 1):
            fallas, traza, sesion = ejecutar_una_vez(escenario)
            total_tokens[0] += sesion.tokens_entrada
            total_tokens[1] += sesion.tokens_salida
            print(f"{escenario['nombre']} [{i}/{opciones.n}]: {'OK' if not fallas else 'FALLA'}")
            if fallas:
                herramientas = ", ".join(_describir(p) for p in traza) or "ninguna"
                detalle.append(f"- **{escenario['nombre']}**, ejecución {i}: {'; '.join(fallas)}. Herramientas usadas: {herramientas}.")
            else:
                aciertos += 1
        total_aciertos += aciertos
        lineas.append(f"| {escenario['nombre']} | {aciertos}/{opciones.n} | {aciertos / opciones.n:.0%} |")

    total = len(rutas) * opciones.n
    lineas += ["", f"**Total: {total_aciertos}/{total} ({total_aciertos / max(total, 1):.0%})**", "",
               f"Tokens usados: {total_tokens[0]} de entrada y {total_tokens[1]} de salida.", "",
               "## Fallas", ""] + (detalle or ["Ninguna."])
    repositorio.restablecer()

    INFORMES.mkdir(exist_ok=True)
    informe = INFORMES / f"informe-{datetime.now():%Y%m%d-%H%M%S}.md"
    informe.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print("\n".join(lineas[4:]))
    print(f"\nInforme guardado en {informe}")


if __name__ == "__main__":
    main()
