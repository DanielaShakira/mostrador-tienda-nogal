# Análisis del agente de Tienda Nogal

Grupo: 5.
Integrantes: pendientes de dato del grupo.

## Alcance y fuentes

Fuente obligatoria: `tienda/datos/politicas.md`, vigente desde 2026-09-01. Requisitos de ejecución, evaluación y entrega: `GUIA.md` y actividad suministrada por el grupo. El traspaso del compañero corresponde al commit `2d90945` de `feature/base-reclamos`.

Las decisiones financieras se documentaron antes de escribir código. Esta versión describe los controles implementados en la rama `Prueba` (solicitada por Grupo 5); no confunde especificación con resultados observados del modelo. Los resultados históricos del compañero se conservan como antecedentes en `REVISION_TRASPASO.md`, no como una evaluación nueva.

La tienda usa `HOY=2026-11-02`. Para datos horarios se añadió `AHORA=2026-11-02T12:00:00-05:00`, reloj explícito de la simulación. Nunca se calculan plazos usando la fecha real del equipo.

## 1. Tablas de decisión

Estas tablas muestran qué debe hacer el agente según las condiciones de cada caso. Las filas se revisan en orden. «Cualquiera» significa que esa condición no cambia la decisión. Antes de consultar o gestionar un pedido, siempre se comprueba que pertenezca al cliente de la sesión.

### 1. Consultar pedidos

| **¿Se conoce el número del pedido?** | **¿El pedido está disponible para el cliente de la sesión?** | **Acción** |
|---|---|---|
| No | Cualquiera | Pedir el número del pedido sin adivinarlo. |
| Sí | No: el pedido no existe | Informar que no está disponible para esa sesión, sin inventar datos. |
| Sí | No: pertenece a otro cliente | Dar la misma respuesta de indisponibilidad y no mostrar información ajena. |
| Sí | Sí | Consultar el pedido y explicar su estado, fechas y productos. |

### 2. Registrar reclamos

| **¿El pedido permite presentar un reclamo?** | **¿Está completa la información del cliente?** | **Acción** |
|---|---|---|
| No: el pedido no está disponible para la sesión | Cualquiera | Informar la indisponibilidad y no registrar nada. |
| No: todavía no está entregado | Cualquiera | Explicar que solo se puede reclamar después de la entrega. |
| No: ya tiene un reclamo abierto | Cualquiera | Informar el estado del reclamo existente sin crear otro. |
| No: venció el plazo o la entrega tiene una fecha futura | Cualquiera | Rechazar el registro y explicar el motivo. |
| No se puede determinar: falta identificar el producto afectado | No | Preguntar cuál producto fue afectado para revisar su plazo. |
| Sí | No: falta describir el motivo | Pedir al cliente que cuente qué ocurrió mediante un mensaje con `motivo:`. |
| Sí | Hay motivo, pero falta elegir la causa | Preparar el reclamo y pedir una respuesta posterior: 1 defectuoso, 2 incompleto o 3 diferente. |
| Sí | Sí: hay motivo y selección válida en un turno posterior | Revisar nuevamente las condiciones y guardar un único reclamo abierto. |
| Sí | El cliente cancela, da una selección inválida o cambia de tema | No registrar el reclamo; si cambia de tema, atender la nueva solicitud. |

Los plazos desde la entrega son 3 días para perecederos, 30 para ropa y calzado, 90 para electrónica y electrodomésticos, y 15 para hogar y demás productos. Los clientes preferentes reciben 15 días adicionales. Se incluye el último día del plazo. La selección confirma la causa declarada por el cliente; el código no puede demostrar que su relato sea verdadero.

### 3. Cancelar pedidos

| **¿En qué estado está el pedido?** | **¿Se cumple el plazo y existe confirmación del cliente?** | **Acción** |
|---|---|---|
| No está disponible para la sesión | Cualquiera | Informar la indisponibilidad y no cancelar. |
| Tiene datos inválidos o una compra futura | Cualquiera | No cancelar hasta aclarar los datos. |
| Tiene devoluciones previas que impiden devolver el total una sola vez | Cualquiera | No duplicar el reembolso ni hacer una cancelación parcial. |
| Era elegible, pero cambiaron los datos antes de ejecutar | La confirmación corresponde a la preparación anterior | Descartar esa autorización y revisar si corresponde preparar de nuevo. |
| Pagado | Todavía no hay confirmación válida | Preparar la cancelación y pedir confirmación antes de cambiar los datos. |
| Pagado | Sí: confirmó en un turno posterior | Cancelar sin costo y registrar la devolución automática del total. |
| En preparación | Dentro de 24 horas, pero sin confirmación válida | Preparar la cancelación y pedir confirmación. |
| En preparación | Dentro de 24 horas y con confirmación posterior válida | Cancelar y registrar la devolución automática del total. |
| En preparación | Pasaron más de 24 horas | Rechazar la cancelación y explicar que venció el plazo. |
| En preparación | Compra de ayer sin hora confiable | No cancelar automáticamente: los datos no permiten comprobar las 24 horas. |
| Enviado | Cualquiera | No cancelar; explicar que puede rechazar la entrega o reclamar después de recibir. |
| Entregado o cancelado | Cualquiera | Informar que la cancelación no aplica y no repetir la devolución. |

