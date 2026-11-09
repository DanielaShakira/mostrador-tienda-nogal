"""Ejecutar desde la terminal que tiene LLM_API_KEY; jamás imprime la clave."""
import os
from pathlib import Path
import subprocess
import sys
import uuid

raiz = Path(__file__).resolve().parent
os.chdir(raiz)
os.environ["PYTHONUTF8"] = "1"
if not all(os.environ.get(k) for k in ("LLM_API_KEY", "LLM_BASE_URL")):
    raise SystemExit("Faltan LLM_API_KEY o LLM_BASE_URL en esta terminal. No se ejecutaron escenarios.")
informes = raiz / "evaluacion" / "informes"
temporal = raiz / ".local" / ("pytest-" + uuid.uuid4().hex)
temporal.parent.mkdir(exist_ok=True)
r = subprocess.run([sys.executable, "-m", "pytest", "-q", "--basetemp", str(temporal)], capture_output=True, text=True, encoding="utf-8", errors="replace")
(informes / "pytest-final.txt").write_text(r.stdout + r.stderr, encoding="utf-8")
print(r.stdout)
if r.returncode:
    raise SystemExit(r.returncode)
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--corregidos", action="store_true", help="Una repetición de los cinco casos ajustados; si pasan, evaluación completa con cinco repeticiones")
opciones = parser.parse_args()
casos = ["cancelacion_limite_24h", "cancelacion_pedido_ajeno", "escalamiento_asesor", "reembolso_sin_procedencia", "reembolso_superior_pagado"]
rutas = [str(raiz / "evaluacion" / "escenarios" / (caso + ".json")) for caso in casos] if opciones.corregidos else []
codigo = subprocess.call([sys.executable, "-m", "evaluacion.ejecutor", "-n", "1", *rutas]) if rutas else 0
if codigo == 0:
    codigo = subprocess.call([sys.executable, "-m", "evaluacion.ejecutor", "-n", "5"])
print("Validación terminada. Los informes están en", informes)
# Iniciar la versión nueva conservando las variables de esta terminal.
import socket
with socket.socket() as s:
    ocupado = s.connect_ex(("127.0.0.1", 8000)) == 0
if not ocupado:
    logdir = raiz / ".local"
    logdir.mkdir(exist_ok=True)
    with (logdir / "servidor.log").open("ab") as log:
        proceso = subprocess.Popen([sys.executable, "-m", "uvicorn", "web.servidor:app", "--host", "127.0.0.1", "--port", "8000"],
            cwd=raiz, stdout=log, stderr=log, creationflags=(subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0))
    print("Servidor actualizado iniciado en http://localhost:8000 PID", proceso.pid)
else:
    print("El puerto 8000 está ocupado. El servidor existente permanece activo.")
raise SystemExit(codigo)
