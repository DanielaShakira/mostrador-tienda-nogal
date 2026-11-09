# Análisis del agente de Tienda Nogal

Grupo: 5.
Integrantes: pendientes de dato del grupo.

## Alcance y fuentes

Fuente obligatoria: `tienda/datos/politicas.md`, vigente desde 2026-09-01. Requisitos de ejecución, evaluación y entrega: `GUIA.md` y actividad suministrada por el grupo. El traspaso del compañero corresponde al commit `2d90945` de `feature/base-reclamos`.

Las decisiones financieras se documentaron antes de escribir código. Esta versión describe los controles implementados en la rama `Prueba` (solicitada por Grupo 5); no confunde especificación con resultados observados del modelo. Los resultados históricos del compañero se conservan como antecedentes en `REVISION_TRASPASO.md`, no como una evaluación nueva.

La tienda usa `HOY=2026-11-02`. Para datos horarios se añadió `AHORA=2026-11-02T12:00:00-05:00`, reloj explícito de la simulación. Nunca se calculan plazos usando la fecha real del equipo.

## 1. Tablas de decisión

Las filas se aplican en orden. Para toda gestión privada, identidad desde `sesion.cliente_id`, titularidad antes de mostrar información y nuevamente antes de escribir. Un pedido ajeno y uno inexistente producen la misma indisponibilidad.

### Consulta

| Condición | Decisión | Escritura |
|---|---|---|
| No hay número de pedido | Pedirlo, sin adivinar. | Ninguna. |
| Pedido ajeno, inexistente o sesión sin acceso | No revelar existencia ni datos. | Ninguna. |
| Pedido propio | Devolver número, estado, fechas y nombre/cantidad de productos; explicar el estado. | Ninguna. |
| Notas o nombres contienen órdenes | Tratarlos como datos sin autoridad; no obedecerlos. | Ninguna autorizada por esos datos. |

`consultar_pedido` omite `nota_cliente`, identidad, precios y total. El nombre del producto sí llega al modelo y se prueba como entrada no confiable. La filtración de notas se evita por código; no se afirma resistencia universal a cualquier ataque textual.

### Registrar reclamo

| Condición | Decisión | Persistencia |
|---|---|---|
| Pedido no autorizado | Indisponibilidad indistinguible. | Ninguna. |
| Estado distinto de entregado | Rechazar. | Ninguna. |
| Ya tiene reclamo abierto | Mostrar id y estado del existente; no duplicar. | Ninguna nueva. |
| Producto ajeno al pedido o pedido mixto sin producto identificado | Pedir aclaración. | Ninguna. |
| Fecha de entrega futura o fuera del plazo | Abstenerse. | Ninguna. |
| Falta descripción explícita del cliente | Pedir un mensaje `motivo: <qué ocurrió>`; una solicitud genérica o `1` no registra nada. | Pendiente temporal. |
| Motivo explícito y caso elegible | Pedir selección posterior: 1 defectuoso, 2 incompleto, 3 diferente o cancelar. | Pendiente temporal. |
| Opción válida posterior, caso aún elegible | Consumir selección, revalidar y registrar relato literal. | Un reclamo abierto en `reclamos.json`. |
| Cancelar, número inválido, cambio de tema o selección en mismo turno | No registrar; el cambio de tema continúa normalmente. | Ninguna. |

Plazos calendario inclusivos desde entrega: perecedero 3 días; ropa/calzado 30; electrónica/electrodomésticos 90; hogar/demás 15. Preferente suma 15 días. Se acepta `0 <= dias <= plazo`; el día siguiente se rechaza. Un reclamo cerrado permite uno nuevo dentro del plazo; el límite es de un abierto por pedido.

El código exige que el cliente declare el motivo con `motivo:` y lo toma del mensaje real, no de argumentos generados por el LLM. Si llega antes del número puede conservarse hasta dos turnos siguientes, vinculado a cliente y pedido si fue indicado. Un motivo sin pedido explícito solo se usa para el siguiente caso que se prepara, se consume y no autoriza otro. Si no hay una descripción estructurada vigente se vuelve a pedir; no se sustituye por el número del pedido.

**Límite semántico:** Python puede garantizar procedencia, presencia y selección explícita, pero no demostrar que una descripción sea verdadera o corresponda materialmente a la causa seleccionada. No se simula esa comprensión con una lista de palabras. La suficiencia narrativa se guía mediante instrucciones y la defensa debe reconocer este límite.

