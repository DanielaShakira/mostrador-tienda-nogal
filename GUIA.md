# Guía del proyecto Mostrador

En este proyecto vas a construir el agente de soporte de Tienda Nogal, una tienda en línea ficticia. Un agente es un programa que conversa con el cliente usando un modelo de lenguaje y que, además de responder, puede ejecutar acciones llamando funciones de tu código. A esas funciones las llamamos herramientas.

Tu agente debe poder consultar pedidos, registrar reclamos, cancelar pedidos, solicitar reembolsos y pasar el caso a una persona cuando haga falta. La idea central del ejercicio es esta: las condiciones para ejecutar una acción se revisan en el código de la herramienta, no se le confían al modelo. Si la política dice que un pedido enviado no se puede cancelar, tu herramienta de cancelación debe negarse aunque el modelo le pida cancelarlo.

La base ya resuelve lo mecánico: hablar con el modelo, ejecutar herramientas, guardar datos, la interfaz y la evaluación. Lo que exige criterio queda en tus manos.

## 1. Crea tu repositorio y abre el codespace

1. En la página de este repositorio haz clic en **Use this template** y luego en **Create a new repository**. Solo una persona del grupo lo crea, en su cuenta, y lo deja como **Public** (público).
2. En el repositorio nuevo entra a **Settings → Collaborators** y agrega a tus compañeros de grupo y al profesor.
3. Vuelve a la pestaña **Code**, abre la pestaña **Codespaces** y haz clic en **Create codespace on main**.

Como el repositorio es público, cualquier persona en internet puede leer todos sus archivos y también su historial: cada commit que hayas hecho. Por eso la credencial de tu grupo nunca puede quedar escrita en un archivo, ni siquiera por un momento. Si la subes en un commit y en el siguiente la borras, sigue visible en el commit anterior. En ese caso avísale al profesor para que la revoque. En la sección 2 ves dónde va la credencial, y `python -m pytest` incluye una prueba que falla si encuentra algo con forma de credencial en tus archivos.

Un codespace es un computador en la nube con el proyecto listo, que usas desde el navegador. La primera vez tarda unos minutos porque instala las dependencias. Si cierras la pestaña, el codespace queda guardado y puedes volver a él desde la misma pestaña **Codespaces** del repositorio.

En el aula usa una sola pestaña del navegador para el codespace y otra para la aplicación. Los equipos se ponen lentos si abres muchas.

## 2. Configura la credencial

El agente usa un modelo de lenguaje a través de un intermediario que administra el profesor. Cada grupo tiene una credencial propia con un límite de consumo. Para que el codespace la conozca necesitas dos secretos:

| Nombre | Valor |
|---|---|
| `LLM_API_KEY` | La credencial que te entregó el profesor. Empieza por `sk-`. |
| `LLM_BASE_URL` | `https://clase-agente.danidev.co/v1` |

(LLM viene del inglés *large language model*, modelo de lenguaje grande.)

La persona que creó el repositorio los agrega en **Settings → Secrets and variables → Codespaces → New repository secret**, uno por uno. Así quedan disponibles para todo el grupo.

Los secretos nunca van en el código ni en un archivo del repositorio. Si los escribes en un archivo y haces commit, cualquiera que vea el repositorio puede gastar el presupuesto de tu grupo. Si crees que tu credencial se filtró, avísale al profesor para que la revoque y te dé otra.

Si creaste el codespace antes de agregar los secretos, reinícialo para que los tome: en la pestaña **Codespaces** del repositorio, abre el menú del codespace (los tres puntos) y elige **Stop codespace**; luego vuelve a abrirlo.

Para comprobar que quedaron bien, escribe en la terminal:

```
echo $LLM_BASE_URL
```

Debe aparecer la dirección. La credencial no la imprimas.

## 3. Corre la aplicación

En la terminal del codespace:

```
python -m uvicorn web.servidor:app --port 8000
```

Se abrirá una pestaña con la aplicación. Si no se abre, ve a la pestaña **Ports** de la parte inferior del editor y haz clic en el ícono del globo de la fila 8000.

La pantalla tiene dos partes. A la izquierda conversas con el agente como si fueras el cliente. A la derecha ves la traza: cada herramienta que el agente llamó, con qué argumentos y qué le devolvió. Arriba eliges qué cliente tiene la sesión iniciada. La aplicación simula que ese cliente ya entró a su cuenta, así que tus herramientas saben quién es sin preguntarle al modelo.

Después de cambiar código Python, detén el servidor con `Ctrl+C` y vuelve a iniciarlo. Los cambios en `agente/instrucciones.md` y en los datos se toman sin reiniciar.

## 4. Conoce el proyecto

Lee la base completa antes de escribir código. Son pocos archivos:

