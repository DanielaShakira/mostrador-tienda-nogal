"""Revisa que ninguna credencial haya quedado escrita en un archivo del repositorio."""
import re
import subprocess
from pathlib import Path

RAIZ = Path(__file__).parent.parent
# Una credencial del intermediario: "sk-" seguido de 16 o más letras, números, guiones o guiones bajos.
FORMA_DE_CLAVE = re.compile(r"sk-[A-Za-z0-9_-]{16,}")


def test_no_hay_credenciales_en_archivos_versionados():
    # git ls-files lista los archivos que git sigue, es decir, los que terminan en GitHub.
    # -z separa los nombres con un carácter nulo, así funcionan nombres con espacios o tildes.
    salida = subprocess.run(["git", "ls-files", "-z"], cwd=RAIZ, capture_output=True, text=True, check=True).stdout
    archivos = [n for n in salida.split("\0") if n]
    hallazgos = []
    for nombre in archivos:
        ruta = RAIZ / nombre
        if not ruta.is_file():
            continue
        texto = ruta.read_text(encoding="utf-8", errors="ignore")
        for numero, linea in enumerate(texto.splitlines(), start=1):
            for clave in FORMA_DE_CLAVE.findall(linea):
                # Solo se muestra el comienzo, para no volver a filtrar la clave en la salida de pytest.
                hallazgos.append(f"{nombre}, línea {numero}: {clave[:6]}…")
    assert not hallazgos, (
        "Hay textos con forma de credencial en archivos del repositorio:\n  "
        + "\n  ".join(hallazgos)
        + "\nBórralos del archivo. La credencial va en los secretos de Codespaces (LLM_API_KEY), nunca en el código. "
        "Si ya hiciste commit, avísale al profesor para que la revoque."
    )