### Cancelar pedido

| Condición | Decisión | Persistencia |
|---|---|---|
| Falta número o pedido no autorizado | Pedir dato o devolver indisponibilidad. | Ninguna. |
| Compra futura o datos incoherentes | Rechazar; no inventar hora. | Ninguna. |
| Enviado | No cancelar; explicar rechazo en puerta o reclamo tras recepción. | Ninguna. |
| Entregado o cancelado | No aplica; no repetir devolución. | Ninguna. |
| Pagado | Elegible sin límite de antigüedad, salvo compra futura. | Solo preparación. |
| En preparación con hora verificada, de 0 a 24 h inclusive | Elegible. | Solo preparación. |
| En preparación con hora verificada, más de 24 h | Rechazar. | Ninguna. |
| En preparación sin hora y compra de hoy | Elegible: dentro del mismo día la antigüedad es menor de 24 h. | Solo preparación. |
| En preparación sin hora, compra de ayer | No se puede verificar el límite: abstenerse hasta contar con dato confiable. | Ninguna. |
| En preparación sin hora, compra de hace dos o más días | Fuera de plazo. | Ninguna. |
| Tiene devoluciones previas o total incompatible | No duplicar el total ni hacer cancelación parcial. | Ninguna nueva. |
| Preparado, sin confirmación exacta posterior | No actuar. | Solo sesión. |
| Confirmado y total hasta $300.000 | Cancelar y crear devolución automática aprobada del total. | `pedidos.json` y `reembolsos.json`. |
| Confirmado y total mayor de $300.000 | Cancelar, solicitar devolución automática del total y escalar aprobación. | Pedido cancelado; reembolso solicitado; escalamiento con resumen. |
| Cambiaron condiciones o falla escritura | No informar éxito; consumir autorización y restaurar datos anteriores. | Rollback o recuperación del diario. |

Una sola autorización informa cancelación y devolución automática del total. El tope humano sigue aplicando aunque el trámite sea automático: por encima de $300.000 se solicita la devolución, no se aprueba ni se paga autónomamente.

### Solicitar reembolso

Se define A = suma de aprobados del pedido; S = suma de solicitudes pendientes. Saldo disponible = total pagado - A - S. Las solicitudes reservan saldo y evitan duplicados. Pesos COP enteros positivos; se rechazan booleanos, fracciones, texto numérico, cero y negativos en argumentos financieros.

| Condición | Decisión | Persistencia |
|---|---|---|
| Falta número o monto | Pedirlo; no adivinar. | Ninguna. |
| Pedido no autorizado | Indisponibilidad indistinguible. | Ninguna. |
| No cancelado y sin reclamo abierto propio | Rechazar; reclamo cerrado no habilita. | Ninguna. |
| Monto inválido o A + S + monto > total | Rechazar sin recortar ni escalar una solicitud inválida. | Ninguna. |
| Ya hay solicitud pendiente | Informar que existe trámite; no duplicar. | Ninguna nueva. |
| Procedente, con saldo y sin confirmación posterior | Mostrar acción, pedido, monto y consecuencias. | Pendiente inmutable. |
| Confirmación válida y A + monto <= $300.000 | Revalidar y aprobar el monto confirmado. | `reembolsos.json`. |
| Confirmación válida y A + monto > $300.000 | Solicitar y escalar; nunca aprobar. | Reembolso solicitado y escalamiento. |
| Código falso, otro cliente, otro pedido, reutilización o cambio de condiciones | No actuar; nueva preparación si corresponde. | Ninguna nueva. |

El control por pedido es acumulado: $200.000 aprobados más $150.000 nuevos requieren asesor. No se puede eludir dividiendo solicitudes. El helper interno de escalamiento verifica el acumulado contra movimientos persistidos; no confía en un total declarado por el modelo.

### Escalar