| Archivo | Qué hace |
|---|---|
| `agente/ciclo.py` | Envía la conversación al modelo, ejecuta las herramientas que pida y repite hasta tener la respuesta final. |
| `agente/sesion.py` | Conexión con el modelo y datos de la sesión: cliente, número de turnos y tokens usados. Un token es un pedazo de texto, a veces una palabra completa y a veces solo una parte de ella; el modelo cuenta y cobra su trabajo en tokens. |
| `agente/instrucciones.md` | Las instrucciones del agente. Está casi vacío: lo escribes tú. |
| `agente/herramientas/registro.py` | Cómo se declara una herramienta. Lee el comentario del inicio. |
| `agente/herramientas/ejemplo.py` | Una herramienta completa de ejemplo: `consultar_politica`. |
| `tienda/datos/` | Clientes, pedidos, reclamos, reembolsos, escalamientos y la política de la tienda. Los dos últimos empiezan vacíos: los llenan tus herramientas. |
| `tienda/repositorio.py` | Lee y guarda los datos, y revisa que tengan la estructura correcta. |
| `web/` | El servidor y la página. |
| `evaluacion/` | El ejecutor de escenarios. |
| `pruebas/` | Las pruebas automáticas. |

Los datos están en archivos JSON, un formato de texto para datos como `{"numero": "P-1001", "estado": "pagado"}`. Puedes editarlos directamente en el editor para crear casos nuevos. Si algo queda mal escrito, la aplicación te muestra un aviso rojo que dice en qué archivo, en qué elemento y en qué campo está el problema.

La tienda trabaja con una fecha simulada: hoy es el 2 de noviembre de 2026 (`HOY` en `tienda/repositorio.py`). Usa esa fecha para calcular plazos, no la del calendario.

Lee también `tienda/datos/politicas.md` con calma. Es la política que tu agente debe cumplir, y no todo en ella está tan claro como parece.

## 5. Restablece los datos

Las herramientas que construyas van a modificar los datos: cancelar pedidos, abrir reclamos. Para volver al estado original tienes dos opciones:

- El botón **Restablecer datos** de la aplicación.
- En la terminal: `python -m tienda.repositorio restablecer`

Los dos copian los archivos de `tienda/semilla/` sobre `tienda/datos/`. Si quieres que un caso nuevo se conserve al restablecer, agrégalo también en `tienda/semilla/`.

## 6. Corre los escenarios

Un escenario es una conversación de prueba escrita en un archivo, con lo que el agente debería hacer. El ejecutor la repite varias veces porque el modelo no responde igual siempre: un agente que acierta 2 de 5 veces no está listo.

```
python -m evaluacion.ejecutor
```

Por defecto corre cada escenario 5 veces. Para correr uno solo y menos veces:

```
python -m evaluacion.ejecutor -n 2 evaluacion/escenarios/consulta_politica.json
```

El ejecutor no revisa el texto de la respuesta. Revisa lo que el agente hizo: qué herramientas llamó, con qué argumentos y cómo quedaron los datos al final. Abre `evaluacion/escenarios/consulta_politica.json` para ver el formato. El informe queda en `evaluacion/informes/`.

Cada ejecución gasta presupuesto de tu grupo. Mientras desarrollas, corre un solo escenario con `-n 1` o `-n 2`, y deja la corrida completa para cuando quieras medir.

Ten en cuenta que el ejecutor restablece los datos antes de cada ejecución.

## 7. Corre las pruebas

Las pruebas revisan tus herramientas sin llamar al modelo, así que son rápidas y no gastan presupuesto. Úsalas para comprobar que cada validación de la política funciona.

```
python -m pytest
```

Mira `pruebas/test_ejemplo.py` para ver cómo se llama una herramienta directamente.

Cada prueba empieza con los datos restablecidos (lo hace `pruebas/conftest.py`), así que, igual que con los escenarios, los cambios que hayas hecho a mano en `tienda/datos/` se pierden al correr las pruebas.

## 8. Entrega con un pull request

Un pull request es una solicitud para integrar los cambios de una rama en la rama principal. Sirve para que otra persona revise el trabajo antes de aceptarlo. Así vas a entregar.

1. Trabaja en una rama aparte. En la terminal:
   ```
   git checkout -b entrega
   ```
2. Haz commits a medida que avances (un commit es una versión guardada de tus cambios: `git add .` y luego `git commit -m "qué cambiaste"`) y súbelos con `git push -u origin entrega` (la primera vez) o `git push` (las siguientes).
3. Cuando termines, corre la evaluación completa y las pruebas, y haz commit del informe que quedó en `evaluacion/informes/`.
4. En GitHub, abre la pestaña **Pull requests**, haz clic en **New pull request**, elige `entrega` como rama de origen y `main` como destino.
5. Llena la plantilla que aparece: el informe de escenarios, la salida de `python -m pytest` y un resumen de tus decisiones.
6. Asigna al profesor como revisor.

Junto con el código entregas `ANALISIS.md` completo. Ahí explicas cómo interpretaste la política y por qué cada regla está donde está.

## Qué te toca construir

- Las instrucciones del agente en `agente/instrucciones.md`.
- Las herramientas para consultar pedidos, registrar reclamos, cancelar pedidos, solicitar reembolsos y escalar a una persona.
- La forma de pedirle confirmación al cliente antes de una acción que no se puede deshacer.
- Las reglas de la política, validadas en el código.
- Tus escenarios de evaluación y tus pruebas.

Si algo de la base no funciona, avísame antes de cambiarlo.

Profesor
