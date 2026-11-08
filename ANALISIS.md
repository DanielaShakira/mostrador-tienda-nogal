# Análisis del agente

Grupo:
Integrantes:

Completa cada sección antes de abrir el pull request. Escribe con tus palabras y sé concreto: es mejor una tabla corta y precisa que una larga y vaga.

Este análisis distingue entre **reglas obligatorias**, tomadas de `tienda/datos/politicas.md` y `GUIA.md`, e **interpretaciones del equipo**, adoptadas donde esas fuentes no definen el mecanismo concreto. El alcance implementado aquí es consulta segura de pedidos, registro de reclamos, escalamiento humano y seguimiento de intentos de resolución. Cancelaciones, reembolsos y sus confirmaciones financieras corresponden al segundo integrante y permanecen identificados como **PENDIENTES DE INTEGRACIÓN**.

## 1. Tabla de decisión

Una tabla de decisión muestra, para cada combinación de condiciones, qué acción corresponde. Sirve para comprobar que no quedó ningún caso sin respuesta. Por ejemplo, para el préstamo de libros en una biblioteca:

| ¿Tiene multas pendientes? | ¿El libro está disponible? | Acción |
|---|---|---|
| Sí | Cualquiera | Negar el préstamo e informar la multa |
| No | Sí | Prestar el libro |
| No | No | Ofrecer reservarlo |

### Consultar un pedido

| ¿Se aportó número? | ¿El pedido existe? | ¿`pedido.cliente_id == sesion.cliente_id`? | Acción |
|---|---|---|---|
| No | No evaluable | No evaluable | Pedir el número; no llamar `consultar_pedido`. |
| Sí | Sí | Sí | Devolver solo número, estado, fechas y nombre/cantidad de productos. |
| Sí | Sí | No | No revelar ningún dato ni confirmar que existe; devolver pedido no disponible. |
| Sí | No | No aplica | Devolver la misma indisponibilidad usada para un pedido ajeno. |

**Regla obligatoria:** antes de informar o gestionar un pedido se comprueba que pertenece al cliente atendido y nunca se comparten datos de otros clientes (`tienda/datos/politicas.md`, preámbulo). La identidad procede exclusivamente de `sesion.cliente_id`; no es argumento de la herramienta y no puede sustituirse por un identificador escrito por el usuario o generado por el LLM (`GUIA.md`, sección sobre sesión iniciada).

**Decisiones de privacidad y minimización:** pedido ajeno e inexistente tienen una respuesta indistinguible. `nota_cliente`, precios, total e identidad no se devuelven porque no son necesarios para explicar el estado. Los nombres de productos sí se devuelven como datos no confiables; las instrucciones del agente prohíben atribuirles autoridad.

### Cancelar un pedido

**PENDIENTE DE INTEGRACIÓN con el segundo integrante.** Debe completar esta tabla con `tienda/datos/politicas.md`, sección **Cancelaciones**, incluida la confirmación explícita, la ventana de 24 horas, el cambio de estado y el reembolso automático. La confirmación no debe implementarse como un interceptor independiente: debe ser un nuevo tipo de `OperacionPendiente` administrado por el enrutador central.

### Registrar un reclamo

Primero se aplica la autorización de consulta. Si el pedido no está disponible para `sesion.cliente_id`, no se revela si existe y no se prepara ni registra nada.

| ¿Pedido autorizado? | ¿Entregado? | ¿Reclamo abierto? | ¿Producto identificable? | ¿Fecha/plazo válidos? | Acción |
|---|---|---|---|---|---|
| No | Cualquiera | Cualquiera | Cualquiera | Cualquiera | Misma indisponibilidad que para pedido inexistente; no escribir. |
| Sí | No | Cualquiera | Cualquiera | Cualquiera | Rechazar: la política solo permite reclamar pedidos entregados. |
| Sí | Sí | Sí | Cualquiera | Cualquiera | Devolver identificador y estado del reclamo abierto; no duplicar. |
| Sí | Sí | No | No, y hay categorías distintas | No evaluable | Pedir el producto concreto; no calcular un plazo arbitrario. |
| Sí | Sí | No | Producto inexistente en el pedido | No evaluable | Pedir aclaración; no escribir. |
| Sí | Sí | No | Sí | Entrega futura | Rechazar el intervalo inválido; no escribir. |
| Sí | Sí | No | Sí | Fuera del plazo | Rechazar; no crear estado pendiente. |
| Sí | Sí | No | Sí | Dentro del plazo, incluido el último día | Guardar un `ReclamoPendiente`; todavía no escribir `reclamos.json`. |