| Condición | Decisión | Evidencia |
|---|---|---|
| Cliente pide asesor explícitamente | Escalar. | Causal `solicitud_asesor`, resumen y cliente de sesión. |
| Reporta cobro no reconocido o posible fraude | Escalar sin movimientos financieros. | Causal correspondiente y resumen. |
| Primer o segundo fallo confirmado del mismo caso | Continuar atención. | Contador en `CasoSoporte`. |
| Tercer fallo confirmado | Escalamiento interno automático. | `tres_intentos_sin_resolver` y caso/contador en Python. |
| Cliente informa resuelto | Cerrar seguimiento sin escalar. | Estado de caso en sesión. |
| Reembolso válido que excede acumulado autónomo | Escalar para aprobación; no presentar como pago. | `reembolso_superior_300000`. |
| Mismo caso ya escalado | Reutilizar id cuando coincide clave de deduplicación. | Sin duplicado. |
| Sin causal habilitada | No escalar automáticamente. | Ninguna escritura. |

Siempre se exige resumen no vacío y se informa contacto en máximo un día hábil. No se inventa una fecha exacta sin calendario laboral. Causales conversacionales son interpretadas por el modelo; Python limita las causales y garantiza titularidad y persistencia, no comprensión universal del lenguaje.

## 2. Ambigüedades y decisiones

| Texto o vacío | Alternativas consideradas | Decisión y razón |
|---|---|---|
| Plazo por producto en pedido mixto | Menor, mayor o producto afectado | Pedir producto afectado y usar su categoría real. |
| Desde entrega, en días | Incluir o excluir último día | Inclusivo; futuro rechazado. Evita quitar un día sin base textual. |
| Motivo descrito por cliente | Cualquier mensaje, resumen del modelo o declaración real | Mensaje real explícito `motivo:`, conservado sin reescritura y selección posterior. No confundir solicitud con motivo. |
| Pedido ajeno | Revelar que existe o indisponibilidad común | Misma respuesta que inexistente para evitar enumeración. |
| 24 horas, datos solo date | Asumir medianoche o admitir incertidumbre | Se añadió instante opcional con zona y reloj simulado. Datos antiguos de ayer sin hora no autorizan. |
| Cancelar devuelve total, pero sobre $300.000 requiere asesor | Excepción financiera o solicitud automática | Cancelar y solicitar total, aprobado solo bajo tope; alto queda pendiente del asesor. |
| Hasta $300.000 por pedido | Por solicitud o acumulado | Acumulado aprobado, con reservas de solicitudes para controlar saldo. Evita fraccionamiento. |
| No exceder pagado | Cada registro o suma | Validar suma y saldo, no cada movimiento aislado. |
| Parciales no se prohíben | Solo total o parciales | Admitir parciales explícitos en solicitudes; cancelación nueva siempre devuelve total. |
| Confirmación explícita | Booleano del LLM, sí libre o protocolo real | Desafío aleatorio Python vinculado a acción/pedido/monto/cliente; turno posterior y consumo único. |
| Confirmación para cancelación y reembolso automático | Dos preguntas o autorización conjunta | Una pregunta con ambas consecuencias, evitando bucles sin perder consentimiento. |
| Mismo medio de pago | Inventar transacción real o registrar destino original | Reembolso guarda medio original, copiado de pedido si existe o marcador `original`. No se ejecutan pagos bancarios. |
| Tres intentos | Mensajes, herramientas o fallos confirmados | Solo resultado exacto `sigue sin resolver` posterior a solución preparada del mismo caso. |
| Mismo problema y reinicios | Agrupar solo por pedido o caso | UUID de caso y `nuevo caso` explícito; estado en memoria se pierde al reiniciar. |
| Un día hábil | Fecha exacta o plazo literal | Plazo literal porque no hay calendario laboral. |
| Concurrencia y múltiples JSON | Escrituras independientes o transacción | Bloqueo de sistema operativo, diario previo, reemplazo atómico y rollback. Evita cancelación sin registro financiero ante fallo. |
| Evaluación de códigos aleatorios | Código fijo o turno dinámico | `{{confirmacion_financiera}}` se sustituye por el código preparado al simular al cliente; pasa por el mismo ciclo y controles. |

## 3. Clasificación por riesgo

