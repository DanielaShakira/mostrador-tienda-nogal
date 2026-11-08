# Análisis del agente

Grupo:
Integrantes:

Completa cada sección antes de abrir el pull request. Escribe con tus palabras y sé concreto: es mejor una tabla corta y precisa que una larga y vaga.

Este análisis distingue entre **reglas obligatorias**, tomadas de `tienda/datos/politicas.md` y `GUIA.md`, e **interpretaciones del equipo**, adoptadas para cubrir casos que esas fuentes no definen por completo. El alcance desarrollado aquí es consulta de pedidos, registro de reclamos y escalamiento humano. Cancelaciones, reembolsos, confirmaciones explícitas y el estado de sesión compartido quedan marcados como **PENDIENTES DE ACUERDO** con el compañero responsable.

## 1. Tabla de decisión

Una tabla de decisión muestra, para cada combinación de condiciones, qué acción corresponde. Sirve para comprobar que no quedó ningún caso sin respuesta. Por ejemplo, para el préstamo de libros en una biblioteca:

| ¿Tiene multas pendientes? | ¿El libro está disponible? | Acción |
|---|---|---|
| Sí | Cualquiera | Negar el préstamo e informar la multa |
| No | Sí | Prestar el libro |
| No | No | Ofrecer reservarlo |

Haz una tabla así para cada acción de tu agente (cancelar, reclamar, reembolsar, escalar). Usa las condiciones que pone la política.

### Consultar un pedido

| ¿El número corresponde a un pedido? | ¿`pedido.cliente_id == sesion.cliente_id`? | Acción |
|---|---|---|
| Sí | Sí | Devolver la información necesaria del pedido. La identidad autorizada procede de `sesion.cliente_id`, no de un identificador escrito por el usuario o generado por el modelo. |
| Sí | No | No devolver ningún dato ni confirmar si el pedido existe. Responder como pedido no disponible para la sesión. |
| No | No aplica | Responder como pedido no disponible para la sesión, sin distinguirlo del caso de un pedido ajeno. |

**Regla obligatoria:** antes de informar o gestionar un pedido se comprueba que pertenece al cliente atendido y nunca se comparten datos de otros clientes (`tienda/datos/politicas.md`, preámbulo, línea 5). La guía establece que la interfaz simula una sesión iniciada y que las herramientas conocen al cliente de esa sesión (`GUIA.md`, sección 3, línea 56). **Interpretación del equipo:** se usa una respuesta indistinguible para pedido inexistente y pedido ajeno, para no revelar la existencia de recursos de otro cliente.

### Cancelar un pedido

**PENDIENTE DE ACUERDO con el compañero responsable.** Debe completar esta tabla con las reglas de `tienda/datos/politicas.md`, sección **Cancelaciones** (líneas 24-35), incluido el requisito de confirmación explícita. También debe acordarse cómo se representa la confirmación en el estado de sesión compartido.

### Registrar un reclamo

Primero se aplica la autorización de consulta: si el pedido no está disponible para `sesion.cliente_id`, no se revela si existe y no se registra nada.

| ¿Pedido autorizado? | ¿Está entregado? | ¿Ya tiene reclamo abierto? | ¿Producto concreto identificado? | ¿Motivo suficiente? | ¿Dentro del plazo? | Acción |
|---|---|---|---|---|---|---|
| No | Cualquiera | Cualquiera | Cualquiera | Cualquiera | Cualquiera | No revelar si existe el pedido y no registrar. |
| Sí | No | Cualquiera | Cualquiera | Cualquiera | Cualquiera | No registrar: la política solo permite reclamar pedidos entregados. |
| Sí | Sí | Sí | Cualquiera | Cualquiera | Cualquiera | Informar el estado del reclamo abierto existente; no crear un duplicado. |
| Sí | Sí | No | No, y el pedido tiene productos de categorías distintas | Cualquiera | No evaluable | Pedir al cliente que identifique el producto concreto antes de calcular el plazo. |
| Sí | Sí | No | Sí, o todas las unidades relevantes comparten categoría | No | Cualquiera | Pedir el motivo o los detalles necesarios antes de registrar. |
| Sí | Sí | No | Sí, o todas las unidades relevantes comparten categoría | Sí | No | No registrar e informar que el plazo aplicable venció. |
| Sí | Sí | No | Sí, o todas las unidades relevantes comparten categoría | Sí | Sí | Crear un único reclamo abierto con pedido, cliente de sesión, fecha simulada y motivo descrito por el cliente. |