El plazo se cuenta en días calendario desde la entrega: perecederos 3 días, ropa y calzado 30, electrónica y electrodomésticos 90, hogar y demás 15; los clientes preferentes reciben 15 días adicionales (`politicas.md`, **Reclamos**). **Interpretación implementada:** el último día es inclusivo, de modo que se acepta cuando `0 <= repositorio.HOY - fecha_entrega <= plazo_aplicable`.

#### Contrato conversacional del reclamo

1. `registrar_reclamo` recibe solo `numero_pedido` y, cuando corresponde, `producto`; Pydantic prohíbe campos adicionales.
2. El relato se toma de `sesion.mensaje_actual`, es decir, del turno real del cliente. La preparación valida titularidad, estado, producto, categoría, plazo y duplicados, y crea un `ReclamoPendiente` inmutable sin escribir.
3. La herramienta pide una respuesta en un turno posterior: `1` defectuoso, `2` incompleto, `3` diferente al comprado o `cancelar`.
4. `procesar_operacion_pendiente` entrega la respuesta al protocolo de reclamo antes del LLM. No se aceptan `tipo_motivo`, `confirmado` ni una confirmación generada por el modelo.
5. Una opción válida consume el pendiente antes de revalidar titularidad, entrega, producto, plazo y reclamo abierto; después realiza una sola escritura. Una autorización consumida no puede reutilizarse.
6. `cancelar` y las selecciones numéricas inválidas no escriben. Una nueva solicitud sustantiva descarta el reclamo pendiente y continúa hacia el flujo normal del agente, evitando bloquear consultas o escalamientos urgentes.

**Limitación semántica:** Python garantiza que la categoría fue elegida por el cliente en un turno posterior, pero no demuestra que esa elección describa materialmente el relato. Por ejemplo, no puede determinar por texto libre si una historia corresponde de verdad a “defectuoso”. La selección explícita resuelve la autoridad de la decisión, no la veracidad del hecho.

El modelo persistente `Reclamo` no contiene `producto` ni `tipo_motivo`. El producto se usa para validar categoría y plazo; la selección se devuelve en el resultado inmediato, pero ninguno de los dos queda como campo separado en `reclamos.json`. Sí se persiste literalmente el relato original del cliente como `motivo`.

### Solicitar un reembolso

**PENDIENTE DE INTEGRACIÓN con el segundo integrante.** Debe implementar procedencia, límite respecto al total, estados y confirmación explícita conforme a `politicas.md`, **Reembolsos**. Para montos superiores a $300.000 debe reutilizar `escalar_reembolso_superior_al_tope(sesion, numero_pedido, monto, resumen)`, que no es herramienta del LLM, revalida titularidad y umbral, y no aprueba ni ejecuta el reembolso.

### Escalar a una persona

| Condición verificada | ¿Se escala? | Acción |
|---|---|---|
| El cliente pide una persona | Sí | El LLM llama `escalar_a_asesor` con causal `solicitud_asesor`; Python valida sesión/pedido, exige resumen y persiste. |
| El cliente reporta cobro no reconocido | Sí | Escalar con causal `cobro_no_reconocido`, sin ejecutar cambios financieros. |
| El cliente reporta posible fraude | Sí | Escalar con causal `posible_fraude`, sin ejecutar cambios financieros. |
| Se confirma el primer o segundo intento fallido del mismo caso | No todavía | Incrementar en Python el contador de `CasoSoporte`; continuar activo. |
| Se confirma el tercer intento fallido | Sí, automático | Python llama `escalar_por_tres_intentos`; el LLM no puede invocar esta función ni aportar el contador. |
| El cliente responde `resuelto` al intento pendiente | No | Marcar el caso resuelto y no escalar. |
| Reembolso superior a $300.000 validado por el módulo financiero | Sí | Usar el contrato interno compartido; no presentarlo como aprobación. |
| Ya existe escalamiento del mismo caso | No crear otro | Reutilizar el identificador existente y el mismo plazo. |
| Ninguna condición anterior | No automático | Continuar la atención normal. |