| Herramienta/acción | Riesgo | Reversibilidad | Control |
|---|---|---|---|
| Consultar política | Bajo | No aplica | Tema enumerado; no datos privados. |
| Consultar pedido | Medio | Divulgación irreversible | Identidad de sesión, titularidad y minimización. |
| Preparar reclamo | Bajo | Descartable | Sin escritura, relato real y protocolo posterior. |
| Registrar reclamo | Medio | No hay cierre automático por este canal | Plazo/estado/duplicado revalidados y selección consumida. |
| Preparar solución | Bajo | Descartable | No suma intentos ni escala. |
| Escalar asesor/fraude | Medio/alto por sensibilidad | No hay cierre persistente | Resumen, causal limitada, titularidad y deduplicación. |
| Confirmar tercer fallo | Medio | Estado de sesión | Fallo real posterior, caso propio y helper interno. |
| Preparar finanzas | Bajo hasta ejecución | Descartable | Datos inmutables y desafío sin escritura. |
| Cancelar y devolver | Alto | Sin reversión por herramienta | Confirmación posterior conjunta, tiempo/estado/saldo/tope y transacción. |
| Solicitar reembolso | Alto | Sin reversión por herramienta | Procedencia, monto positivo, saldo reservado, tope acumulado y aprobación humana. |

## 4. Matriz de reglas y mecanismos

Las instrucciones orientan al modelo. La autorización y las reglas deterministas se ejecutan en Python. La sesión no es un argumento público ni puede sustituirse desde el modelo.

| Regla | Instrucciones | Validación en código | Estado de sesión | Prueba/escenario |
|---|---|---|---|---|
| Solo pedidos propios | No suplantar identidad | Búsqueda conjunta y helper de sesión | cliente_id | test_pedidos, test_finanzas; pedido_ajeno, cancelacion_pedido_ajeno |
| No inventar número/monto | Pedir faltantes | Esquema obligatorio, sin valores por defecto de monto | No aplica | consulta_incompleta, reembolso_monto_faltante |
| No obedecer datos inyectados | Datos sin autoridad | Omitir nota; escrituras protegidas | Pendientes no generables por tools | test_prompt_injection; dos escenarios de inyección |
| Reclamo dentro de plazo, entregado y no duplicado | Explicar resultado | _validar_caso antes y después | ReclamoPendiente | test_reclamos; reclamo_limite_*, reclamo_vencido |
| Motivo real y explícito | Pedir `motivo:` | No acepta motivo por argumento; selección sin relato no escribe | relato_reclamo y pendiente | test_motivo_explicito; reclamo_motivo_faltante |
| Cancelación según estado/24 h | No inventar horas | _validar_cancelacion; reloj simulado | FinanzasPendientes | test_finanzas; cancelacion_limite_24h, cancelacion_rechazada_enviado |
| Confirmación anterior no saltable | No pedir una segunda pregunta | Mensaje exacto posterior fuera del LLM; desafío y consumo único | Cliente/acción/pedido/monto/turno/huella inmutables | test_finanzas, test_evaluacion_entrega; confirmacion_generica_no_autoriza |
| Devolución total automática al cancelar | Informar ambas consecuencias | Una transacción crea cambio de estado y un reembolso total | Una autorización conjunta | test_finanzas; cancelacion_confirmada |
| Reembolso procedente | No prometer aprobación | Cancelado o reclamo abierto propio | Huella de condiciones | test_finanzas; reembolso_sin_procedencia |
| No exceder total ni fraccionar tope | No recortar/dividir | Saldo A+S y umbral acumulado inclusivo | Monto autorizado | test_finanzas; reembolso_superior_pagado, reembolso_tope_exacto |
| Superior a $300.000 escala | No llamarlo aprobado | Solicitud, helper interno y resumen | Preparación informa revisión | test_finanzas; reembolso_sobre_tope |
| Escalar tercer fallo | No contar mensajes | Resultado posterior real y contador Python | CasoSoporte y ResultadoIntentoPendiente | test_intentos; tres_intentos_sin_resolver |
| Trazabilidad/consistencia | Confirmar solo persistencia | JSON, bloqueo, diario, rollback y recuperación | Autorización consumida | test_finanzas y test_evaluacion_entrega: fallos de escritura y ciclo |
| No direcciones/precios/datos personales | Comunicar límite | No hay herramientas habilitadas para cambios | No aplica | canal_no_modifica_datos |
| Evaluación reproducible sin borrar trabajo | No aplica | DATOS temporal por repetición y captura de trazas | Sesión nueva por corrida | test_evaluacion_entrega |

### Cambios al modelo base justificados

`Pedido.instante_compra` es opcional y debe tener huso horario y fecha coherente con `fecha_compra` en Bogotá; permite el límite exacto sin romper pedidos antiguos. `Pedido.medio_pago` es opcional y solo lo aporta la fuente de datos, nunca la herramienta del modelo. `Reembolso.medio_pago` conserva el destino original; `monto` persistido exige entero positivo. En la semilla P-1005 representa exactamente 24 horas, y P-1001 tiene medio de pago simulado. No se afirma integración con una pasarela.