El plazo se cuenta en días calendario desde la entrega: perecederos 3 días, ropa y calzado 30, electrónica y electrodomésticos 90, hogar y demás 15; un cliente preferente recibe 15 días adicionales (`tienda/datos/politicas.md`, **Reclamos**, líneas 9-18). **Interpretación del equipo:** el último día del plazo es válido, es decir, se acepta cuando `HOY - fecha_entrega <= plazo_aplicable`. La fecha usada es `repositorio.HOY`, como exige `GUIA.md`, sección 4, línea 79.

Las demás condiciones obligatorias proceden de `tienda/datos/politicas.md`, **Reclamos**, líneas 9 y 20-22: el motivo debe corresponder a producto defectuoso, incompleto o distinto al comprado; el pedido debe estar entregado; solo puede existir un reclamo abierto por pedido; y se debe registrar el motivo del cliente. Pedir detalles cuando el motivo es insuficiente es una **interpretación conservadora**: la política obliga expresamente a preguntar cuando no hay motivo, pero no define cuánto detalle basta. No se rechazará automáticamente un relato breve que permita identificar una de las causas admitidas.

El modelo actual `Reclamo` solo contiene `numero_pedido`, no un producto. Por eso la elección del producto en pedidos mixtos sirve para validar categoría, plazo y motivo antes de guardar; no puede persistirse como campo separado sin cambiar el modelo. Cualquier cambio de ese modelo queda fuera del alcance de este documento y requeriría acuerdo.

### Solicitar un reembolso

**PENDIENTE DE ACUERDO con el compañero responsable.** Debe completar esta tabla con `tienda/datos/politicas.md`, sección **Reembolsos** (líneas 37-43), el flujo de confirmación explícita y el contrato por el cual un reembolso superior a $300.000 solicita escalamiento humano. También debe resolverse su interacción con el reembolso automático de una cancelación.

### Escalar a una persona

| Condición observada | ¿Se escala? | Acción |
|---|---|---|
| El cliente lo pide explícitamente | Sí | Registrar un resumen breve del caso e informar el plazo máximo de contacto. |
| El cliente reporta un cobro que no reconoce o posible fraude | Sí | Tratarlo como operación sensible, registrar un resumen mínimo y escalar sin intentar resolverlo mediante cambios de datos. |
| El mismo problema sigue sin resolverse después de tres intentos de resolución | Sí | Registrar el caso y su resumen. Los intentos son de resolución del problema, no iteraciones internas del LLM. |
| Se requiere aprobar un reembolso superior a $300.000 | Sí | El módulo de reembolso debe solicitar el escalamiento mediante el contrato compartido. **PENDIENTE DE ACUERDO** con el compañero. |
| Ninguna condición anterior | No automático | Continuar la atención normal. |
| Ya hay un escalamiento activo del mismo caso | No crear otro | Informar que el caso ya está escalado y reutilizar el registro existente. |

Las cuatro causas obligatorias y la obligación de registrar un resumen e informar contacto en máximo un día hábil proceden de `tienda/datos/politicas.md`, **Escalamiento**, líneas 45-54. **Interpretación del equipo:** se comunica literalmente el plazo máximo de un día hábil; no se calcula una fecha de contacto porque el repositorio no contiene calendario laboral, festivos ni horario de corte.

Evitar duplicados activos del mismo caso es una **interpretación operativa**, no una regla expresa. Presenta una limitación: el modelo `Escalamiento` no tiene campo `estado`, por lo que no permite distinguir formalmente registros activos y cerrados. La alternativa compatible con el modelo existente es considerar duplicado, durante la conversación actual, un escalamiento ya registrado para el mismo `cliente_id`, el mismo `numero_pedido` cuando exista y el mismo problema normalizado. La definición persistente de “activo” queda **PENDIENTE DE ACUERDO** si requiere ampliar el modelo.

## 2. Ambigüedades y decisión tomada

Anota los puntos de la política que admiten más de una interpretación. Para cada uno: qué dice el texto, qué interpretaciones posibles viste, cuál elegiste y por qué.

