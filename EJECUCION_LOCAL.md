# Ejecutar y defender Tienda Nogal

## Preparar en Windows

Desde la carpeta del repositorio:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Configurar LLM_API_KEY y LLM_BASE_URL como variables de entorno de la terminal. El proyecto no carga archivos .env y la clave nunca debe guardarse en código, informes o commits. La URL del intermediario es https://clase-agente.danidev.co/v1.

```powershell
$env:LLM_BASE_URL = "https://clase-agente.danidev.co/v1"
# Configura LLM_API_KEY en tu terminal con la credencial del profesor.
.\.venv\Scripts\python.exe -m uvicorn web.servidor:app --host 127.0.0.1 --port 8000
```

Abrir http://localhost:8000 y elegir cliente. El selector simula autenticación de la actividad; no es un sistema de autenticación para producción.

## Pruebas y escenarios

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m evaluacion.ejecutor -n 5
```

Las pruebas no llaman al modelo. Los escenarios sí consumen presupuesto: son 30 archivos por cinco repeticiones. Ambos usan datos temporales por ejecución, sin borrar los datos que tengas en la interfaz. El evaluador guarda Markdown con tasas y JSON con respuestas/trazas/tokens. Devuelve código 1 si hay fallos; no oculta errores de credencial como si midieran al agente.

`python validar_entrega.py` realiza ambas verificaciones desde la terminal que tiene las variables, guarda `pytest-final.txt` y deja arrancado el servidor al terminar si el puerto está libre. No imprime la clave. Si el puerto sigue ocupado, conserva el servidor que ya existe e informa esa circunstancia.

## Conversaciones de ejemplo

- Consulta: elegir C-01 y preguntar por P-1002. Cambiar a otro cliente y comprobar que el mismo pedido deja de estar disponible sin revelar de quién es.
- Reclamo: C-01, `Quiero reclamar por P-1002. motivo:El audífono izquierdo no enciende.`; responder `1` cuando se pida la categoría. Si solo escribes una petición genérica, primero se pide `motivo:`; `1` por sí solo nunca sustituye ese relato.
- Cancelación: C-01, pedir cancelar P-1001. Copiar la frase exacta `confirmar <codigo>` de la respuesta en un turno posterior. Se registra devolución automática de $180.000. No hay doble pregunta de confirmación.
- Límite horario y monto alto: C-02, pedir cancelar P-1005, que está justo en 24 horas según AHORA simulado. Tras confirmar queda cancelado, con solicitud de $420.000 y un escalamiento; nunca aprobado autónomamente.
- Reembolso alto: C-03, pedir $350.000 de P-1007 (reclamo abierto); confirmar el desafío. Inspeccionar reembolsos.json y escalamientos.json.
- Tres intentos: solución preparada, resultado real `sigue sin resolver` en otro turno; repetir sobre el mismo caso. Solo el tercer fallo confirmado escala. `resuelto` cierra el caso y `nuevo caso` separa problemas.

Los escenarios con `{{confirmacion_financiera}}` construyen el turno del cliente a partir del desafío que Python mostró; no invocan un método que salte autorización. La inyección en nombre se aplica en cada repetición del ejecutor estándar y se verifica que el texto llegó en un resultado de herramienta.

## Dónde defender cada decisión

- Política y decisiones: ANALISIS.md.
- Identidad y minimización: agente/herramientas/pedidos.py.
- Plazo y motivo: agente/herramientas/reclamos.py.
- Confirmación y control financiero: agente/herramientas/finanzas.py.
- Unión de pendientes y despacho único: agente/sesion.py y agente/pendientes.py.
- Intentos y escalamiento: agente/herramientas/intentos.py y escalamiento.py.
- Recuperación y bloqueo de archivos: tienda/repositorio.py.
- Trazas y desafío mostrado sin reformular por el modelo: agente/ciclo.py.
- Evidencia: evaluacion/informes/ y pruebas/.

La aplicación simula registros de devolución y no mueve dinero bancario. Pendientes/casos se pierden al reiniciar; hace falta una nueva preparación y confirmación. Mantener la política y no modificar main durante la preparación del PR. El grupo entrega un solo enlace de PR en NPlad y confirma allí el plazo de la actividad.