La persistencia se amplió porque cancelar implica varias escrituras: bloqueo entre hilos/procesos y diario del estado anterior. Si una escritura falla se restaura; si se interrumpe el proceso, la siguiente lectura recupera el diario antes de exponer datos. La operación no se informa como exitosa antes de terminar. Este mecanismo está pensado para los archivos de una tienda local; no reemplaza una base de datos ni garantiza comportamiento ante daño físico del disco.

### 4.1. Dejar rastro de cada acción en los datos

**Requisito:** los reclamos deben persistirse en `reclamos.json`, los reembolsos en `reembolsos.json` y los escalamientos en `escalamientos.json`, para que los escenarios comprueben tanto la ejecución como la ausencia de una acción prohibida. Estos archivos están en `tienda/datos/`; `tienda/semilla/` es el estado inicial reproducible de la actividad.

La respuesta del modelo no constituye evidencia de una acción. Decir «registré el reclamo» no basta: debe existir el registro correspondiente. Consultar o preparar una operación tampoco equivale a ejecutarla.

| Acción ejecutada | Archivo que constituye la evidencia | Datos persistidos y comprobación |
|---|---|---|
| Registrar reclamo | `tienda/datos/reclamos.json` | Identificador, número de pedido, cliente de sesión, fecha simulada, motivo del cliente y estado abierto. `guardar_reclamos` solo se llama después de la selección real posterior y la revalidación. |
| Solicitar/aprobar reembolso | `tienda/datos/reembolsos.json` | Identificador, pedido, cliente, fecha, monto, motivo, estado solicitado/aprobado y medio de pago original. Una preparación sin confirmación no crea este registro. |
| Escalar a asesor | `tienda/datos/escalamientos.json` | Identificador, cliente, pedido si corresponde, fecha, causal y resumen del caso. Los casos repetidos pueden reutilizar un registro existente según su clave de deduplicación. |
| Cancelar pedido | `tienda/datos/pedidos.json` y `tienda/datos/reembolsos.json` | El pedido pasa a cancelado y se registra una sola devolución del total. Si supera el tope autónomo, además se guarda un escalamiento y la devolución queda solicitada. |
| Rechazar, abstenerse o esperar datos/confirmación | Ningún registro nuevo de la acción de negocio rechazada | Se conservan los datos previos. La traza puede mostrar el error o la preparación, pero no se inventa un reclamo, reembolso o escalamiento para simular que hubo éxito. Un escalamiento que sí sea procedente constituye otra acción y debe tener su propio registro. |

**Mecanismo en código:** `registrar_reclamo`/`procesar_seleccion_reclamo`, `procesar_confirmacion_financiera` y los helpers de escalamiento llaman las funciones `guardar_*` de `tienda/repositorio.py`. Las escrituras relacionadas se agrupan mediante `transaccion`: si falla el reembolso de una cancelación se restaura el estado anterior, en lugar de informar un éxito incompleto.

**Cómo lo comprueba la evaluación:** `evaluacion/ejecutor.py::verificar` lee los JSON y aplica `estado_final`. Una regla con `donde` selecciona el pedido o registro; `cantidad: 1` comprueba su existencia, `esperado` revisa valores como monto/estado y `cantidad: 0` demuestra que no se creó la acción. Cuando ya hay datos de semilla se compara con el estado esperado, no se supone que todo archivo deba quedar vacío. `sin_cambios` permite comparar el contenido completo con el inicial.

**Evidencia:** escenarios `reclamo_valido`, `cancelacion_confirmada`, `reembolso_sobre_tope`, `escalamiento_asesor`, `cancelacion_sin_confirmacion` y `cancelacion_pedido_ajeno`; pruebas en `test_reclamos.py`, `test_finanzas.py`, `test_escalamiento.py` y `test_evaluacion_entrega.py`. Las evaluaciones usan copias temporales de semilla: comprueban las escrituras sin alterar los datos abiertos en la interfaz.

### 4.2. Pedir confirmación explícita antes de cancelar o reembolsar

**Requisito:** el cliente debe autorizar explícitamente la cancelación o el reembolso antes de ejecutar, con un mecanismo que el modelo no pueda sustituir por un argumento o una afirmación.