| Qué dice la política | Interpretaciones posibles | Decisión y razón |
|---|---|---|
| El plazo depende del tipo de producto. | En un pedido con categorías distintas se podría usar el plazo menor, el mayor o el del producto afectado. | **Interpretación:** pedir el producto concreto y aplicar su categoría. Es la opción que vincula el plazo al producto reclamado. El modelo `Reclamo` no persiste el producto; se usa para validar antes de guardar. |
| El plazo se cuenta en días calendario desde la entrega. | El último día podría incluirse o excluirse. | **Interpretación:** admitir el reclamo hasta el último día inclusive (`días_transcurridos <= plazo`). Es la lectura ordinaria de “tiene N días”. Se usa `repositorio.HOY`, no la fecha real, por `GUIA.md`, sección 4. |
| Cada pedido admite un único reclamo abierto; si existe, se informa su estado. | Volver a validar plazo y motivo, crear otro registro o devolver el abierto. | **Regla directa:** devolver el estado del reclamo abierto sin crear otro. Esta decisión reproduce `politicas.md`, **Reclamos**, línea 20. |
| Si el cliente no ha dado el motivo, hay que pedírselo. | Aceptar cualquier texto no vacío o pedir detalles cuando no permite entender la causa. | **Interpretación:** pedir detalles solo si no se puede identificar el producto afectado o una causa admitida. No se inventa ni completa el motivo por el cliente. |
| Nunca compartir datos de pedidos de otros clientes. | Decir “existe pero no pertenece a tu cuenta” o dar la misma respuesta que para un pedido inexistente. | **Interpretación de privacidad:** no confirmar su existencia; usar la misma respuesta de no disponibilidad. |
| La política no regula escalados repetidos. | Crear uno por llamada, reutilizar cualquiera anterior o evitar solo duplicados activos del mismo caso. | **Interpretación:** evitar duplicados activos del mismo caso. Como `Escalamiento` no tiene estado, en el modelo actual solo puede garantizarse dentro de la conversación o mediante coincidencia conservadora; ampliar el concepto de actividad queda pendiente de acuerdo. |
| Escalar si el problema no queda resuelto después de tres intentos. | Contar turnos, llamadas a herramientas, iteraciones del LLM o intentos de solución del problema. | **Interpretación:** contar intentos de resolución del mismo problema. Las iteraciones del LLM son un detalle técnico y no representan esfuerzos visibles de atención. Falta acordar cómo identificar el problema y compartir este estado en `Sesion`. |
| El asesor contactará en máximo un día hábil. | Calcular una fecha exacta o comunicar el plazo. | **Interpretación:** comunicar el plazo sin calcular fechas no justificables; no hay calendario laboral ni festivos en los modelos. |
| El escalamiento por reembolso superior a $300.000 cruza dos módulos. | El reembolso crea el escalamiento, la herramienta de escalamiento lo crea, o ambos escriben. | **PENDIENTE DE ACUERDO:** definir un único contrato para evitar dobles escrituras y asegurar que el reembolso alto no se presente como aprobado. |
| Las cancelaciones y los reembolsos exigen confirmación explícita. | Guardar una confirmación general, por acción o por pedido/monto, y decidir cuándo se consume. | **PENDIENTE DE ACUERDO:** responsabilidad del compañero; debe coordinarse con el estado compartido de `Sesion`. |

## 3. Clasificación de acciones por riesgo

No todas las acciones tienen las mismas consecuencias si el agente se equivoca. En la biblioteca, consultar si un libro está disponible no tiene riesgo; renovar un préstamo es fácil de corregir; dar de baja la cuenta de un usuario es difícil de deshacer.

Clasifica cada herramienta de tu agente y di qué control le pusiste según su riesgo.