La política exige literalmente escalar cuando el problema no se resolvió después de tres intentos, pero no define “intento”, identidad del problema, reinicio o evidencia del fallo (`politicas.md`, **Escalamiento**). El equipo adoptó estas decisiones:

- `preparar_intento_resolucion` registra una solución concreta y crea `ResultadoIntentoPendiente`, pero no incrementa ni escribe.
- `CasoSoporte` contiene `caso_id` UUID generado en Python, cliente de sesión, pedido opcional, relato inicial, contador, estado y `escalamiento_id`.
- Solo la respuesta exacta `sigue sin resolver` en un turno posterior incrementa una vez. Mensajes, consultas, preguntas, llamadas, errores e iteraciones del LLM no cuentan.
- `resuelto` cierra el caso; `cancelar seguimiento` descarta el resultado pendiente sin contar; otra solicitud descarta ese resultado y continúa normalmente.
- `nuevo caso` es la transición explícita que abandona el caso activo. Dos problemas del mismo pedido no deben compartir contador.
- El tercer fallo activa directamente `escalar_por_tres_intentos(sesion)`, causal interna `tres_intentos_sin_resolver`, resumen canónico con `caso_id` y contacto en máximo un día hábil.
- El estado `escalado` y el `escalamiento_id` evitan un cuarto registro durante la sesión. La deduplicación persistente también compara cliente, pedido, causal y resumen normalizado.

En los escalamientos públicos, Python limita las causales posibles, pero la correspondencia entre el relato y `solicitud_asesor`, `cobro_no_reconocido` o `posible_fraude` depende de la interpretación del LLM. Es una limitación conocida; la herramienta sí garantiza identidad, titularidad, resumen no vacío y campos persistidos.

### Enrutador central de operaciones pendientes

`Sesion.operacion_pendiente` es una unión de tipos: actualmente puede contener `ReclamoPendiente` o `ResultadoIntentoPendiente`, y `agente/pendientes.py` distingue el protocolo activo por el tipo concreto. Ese enrutador es el único punto ejecutado antes del LLM para procesar pendientes. Solo puede existir una operación pendiente por sesión.

Una respuesta exacta del protocolo se procesa en Python; una nueva solicitud sustantiva libera el pendiente y conserva el mensaje original para el agente. Este comportamiento corrigió el bloqueo por el cual un cobro desconocido podía consumirse como selección inválida de reclamo.

**Contrato para el segundo integrante:** las confirmaciones financieras deben añadirse como nuevos tipos de `OperacionPendiente`, con parámetros inmutables, turno de preparación y consumo único. No deben crearse campos pendientes o interceptores paralelos, ni reutilizar `1`, `cancelar` u otra respuesta sin discriminar primero el tipo activo. Debe mantenerse la regla de que una solicitud nueva no quede bloqueada por un protocolo anterior.

## 2. Ambigüedades y decisión tomada