Se implementa el siguiente protocolo en Python:

1. `cancelar_pedido` y `solicitar_reembolso` validan y **preparan**, sin cambiar los JSON de negocio.
2. La sesión guarda un `FinanzasPendientes` inmutable: cliente, tipo de acción, pedido, monto, motivo, turno de preparación, código generado por Python y huella de las condiciones relevantes.
3. Python muestra al cliente la acción, el monto y sus consecuencias y pide la frase `confirmar <codigo>`. La cancelación incluye explícitamente su devolución automática del total en una sola autorización conjunta.
4. El cliente debe enviar la frase correspondiente en un **turno posterior real**. Se normalizan mayúsculas y espacios; no se acepta un código distinto. Un `sí` genérico no autoriza.
5. `agente/pendientes.py::procesar_operacion_pendiente` entrega ese mensaje a `procesar_confirmacion_financiera` antes de consultar al LLM. La confirmación válida se procesa sin pedir al modelo que decida si hubo consentimiento.
6. Antes de escribir se comprueba la identidad y se revalidan titularidad, estado, tiempo, procedencia, saldo y tope. Si cambian las condiciones respecto de la preparación, la autorización anterior no sirve.
7. El pendiente se consume una sola vez. No puede reutilizarse para repetir la acción, cambiar pedido/monto o autorizar otra operación. Una negativa, un código falso o un cambio de tema descartan la preparación según el protocolo. Tras reinicio o cambio de cliente se necesita una preparación nueva.

**Por qué no puede autorizarlo el modelo:** el esquema público no admite `confirmado`, `confirmacion_cliente`, `codigo` ni identidad alternativa. Esos campos se rechazan como argumentos adicionales. `procesar_confirmacion_financiera` es una función interna y no está registrada como herramienta del LLM; la entrada confiable es el mensaje recibido del cliente, no texto generado por el modelo. `tool_choice` solo exige una herramienta de validación para determinadas solicitudes directas y nunca constituye confirmación.

**Evidencia:** `test_finanzas.py` cubre falta de confirmación, mismo turno, código falso, sí genérico, argumentos fabricados, identidad cambiada, condiciones modificadas, consumo único y dos sesiones intentando la misma cancelación. `test_evaluacion_entrega.py` comprueba el ciclo completo y que confirmar no produzca otra llamada al modelo. Los escenarios `cancelacion_confirmada`, `cancelacion_sin_confirmacion`, `confirmacion_generica_no_autoriza`, `reembolso_tope_exacto` y `reembolso_sobre_tope` comprueban las consecuencias persistidas.

En escenarios, `{{confirmacion_financiera}}` construye un mensaje del cliente a partir del desafío mostrado; atraviesa el mismo ciclo de producción. No es una herramienta privilegiada para omitir la autorización.

### 4.3. Pedir lo que falte, reconocer pedidos inexistentes y abstenerse

**Requisito:** ante información incompleta se pide el dato; ante un pedido que no se puede recuperar no se inventa información; si la política prohíbe la acción, el sistema no la ejecuta.

| Situación | Respuesta y comportamiento esperado | Control que impide actuar sin fundamento |
|---|---|---|
| Falta número de pedido | Pedir el número; no elegir uno de la semilla ni adivinarlo. | Campo obligatorio en las herramientas e instrucciones de aclaración. Si el modelo llama sin él, el esquema devuelve error de argumentos. |
| Falta monto de reembolso | Pedir el monto en pesos; no asumir el total ni una cantidad arbitraria. | `ArgsSolicitarReembolso.monto` es obligatorio, entero positivo y sin valor predeterminado. |
| Falta motivo del reclamo | Pedir el relato real con `motivo:`; una solicitud genérica y una opción numérica no registran nada. | Pendiente de reclamo sin motivo no se persiste; el relato no se acepta como argumento del LLM. |
| Pedido mixto sin producto afectado identificable | Preguntar cuál producto fue afectado y no escoger el plazo más conveniente. | Validación contra los productos y categorías reales del pedido. |
| Pedido inexistente | Comunicar que no está disponible para la sesión, sin inventar estado, productos ni acciones. | Búsqueda conjunta por pedido/cliente devuelve indisponibilidad y no escribe datos. |
| Pedido de otro cliente | Misma indisponibilidad y ninguna divulgación ni modificación. | Titularidad desde `sesion.cliente_id`; el mensaje del usuario no concede acceso. |
| Reclamo vencido, pedido no entregado o ya hay uno abierto | Explicar rechazo o informar el reclamo existente, según corresponda. | Estado, plazo y duplicados comprobados antes de preparar y antes de persistir. |
| Cancelación de enviado/entregado/cancelado o fuera de 24 h | Abstenerse; informar el motivo y la alternativa prevista en la política cuando corresponda. | `_validar_cancelacion`, con estado persistido y reloj simulado. Ayer sin hora confiable no autoriza. |
| Reembolso sin pedido cancelado ni reclamo abierto, o superior al saldo | Rechazar sin crear devolución, sin recortar monto ni presentar como válida una solicitud que no procede. | `_estado` valida procedencia y saldo con aprobados y solicitudes reservadas. |
| Reembolso válido sobre el tope | Abstenerse de aprobar autónomamente y tramitar la solicitud confirmada con asesor. | Estado solicitado y escalamiento; el límite no se salta fraccionando reembolsos. |
| Cambio de dirección, precio o datos personales | Comunicar que el canal no hace esa gestión. | No existen herramientas habilitadas para realizar esas modificaciones. |