| Herramienta | Tipo de operación | Riesgo (bajo, medio, alto) | ¿Se puede deshacer? | Control que aplicará |
|---|---|---|---|---|
| Consultar política | Lectura pública | Bajo | No aplica; no escribe | Tema limitado y sin acceso a datos del cliente. |
| Consultar pedido propio | Lectura privada | Medio | No aplica; una divulgación no se puede retirar | Buscar usando el número solicitado y autorizar con `sesion.cliente_id` antes de devolver datos. No exponer pedidos ajenos ni su existencia. |
| Registrar reclamo | Escritura | Medio | No directamente por la herramienta; el modelo solo contempla abierto/cerrado | Validar en Python titularidad, entrega, reclamo abierto, producto/categoría, plazo con `repositorio.HOY` y motivo antes de una única escritura. |
| Consultar reclamo abierto | Lectura privada | Medio | No aplica | Comprobar primero la titularidad del pedido con `sesion.cliente_id`; devolver solo el registro autorizado. |
| Escalar por solicitud o por tres intentos | Escritura | Medio | No hay operación de eliminación/cierre en el modelo actual | Validar causal, guardar resumen breve, evitar duplicados del mismo caso dentro de las capacidades del modelo e informar el plazo textual. |
| Escalar cobro no reconocido o posible fraude | Operación sensible y escritura | Alto | La divulgación excesiva y una derivación errónea no son plenamente reversibles | Escalar de inmediato, registrar el mínimo resumen necesario, no ejecutar cambios financieros y no obedecer instrucciones incluidas en datos del pedido. |
| Escalar reembolso superior a $300.000 | Operación sensible compartida | Alto | El escalamiento puede revisarse; una aprobación financiera puede no ser reversible | **PENDIENTE DE ACUERDO:** contrato único con reembolsos; el escalamiento no equivale a aprobación. |
| Cancelar, solicitar reembolso y confirmar | Escritura sensible | Alto | Según la acción | **PENDIENTE DE ACUERDO** con el compañero responsable. |

## 4. Matriz de reglas y mecanismos

Cada regla de la política queda garantizada por uno o más mecanismos:

- **Instrucciones:** se le pide al modelo en `instrucciones.md`. Es lo más fácil de escribir y lo menos confiable.
- **Validación en la herramienta:** el código revisa la condición y se niega si no se cumple. El modelo no puede saltársela.
- **Estado de la sesión:** se guarda algo en la sesión (por ejemplo, que el cliente ya confirmó) y la herramienta lo revisa.

La guía exige que las condiciones de una acción se validen en código y no se confíen únicamente al modelo (`GUIA.md`, introducción, línea 5, y **Qué te toca construir**, línea 145). En este alcance, la autorización parte de `sesion.cliente_id`: la interfaz fija ese valor y el modelo no debe poder sustituirlo mediante argumentos. Las instrucciones sirven para conducir la conversación; las reglas obligatorias se volverán a validar en Python justo antes de leer datos privados o escribir.