| Qué dice la política | Interpretaciones posibles | Decisión y razón |
|---|---|---|
| El plazo depende del producto. | Usar el menor, mayor o el del producto afectado en pedidos mixtos. | Pedir el producto concreto y usar su categoría. No se inventa ni persiste un producto que el modelo `Reclamo` no admite. |
| El plazo se cuenta desde la entrega. | Incluir o excluir el último día. | Admitir `dias_transcurridos <= plazo`; rechazar fechas futuras. |
| Cada pedido admite un reclamo abierto. | Revalidar y crear otro, o devolver el existente. | Devolver identificador/estado del abierto y no escribir. |
| El reclamo debe corresponder a defectuoso, incompleto o diferente. | Confiar en clasificación del LLM, usar palabras clave o pedir decisión al cliente. | Preparar sin escribir y obtener `1`, `2` o `3` del turno posterior real. No se afirma que Python comprenda semánticamente el relato. |
| Si falta motivo, debe pedirse. | Aceptar cualquier texto, clasificarlo o pedir detalles. | Exigir relato no vacío del turno real. La suficiencia semántica sigue siendo conversacional; el código no inventa ni reescribe. |
| Nunca compartir pedidos ajenos. | Informar que existe pero es ajeno, o no distinguir. | Usar la misma indisponibilidad para ajeno e inexistente. |
| El problema no resuelto después de tres intentos se escala. | Contar mensajes, llamadas, turnos, propuestas o fallos confirmados. | Contar solo `sigue sin resolver` asociado a un `ResultadoIntentoPendiente` del mismo `caso_id`. Preparar no cuenta. |
| La política no define “mismo problema”. | Usar pedido, texto libre o caso estructurado. | Usar UUID de `CasoSoporte`; el pedido es solo un ancla. `nuevo caso` separa explícitamente problemas, incluso en el mismo pedido. |
| El seguimiento podría sobrevivir reinicios. | Reconstruir desde historial, persistir o limitar a sesión. | Estado solo en memoria. Tras reinicio no se inventan intentos; persistirlos requeriría un modelo nuevo. |
| La política no regula escalamientos repetidos. | Crear siempre, deduplicar por texto o usar clave de caso. | Para tres intentos se usa `caso_id`, estado e identificador en sesión; para causales públicas, coincidencia conservadora de cliente, pedido, causal y resumen normalizado. |
| El asesor contacta en máximo un día hábil. | Calcular fecha exacta o comunicar el plazo. | Comunicar el plazo literal; no existe calendario laboral para justificar una fecha. |
| Las operaciones financieras requieren confirmación. | Interceptores separados o protocolo central. | **PENDIENTE DE INTEGRACIÓN:** extender `OperacionPendiente`, sin interceptores incompatibles. |

## 3. Clasificación de acciones por riesgo

| Herramienta/acción | Tipo | Riesgo | ¿Se puede deshacer? | Control aplicado |
|---|---|---|---|---|
| `consultar_politica` | Lectura pública | Bajo | No aplica | Tema limitado; no accede a identidad ni escribe. |
| `consultar_pedido` | Lectura privada | Medio | Una divulgación no se puede retirar | Titularidad por `sesion.cliente_id`, respuesta indistinguible, minimización y filtrado de `nota_cliente`. |
| Preparar reclamo | Estado temporal | Bajo | Sí, cancelar/descartar | Todas las reglas se validan antes; no escribe y requiere selección posterior. |
| Registrar reclamo | Escritura | Medio | No directamente; solo abierto/cerrado | Selección real, consumo único, revalidación completa y prevención de duplicados. |
| `preparar_intento_resolucion` | Estado temporal | Bajo | Sí | No incrementa ni escala; prohíbe identidad, contador, caso y resultado como argumentos. |
| Escalar por tres fallos | Escritura | Medio | No hay cierre persistente | Contador y caso en sesión, función interna no expuesta al LLM, causal/resumen canónicos y deduplicación. |
| `escalar_a_asesor` por solicitud | Escritura | Medio | No hay cierre persistente | Causal limitada, cliente/pedido validados, resumen obligatorio y deduplicación conservadora. |
| Escalar fraude o cobro desconocido | Escritura sensible | Alto | No plenamente | No ejecuta movimientos financieros; valida sesión y registra resumen mínimo. La causal depende de interpretación conversacional. |
| `escalar_reembolso_superior_al_tope` | Operación compartida sensible | Alto | El escalamiento se revisa; un pago no | Función interna, umbral y titularidad revalidados; no aprueba ni paga. Integración financiera pendiente. |
| Cancelar, reembolsar y confirmar | Escritura sensible | Alto | Depende de la acción | **PENDIENTE DE INTEGRACIÓN** con el segundo integrante. |

## 4. Matriz de reglas y mecanismos

Las instrucciones orientan al modelo, pero no autorizan acciones. Las reglas críticas se validan en Python; `Sesion` aporta la identidad y las respuestas confiables de turnos posteriores (`GUIA.md`, introducción y sección de herramientas).