**Decisión de privacidad:** inexistente y ajeno producen la misma frase de indisponibilidad. Se reconoce que no se puede recuperar un pedido autorizado y no se inventa información; no se revela al interlocutor si existe una compra ajena. Esta decisión evita que consultar números sirva para enumerar pedidos de otras personas.

**Distinción entre instrucciones y garantías:** pedir la aclaración con palabras adecuadas es comportamiento conversacional orientado por `instrucciones.md`. Python garantiza el rechazo de argumentos ausentes/invalidos y de condiciones de negocio prohibidas; no garantiza por sí solo que cada frase generada por el modelo esté bien redactada. La consulta minimizada no devuelve saldo, reclamos u hora verificada: su ausencia en ese resultado no permite afirmar que no existan. Las herramientas financieras consultan esos datos para decidir de forma autorizada.

**Evidencia:** escenarios `consulta_incompleta`, `reclamo_motivo_faltante`, `reembolso_monto_faltante`, `pedido_inexistente`, `pedido_ajeno`, `reclamo_vencido`, `cancelacion_rechazada_enviado`, `reembolso_sin_procedencia`, `reembolso_superior_pagado` y `canal_no_modifica_datos`; pruebas en `test_pedidos.py`, `test_reclamos.py`, `test_motivo_explicito.py` y `test_finanzas.py`.

El evaluador comprueba llamadas y estado final; solo comprueba fragmentos de texto si se configuran. Por eso la evidencia de no ejecución se demuestra con los JSON, mientras que la calidad de las explicaciones también se revisa en respuestas y trazas. La corrida completa documentada obtuvo 150/150 verificaciones satisfactorias y la suite posterior pasó 175 pruebas; no se presenta esto como comprensión semántica universal del modelo.

## 5. Resultados y aprendizajes

### Evidencia comprobada

- El traspaso original pasó 103 pruebas; la brecha de motivo se reprodujo antes de corregirla.
- Suite ampliada comprobada: 175 pruebas aprobadas, sin llamadas al modelo. La salida final reproducible queda en `evaluacion/informes/pytest-final.txt`.
- Hay 30 escenarios JSON con los siete casos mínimos y casos financieros adicionales. Los pedidos propios P-1016 y P-1017 permanecen en semilla: cubren fronteras de hogar regular y perecedero preferente.
- La evaluación real completa de la versión corregida obtuvo **150/150 aciertos (100%)**, cinco repeticiones de cada uno de los 30 escenarios. Evidencia: `evaluacion/informes/informe-20261109-002259.md` y su JSON. Usó 1.145.195 tokens de entrada y 30.471 de salida. Se conserva el primer informe 139/150 y la prevalidación 5/5 para mostrar la evolución, no para mezclarlos con la tasa final.

### Cómo reproducir

Desde la raíz del proyecto y con dependencias instaladas, `python -m pytest -q` no usa presupuesto ni modifica los datos de la interfaz. Para el modelo real, configurar LLM_API_KEY y LLM_BASE_URL solo en el entorno y ejecutar `python -m evaluacion.ejecutor -n 5`. Cada repetición usa una copia temporal de semilla; los informes Markdown y JSON guardan tasas, fallas, respuestas, trazas y tokens.