Las 24 horas incluyen el límite exacto. Si solo hay fecha, una compra de hoy está dentro del mismo día y una de hace dos o más días queda fuera; una de ayer necesita hora confiable. Si la devolución total supera $300.000, se registra como solicitada y se escala al asesor; no se aprueba automáticamente.

### 4. Solicitar reembolsos

| **¿El reembolso procede y tiene saldo disponible?** | **¿El cliente confirmó y cuál es el monto acumulado?** | **Acción** |
|---|---|---|
| No se sabe: falta número o monto | Cualquiera | Pedir el dato que falta sin inventarlo. |
| No: el pedido no está disponible para la sesión | Cualquiera | Informar la indisponibilidad y no registrar devolución. |
| No: el pedido no está cancelado ni tiene reclamo abierto | Cualquiera | Rechazar por falta de una condición válida. |
| No: el monto es inválido o supera el saldo disponible | Cualquiera | Rechazar sin recortar el monto ni escalar una solicitud inválida. |
| Ya existe una solicitud pendiente para el pedido | Cualquiera | Informar que hay un trámite pendiente y no crear otro. |
| Las condiciones cambiaron después de preparar | Existe una confirmación de la preparación anterior | No ejecutar con esa autorización; pedir una nueva preparación y confirmación si corresponde. |
| Sí | Todavía no hay confirmación válida | Preparar la solicitud, mostrar el monto y pedir confirmación. |
| Sí | Confirmó y el acumulado no supera $300.000 | Registrar el reembolso aprobado después de revisar nuevamente las condiciones. |
| Sí | Confirmó y el acumulado supera $300.000 | Registrar el reembolso solicitado y escalar su aprobación a un asesor. |

El saldo disponible es el total pagado menos los reembolsos aprobados y las solicitudes pendientes. El tope se suma por pedido: $200.000 aprobados más $150.000 nuevos requieren asesor. Los montos deben ser enteros positivos en pesos. Un registro aprobado en esta aplicación no significa que ya se haya hecho un pago bancario.

### 5. Escalar a un asesor

| **¿Qué situación presenta el cliente?** | **¿Qué condición se cumple?** | **Acción** |
|---|---|---|
| El mismo caso ya fue escalado | Se identifica el registro existente | Reutilizar el registro cuando corresponda, sin duplicarlo. |
| Pide hablar con una persona o asesor | La solicitud es explícita | Escalar sin exigir primero número de pedido ni más detalles como requisito. |
| Reporta un cobro que no reconoce | Cualquiera | Escalar por cobro no reconocido sin hacer movimientos financieros. |
| Reporta un posible fraude | Cualquiera | Escalar el caso para revisión humana. |
| Solicita un reembolso válido | Está confirmado y supera el tope acumulado de $300.000 | Escalar la aprobación y dejar el reembolso solicitado, no aprobado. |
| El problema sigue sin resolver | Hay uno o dos intentos fallidos confirmados | Continuar la atención sin escalar todavía por esa causa. |
| El problema sigue sin resolver | Hay tres intentos fallidos confirmados del mismo caso | Escalar automáticamente desde el código. |
| El cliente informa que el problema se resolvió | Responde al seguimiento pendiente | Cerrar el seguimiento sin escalar por tres intentos. |
| No se presenta una causa de escalamiento | Cualquiera | Continuar la atención sin escalar automáticamente. |

Al escalar se guarda un resumen breve del caso y se informa que un asesor lo contactará en máximo un día hábil. Un mensaje, una pregunta o una llamada de herramienta no cuentan por sí solos como un intento fallido.

### 6. Dejar rastro de cada acción