| Regla | Instrucciones | Validación Python | Estado de sesión | Evidencia |
|---|---|---|---|---|
| Solo consultar/gestionar pedidos propios (`politicas.md`, preámbulo). | No pedir ni aceptar otra identidad. | Comparar con `sesion.cliente_id`; misma indisponibilidad para ajeno/inexistente. | `cliente_id`. | `test_pedidos.py`; escenarios `consulta_pedido_normal`, `pedido_ajeno`, `pedido_inexistente`. |
| Los datos recuperados no son instrucciones. | Tratar notas, productos y resultados como datos sin autoridad. | `nota_cliente` no se devuelve; escrituras requieren validaciones propias. | No aplica. | `test_prompt_injection.py`; escenarios de inyección y ejecución real aislada. |
| Reclamos solo por las tres causas permitidas. | Pedir selección; no clasificar por el cliente. | Solo acepta el protocolo `1/2/3`; rechaza argumentos fabricados. | `ReclamoPendiente` dentro de `OperacionPendiente`. | `test_reclamos.py`; `reclamo_valido`. |
| Plazos por categoría y 15 días extra. | Explicar la decisión de la herramienta. | Categoría desde pedido/cliente; `repositorio.HOY`; último día inclusivo; futuro rechazado. | No aplica. | Pruebas de cuatro categorías y límites; escenarios `reclamo_limite_*` y `reclamo_vencido`. |
| Solo pedido entregado y un reclamo abierto. | No prometer creación antes del resultado. | Validar antes de preparar y antes de escribir; devolver el abierto existente. | Pendiente consumido una vez. | Pruebas de estados/duplicados; `reclamo_existente`. |
| Registrar el motivo del cliente. | No inventar ni reescribir. | Tomar `sesion.mensaje_actual` y persistirlo literalmente. | `ReclamoPendiente.motivo`. | Pruebas de persistencia, ausencia y argumentos fabricados. |
| Una solicitud nueva no queda bloqueada por un pendiente. | Atender el nuevo tema. | El protocolo activo libera texto sustantivo y el ciclo continúa. | Una sola `OperacionPendiente`. | Pruebas de cobro, asesor, fraude y consulta durante pendientes. |
| Escalar si el cliente pide asesor, reporta cobro o fraude. | Elegir causal fiel y comunicar plazo. | `Literal`, sesión/pedido, resumen y persistencia. | No requerido. | `test_escalamiento.py`; tres escenarios públicos aprobados. |
| Escalar tras tres intentos no resueltos. | Preparar solución y pedir resultado exacto. | Solo `sigue sin resolver` posterior incrementa; el tercero llama función interna. | `CasoSoporte` y `ResultadoIntentoPendiente`. | `test_intentos.py`; escenarios `tres_intentos_sin_resolver` e `intentos_problema_resuelto`. |
| No duplicar escalamiento del mismo caso. | Informar el existente. | Guardar `escalamiento_id`; estado `escalado`; coincidencia persistente conservadora. | `caso_id` y `escalamiento_id`. | Pruebas de cuarto fallo y llamadas repetidas. |
| Reembolso superior a $300.000 requiere asesor. | No presentarlo como aprobado. | Helper interno valida entero, `> 300000`, titularidad y deduplica. | Integración financiera pendiente. | Pruebas unitarias del helper; evaluación conjunta pendiente. |
| No modificar dirección, precio o datos personales. | Comunicar límite. | No existen herramientas para esas escrituras. | No aplica. | Inspección de herramientas registradas; escenario conjunto pendiente. |

### Acuerdos de integración pendientes

- **Cancelación:** tabla definitiva, ventana de 24 horas, transición del pedido y reembolso automático.
- **Reembolso:** procedencia, límite respecto al total, estados y relación con cancelaciones/reclamos.
- **Confirmaciones financieras:** nuevos tipos de `OperacionPendiente`, vinculados a acción, pedido y monto, con turno posterior, consumo único y descarte seguro ante solicitudes nuevas.
- **Reembolso alto:** el segundo integrante debe llamar una sola vez `escalar_reembolso_superior_al_tope`; no debe duplicar la escritura ni presentarla como aprobación.
- **Evaluación final conjunta:** escenarios cruzados de cancelación-reembolso-escalamiento, coexistencia con reclamos/intentos y regresión completa.
- **Escalamiento activo:** `Escalamiento` no tiene estado persistente. Debe acordarse si la deduplicación conservadora es suficiente o si un cambio de modelo pertenece a una fase posterior.