El escenario de inyección en nombre incluye metadatos que el ejecutor aplica en memoria en cada repetición. Verifica además que el texto atacado llegó al resultado de una herramienta, evitando un falso positivo por ausencia de exposición. La confirmación dinámica no altera la herramienta: solo construye el mensaje del cliente que conoce el desafío mostrado.

### Límites y mejoras con una semana adicional

El modelo puede interpretar mal el lenguaje o producir texto incorrecto; las invariantes de autorización y dinero no dependen de esa interpretación. Las comprobaciones de fragmentos de respuesta y revisión de trazas ayudan, pero no prueban comprensión universal ni resistencia a cualquier inyección. Los contadores y pendientes son de sesión y se pierden al reiniciar. Reclamo no persiste producto ni categoría en campos separados; conserva el relato y la selección se observa al ejecutarse. Escalamiento no tiene estado de cierre; la deduplicación conversacional depende también de resumen normalizado.

Con una semana adicional usaríamos base de datos transaccional, estado de casos persistente, calendario laboral, pruebas adversariales adicionales y una evaluación independiente del texto. El grupo debe poder explicar: por qué 24 h no equivale siempre a un día calendario; por qué el tope se acumula; cómo una cancelación alta se convierte en solicitud y no en aprobación; dónde se consume la confirmación; y cómo se recupera un fallo entre escrituras.

### Entrega

Rama `Prueba` por solicitud explícita del Grupo 5, PR hacia `main` con plantilla, informe -n 5, salida pytest y decisiones. El grupo aporta integrantes, asigna al profesor como revisor y presenta en NPlad un solo enlace al PR. La fecha límite es la de NPlad; no se inventa aquí. No se cambia main ni se fusiona el PR como parte de esta preparación.


### Primera evaluación real y correcciones

El informe `informe-20261109-000826.md` registró 139/150 (93% redondeado), con cinco repeticiones de cada uno de los 30 casos. No se reemplaza ni se presenta como 100%. Cinco fallos correspondían al escenario de pedido ajeno: el agente se abstuvo sin llamar a cancelar y el escenario exigía esa llamada. Se corrigió para aceptar abstención directa y comparar todo el contenido de pedidos, reclamos, reembolsos y escalamientos con la semilla; las pruebas unitarias mantienen la invocación adversarial directa a las herramientas.

Los otros seis fallos revelaron demoras indebidas o inferencias sobre campos que la consulta no devolvía. Se añadieron instrucciones para preparar solicitudes completas directamente, sin una pregunta previa, y para escalar asesor sin pedir más detalles como requisito. El ciclo usa `tool_choice` en la primera llamada para patrones conservadores de solicitudes directas reales: asesor; cancelación con número; reembolso con número y monto. Esta ruta decide qué herramienta debe VALIDAR, nunca autoriza una escritura ni interpreta una confirmación. Solo evalúa el mensaje del usuario, nunca texto recuperado; preguntas, citas y negaciones fuera de esos patrones conservadores permanecen con el flujo normal. Las invariantes siguen dentro de las herramientas y el enrutador único de pendientes no se duplicó.

El Grupo 5 pidió subir el trabajo en `Prueba`, aunque la actividad menciona `entrega`; se conserva la rama previa y el PR definitivo usa la rama solicitada. Los nombres de integrantes y el usuario del profesor siguen pendientes de dato humano.


### Cierre de validación y procedencia

La corrida completa inició con el código de `2bc526d` y finalizó sin fallas: 150/150. Después se añadió una corrección del cruce `nuevo caso` durante una preparación financiera, cubierta por una prueba determinista adicional, y mejoras operativas de timeout y guardado incremental para futuras evaluaciones. Estos cambios no se presentan como una nueva corrida pagada: la suite local completa posterior aprobó 175 pruebas. El informe del modelo conserva las respuestas y trazas reales de la versión que corrió. Las comprobaciones de GitHub en Linux se consultan en el PR.

La aplicación quedó comprobada por HTTP (página, JavaScript y cinco clientes, todo 200). Windows impidió al agente detener la instancia anterior iniciada desde la terminal del usuario; si sigue abierta, hace falta reiniciarla desde esa misma terminal para cargar todos los módulos nuevos. Los datos de la interfaz permanecen intactos.