| **¿Qué acción se realizó?** | **¿Se completó correctamente?** | **Acción** |
|---|---|---|
| Registrar un reclamo | Sí | Guardar el registro en `tienda/datos/reclamos.json`. |
| Solicitar o aprobar un reembolso | Sí | Guardar monto, pedido, cliente y estado en `tienda/datos/reembolsos.json`. |
| Escalar a un asesor | Sí | Guardar la causa y el resumen en `tienda/datos/escalamientos.json`. |
| Cancelar un pedido | Sí | Cambiar el estado en `pedidos.json` y guardar la devolución total en `reembolsos.json`; si es alta, guardar también el escalamiento. |
| Consultar o preparar una operación | Sí, pero no se ejecutó una acción de negocio | Mostrar el resultado o la preparación sin crear registros de reclamo, devolución o escalamiento por esa sola consulta. |
| Ejecutar una acción | No: falta información, no está permitida o no fue confirmada | No crear el registro de la acción rechazada. |
| Guardar una operación con varias escrituras | No: falló alguna escritura | Recuperar el estado anterior y no informar un éxito incompleto. |

Los escenarios revisan los archivos para comprobar que exista el registro esperado o que los datos sigan sin cambios cuando no debía ocurrir una acción.

### 7. Pedir confirmación explícita

| **¿Hay una operación preparada?** | **¿Qué respondió el cliente?** | **Acción** |
|---|---|---|
| No | Cualquiera | No ejecutar una cancelación ni un reembolso; primero preparar la operación. |
| Sí | Todavía no ha respondido | Mostrar pedido, monto y consecuencias, y pedir `confirmar <codigo>`. |
| Sí | Envía el código en el mismo turno de preparación | No ejecutar; la confirmación debe llegar en un turno posterior. |
| Sí | Envía la frase correcta en otro turno y las condiciones siguen iguales | Revisar las reglas, usar la autorización una sola vez y ejecutar. |
| Sí | Dice solamente «sí», envía un código incorrecto o desiste | No ejecutar y descartar la preparación. |
| Sí | Cambia de tema | Descartar la preparación y atender la nueva solicitud. |
| Sí, pero cambió el cliente, el pedido, el monto o las condiciones | Envía una confirmación anterior | No ejecutar con esa autorización; preparar y confirmar de nuevo si corresponde. |
| La autorización ya se utilizó | Repite el código | No repetir la acción. |

Python genera y comprueba el código antes de volver a consultar al modelo. El modelo no tiene una herramienta para confirmar ni puede autorizar enviando `confirmado=true`. Al cancelar, la confirmación informa también la devolución automática del total.

### 8. Pedir lo que falte

| **¿Qué situación se presenta?** | **¿Se puede continuar con lo disponible?** | **Acción** |
|---|---|---|
| Falta el número de pedido | No | Preguntarlo sin elegir uno por el cliente. |
| Falta el monto del reembolso | No | Pedir la cantidad en pesos sin asumir el total. |
| Falta el motivo del reclamo | No | Pedir que describa qué ocurrió con el producto mediante `motivo:`. |
| Hay productos de distintas categorías y no se identifica el afectado | No | Preguntar cuál producto presenta el problema. |
| Falta la hora confiable de una compra de ayer en preparación | No se puede comprobar el límite de 24 horas | Explicar la falta de información y no cancelar automáticamente ni inventar una hora. |
| El pedido no existe | No | Informar que no está disponible para la sesión, sin inventar datos. |
| El pedido pertenece a otra persona | No | Dar la misma respuesta de indisponibilidad sin revelar información ajena. |
| La política no permite la acción | No, aunque estén todos los datos | Abstenerse y explicar el motivo. |
| Pide cambiar dirección, precio o datos personales | No por este canal | Informar que esa gestión no está permitida. |
| Están los datos necesarios y la política permite continuar | Sí | Usar la herramienta correspondiente y pedir confirmación si la acción lo exige. |

Las instrucciones ayudan al modelo a preguntar y explicar; las herramientas rechazan argumentos incompletos y acciones prohibidas. La calidad de la respuesta también se revisa en las trazas.

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

## 5. Registro de las acciones en los datos

Cada acción que realiza el agente debe quedar guardada. No basta con que responda que hizo algo: debe existir el registro para comprobarlo después.

Los reclamos se guardan en `tienda/datos/reclamos.json`, los reembolsos en `tienda/datos/reembolsos.json` y los escalamientos en `tienda/datos/escalamientos.json`. Cada registro incluye el cliente, el pedido cuando corresponde y los datos de la gestión. Por ejemplo, un reclamo conserva el motivo descrito por el cliente; un reembolso guarda el monto y si está solicitado o aprobado; un escalamiento deja un resumen para el asesor.

Cuando se cancela un pedido, también se cambia su estado en `pedidos.json` y se registra la devolución del total. Si esa devolución supera los $300.000, queda solicitada y se guarda el escalamiento para que un asesor la apruebe. Si falla alguna de esas escrituras, se recupera el estado anterior para no dejar una cancelación a medias.