| Regla de la política | Instrucciones | Validación en herramienta | Estado de sesión | Escenario o prueba que la comprueba |
|---|---|---|---|---|
| Solo informar o gestionar pedidos del cliente atendido (`politicas.md`, preámbulo, línea 5). | Indicar que no revele ni confirme pedidos ajenos. | Comparar siempre `pedido.cliente_id` con `sesion.cliente_id`; devolver la misma indisponibilidad para ajeno e inexistente. | `cliente_id` es la identidad autorizada de la conversación. | **Planificada:** pedido propio, ajeno e inexistente; verificar ausencia de datos y escrituras. |
| Reclamos solo por producto defectuoso, incompleto o distinto (`politicas.md`, Reclamos, línea 9). | Pedir causa y producto afectado. | Comprobar que el relato permite identificar una causa admitida; no inventar motivo. | No requerido. | **Planificada:** cada causa válida y motivo insuficiente/no admitido. |
| Plazos por categoría y 15 días extra para preferentes (`politicas.md`, Reclamos, líneas 9-18). | Explicar el plazo aplicable. | Obtener categoría del producto y categoría del cliente desde datos; calcular días calendario con `repositorio.HOY`, incluyendo el último día. | No requerido. | **Planificada:** cuatro categorías, regular/preferente, día límite y día posterior. |
| Reclamo solo si el pedido está entregado (`politicas.md`, Reclamos, línea 20). | Explicar la restricción. | Exigir `pedido.estado == "entregado"`. | No requerido. | **Planificada:** entregado y cada estado no permitido. |
| Un único reclamo abierto por pedido (`politicas.md`, Reclamos, línea 20). | Informar el estado del existente. | Buscar reclamo abierto antes de crear; si existe, devolverlo sin escribir. | No requerido. | **Planificada:** reclamo abierto no se duplica; uno cerrado no cuenta como abierto. |
| Registrar el motivo del cliente (`politicas.md`, Reclamos, línea 22). | Pedir motivo o detalles faltantes. | Rechazar creación sin motivo suficiente y guardar el texto aportado, sin completarlo. | No requerido. | **Planificada:** motivo ausente, insuficiente y válido. |
| Escalar cuando el cliente lo pide (`politicas.md`, Escalamiento, línea 49). | Reconocer la petición y explicar el plazo. | Clasificar la causal y registrar resumen. | Puede registrar que el caso ya fue escalado para evitar repetirlo. | **Planificada:** petición explícita y repetición del mismo caso. |
| Escalar reembolso superior a $300.000 (`politicas.md`, Escalamiento, línea 50). | No presentarlo como aprobado. | **PENDIENTE DE ACUERDO:** validación y llamada desde el módulo de reembolso. | **PENDIENTE DE ACUERDO** con confirmaciones y flujo financiero. | **Planificada con el compañero:** $300.000 y $300.001, sin doble escalamiento. |
| Escalar después de tres intentos sin resolver (`politicas.md`, Escalamiento, línea 51). | Mantener el foco en el mismo problema. | Antes de escribir, verificar contador y problema asociado; no usar iteraciones del LLM. | Requiere intentos por problema. **PENDIENTE DE ACUERDO** sobre campos y reinicio. | **Planificada:** dos intentos no escalan; tercero sin resolver sí; cambio o resolución reinicia/cierra según acuerdo. |
| Escalar cobro desconocido o posible fraude (`politicas.md`, Escalamiento, línea 52). | No intentar resolver con acciones financieras. | Detectar causal y crear escalamiento con resumen mínimo. | Puede marcar el caso escalado para impedir duplicados. | **Planificada:** cobro no reconocido, fraude y repetición. |
| Registrar resumen e informar contacto en máximo un día hábil (`politicas.md`, Escalamiento, línea 54). | Comunicar el plazo literal. | Exigir un resumen no vacío antes de guardar; no calcular fecha exacta. | No requerido. | **Planificada:** persistencia del resumen; escenario conversacional para verificar el mensaje, porque el evaluador base no valida texto. |
| No modificar dirección, precios ni datos personales (`politicas.md`, Lo que no hacemos, línea 58). | Rechazar esas solicitudes. | No ofrecer herramientas de escritura para esos datos. | No requerido. | **Planificada:** solicitudes de cambio no producen escrituras. |
| Las reglas críticas se validan en código (`GUIA.md`, líneas 5 y 145). | Orienta al modelo, pero no autoriza acciones. | Cada herramienta vuelve a validar identidad y condiciones inmediatamente antes de leer o guardar. | La sesión aporta identidad y, tras acuerdo, estado conversacional. | Pruebas unitarias llamarán herramientas directamente, sin depender del comportamiento del LLM. |

### Acuerdos de integración pendientes

- **PENDIENTE DE ACUERDO — cancelación:** tabla de decisión, efecto conjunto sobre pedido y reembolso, y tratamiento de la ventana de 24 horas con un modelo que solo almacena fecha.
- **PENDIENTE DE ACUERDO — reembolso:** contrato para pedir escalamiento por montos superiores a $300.000, prevención de duplicados y distinción entre solicitado, aprobado y efectivamente pagado.
- **PENDIENTE DE ACUERDO — confirmaciones explícitas:** alcance por cliente, acción, pedido y monto; vigencia, consumo e invalidación de la confirmación.
- **PENDIENTE DE ACUERDO — estado de sesión compartido:** campos separados para confirmaciones, intentos por problema y escalamiento ya realizado; definición de cuándo se incrementan, reinician o eliminan.
- **PENDIENTE DE ACUERDO — escalamiento activo:** el modelo `Escalamiento` no tiene estado. Se debe decidir si basta la deduplicación durante la conversación o si se modifica el modelo persistente.

## 5. Resultados y aprendizajes

Todavía no se registran tasas de acierto ni resultados: este documento se completó antes de implementar y ejecutar las pruebas y los escenarios de consulta de pedidos, reclamos y escalamiento. Esta sección se actualizará únicamente con resultados observados, incluida la tasa final de escenarios, los casos que fallen y los cambios justificados por esa evidencia.

Por ahora, el análisis identifica como focos de prueba la autorización por `sesion.cliente_id`, los límites de plazo, los pedidos con productos de categorías distintas, la no duplicación de reclamos y escalamientos, el conteo de intentos por problema y el contrato de escalamiento para reembolsos altos. No se atribuye ningún resultado a esos casos hasta ejecutarlos.