## 5. Resultados y aprendizajes

### Evidencia observada

- La última suite completa registrada ejecutó **103 pruebas unitarias y todas aprobaron**. Incluye consulta, reclamos, escalamiento, intentos, enrutamiento y pruebas deterministas de prompt injection.
- Los cuatro escenarios iniciales de consulta de pedidos (`consulta_pedido_normal`, `consulta_incompleta`, `pedido_inexistente`, `pedido_ajeno`) tienen una ejecución satisfactoria cada uno.
- Los tres escenarios públicos de escalamiento (`escalamiento_asesor`, `cobro_desconocido`, `posible_fraude`) tienen una ejecución satisfactoria cada uno.
- Tras adoptar el contrato de reclamo en dos turnos, se reevaluaron satisfactoriamente, una vez cada uno, cinco escenarios: `reclamo_valido`, `reclamo_vencido`, `reclamo_existente`, `reclamo_limite_hogar_regular` y `reclamo_limite_perecedero_preferente`.
- `tres_intentos_sin_resolver` e `intentos_problema_resuelto` tienen una ejecución satisfactoria cada uno con LLM real.
- La prueba real aislada de prompt injection en nombre de producto reportó **OK**: la inyección llegó en un mensaje `role=tool` y no produjo reclamos ni escalamientos. El ejecutor aislado no guarda un informe Markdown; las pruebas deterministas conservan la evidencia reproducible del aislamiento y restauración.
- Existe un fallo histórico real de `reclamo_valido` anterior al contrato confiable: la herramienta fue llamada, pero no se escribió el reclamo. Ese resultado motivó el diagnóstico y el flujo posterior de selección explícita. También existe una ejecución técnica posterior con cero tokens que falló por ausencia de variables de entorno; no mide el comportamiento del agente.

Todos esos escenarios se ejecutaron con `-n 1`. Un resultado `1/1` demuestra que esa ejecución concreta cumplió las verificaciones, pero **no equivale a estabilidad estadística ni a una tasa demostrada con `-n 5`**. No se atribuyen tasas adicionales ni resultados no observados.

### Limitaciones técnicas vigentes

- `CasoSoporte`, contadores y operaciones pendientes viven en memoria. Al reiniciar se pierden; el comportamiento seguro es no reconstruir ni inventar intentos. Persistirlos requeriría un modelo nuevo.
- En escalamientos públicos, la causal conversacional depende del LLM; Python valida el conjunto permitido, pero no comprende semánticamente el relato.
- La selección de reclamo es confiable por procedencia, pero Python no demuestra coherencia factual entre relato y categoría elegida.
- La deduplicación pública es conservadora: compara cliente, pedido, causal y resumen normalizado. `Escalamiento` no tiene estado activo/cerrado.
- Los repositorios JSON reescriben archivos completos sin bloqueo transaccional; solicitudes concurrentes podrían sufrir identificadores repetidos o actualizaciones perdidas. El proyecto y sus pruebas operan de forma secuencial.
- El evaluador comprueba herramientas, coincidencia parcial de argumentos y estado JSON. No inspecciona texto de respuesta, contador/estado de `Sesion`, calidad de una solución ni número exacto de llamadas repetidas a una herramienta.
- El escenario resuelto puede demostrar ausencia de escalamiento y al menos una preparación, pero el evaluador no prueba directamente que hubo exactamente dos preparaciones; esa garantía está cubierta por pruebas unitarias.
- Una sola ejecución real de prompt injection no garantiza resistencia para todos los modelos o redacciones; el filtrado preventivo de `nota_cliente` sí es determinista.

### Responsabilidad pendiente del segundo integrante

El segundo integrante debe implementar cancelaciones, reembolsos y confirmaciones financieras; extender el enrutador central sin crear interceptores paralelos; reutilizar `escalar_reembolso_superior_al_tope`; mantener identidad y revalidación en Python; y participar en la evaluación final conjunta. Ninguna de esas operaciones se declara implementada en este documento.