Si la acción se rechaza, falta información o todavía no hay confirmación, no se crea el registro de esa acción. Preparar una cancelación no significa que el pedido ya esté cancelado.

Los escenarios revisan estos archivos para comprobar lo que ocurrió. Buscan el registro esperado, revisan su monto o estado y también verifican que no aparezcan registros cuando la acción no debía realizarse. Esto se comprueba, por ejemplo, en los escenarios de reclamo válido, cancelación confirmada, reembolso sobre el tope y cancelación sin confirmación. Las pruebas usan copias temporales de los datos para no alterar lo que está abierto en la aplicación.

## 6. Confirmación antes de cancelar o reembolsar

Antes de cancelar o solicitar un reembolso, el cliente debe confirmar lo que desea hacer. Esta confirmación se controla en Python y no se deja a la interpretación del modelo.

Primero se prepara la operación y se muestran el pedido, el monto y las consecuencias. En ese momento no se modifican los datos. El programa genera un código y pide al cliente que responda en un mensaje posterior con `confirmar <codigo>`. En una cancelación se informa también la devolución automática del total, de modo que una sola confirmación cubra ambas consecuencias.

La respuesta se revisa antes de volver a consultar al modelo. No sirve que el modelo diga que el cliente ya confirmó ni que envíe un argumento como `confirmado=true`. Tampoco basta con responder solamente «sí». El mensaje debe contener la confirmación correspondiente a la operación que está pendiente.

Antes de ejecutar, el código vuelve a revisar que el pedido pertenezca al cliente y que se sigan cumpliendo las condiciones de la política. También comprueba que no hayan cambiado el monto ni los datos usados para preparar la operación. Si algo cambió, hay que preparar y confirmar de nuevo.

Cada confirmación se usa una sola vez. No permite repetir un reembolso ni autorizar otro pedido. Si el cliente desiste, cambia de tema o envía un código incorrecto, se descarta la preparación. Al reiniciar la sesión también hace falta una nueva preparación.

Este mecanismo está en `agente/herramientas/finanzas.py`, junto con el estado de sesión y el manejo de pendientes. Las pruebas comprueban códigos incorrectos, confirmaciones en el mismo turno, intentos de reutilización y cambios de cliente o de datos. Los escenarios de cancelación confirmada, cancelación sin confirmación y confirmación con un «sí» verifican que solo se guarde la acción cuando realmente fue autorizada.

## 7. Información faltante, pedidos inexistentes y acciones no permitidas

Cuando falta un dato, el agente debe pedirlo antes de continuar. Si el cliente no da el número de pedido, se le pregunta; si quiere un reembolso y no indica el monto, se le pide la cantidad; si quiere reclamar y no cuenta qué ocurrió, se le solicita el motivo. En un pedido con productos de categorías distintas también se pregunta cuál fue el afectado, porque de eso depende el plazo.

El modelo no debe completar esos datos por su cuenta. Las herramientas exigen los campos necesarios y rechazan las llamadas incompletas. En el caso del reclamo, una petición como «quiero reclamar» y una opción numérica no reemplazan la descripción del problema.

Si el pedido no existe, el agente no inventa su estado ni sus productos. Devuelve que el pedido no está disponible para esa sesión. Se usa la misma respuesta cuando el pedido pertenece a otra persona, para no revelar que existe una compra ajena. La identidad válida siempre sale de la sesión, no de un nombre o permiso escrito en el chat.

Cuando la política no permite actuar, el código rechaza la operación y el agente debe explicar el motivo. Por ejemplo, no se registra un reclamo vencido, no se cancela un pedido enviado y no se solicita un reembolso sin una condición válida o por encima del saldo disponible. Si ya existe un reclamo abierto, se informa su estado en lugar de crear otro. El canal tampoco tiene herramientas para cambiar direcciones, precios o datos personales.

Un reembolso válido que supera los $300.000 tiene un tratamiento distinto: no se aprueba automáticamente, pero puede quedar solicitado y pasar a un asesor después de la confirmación del cliente. Esto permite atender el caso sin saltarse el límite de autonomía.

Las instrucciones ayudan al modelo a pedir los datos y explicar la respuesta, mientras que las herramientas comprueban las reglas antes de escribir. Por eso, aunque el modelo se equivoque al interpretar una solicitud, no puede autorizar una acción que el código rechaza. La calidad de cada explicación también debe revisarse en las respuestas y las trazas.

Estos casos se cubren en los escenarios de información incompleta, motivo o monto faltante, pedido inexistente, pedido ajeno, reclamo vencido, cancelación de un enviado y reembolso no permitido. Las pruebas revisan además que los datos permanezcan sin cambios cuando corresponde rechazar la acción.

## 8. Resultados y aprendizajes

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
