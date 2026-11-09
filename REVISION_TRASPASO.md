# Revisión de TRASPASO_COMPANERO

Fuente: origin/feature/base-reclamos, commit 2d90945. Revisión: 2026-11-08, America/Bogota.

## Conclusión

La base de consulta, reclamos, escalamiento y seguimiento está implementada, pero todavía no satisface la entrega completa. Se verificaron 103 pruebas aprobadas en un worktree aislado. No se modificó código funcional ni se consumió presupuesto del modelo.

## Hallazgos que impiden declarar la entrega lista

1. **Alta: falta toda la parte financiera.** No hay herramientas de cancelación o reembolso ni protocolo financiero; tampoco escenario de reembolso sobre el tope. El helper de escalamiento por monto alto no implementa por sí mismo esa funcionalidad.
2. **Alta: el motivo no queda garantizado.** En agente/herramientas/reclamos.py::registrar_reclamo solo se exige mensaje_actual no vacío. Con «Quiero registrar un reclamo de P-1002.» seguido de «1» se crea un reclamo sin relato material del problema. Además, si un turno anterior describió el daño y el actual solo aporta el pedido, se guarda el último texto y se pierde el motivo original. El protocolo prueba selección posterior, no suficiencia semántica del relato.
3. **Alta: límite horario sin datos suficientes.** Pedido.fecha_compra es date. Tomar ayer como exactamente 24 h puede autorizar compras que superan el límite. No implementar así; la especificación conservadora y la alternativa de marca horaria están en ANALISIS.md.
4. **Alta: el helper alto no cubre el tope por pedido acumulado.** Solo acepta montos individuales mayores que 300000. La interpretación documentada por esta revisión requiere escalar también una fracción que haga superar el acumulado, evitando dividir pagos. Debe cambiarse el contrato antes de integrar.
5. **Media: evaluación de inyección incompleta en el comando estándar.** inyeccion_nombre_producto.json no contiene el ataque persistido y depende de evaluacion/ejecutar_inyeccion_producto.py. Correr el JSON con el ejecutor normal puede aprobar sin exponer al modelo a ese ataque. El especial corre una vez y no genera informe persistente con cinco repeticiones.
6. **Media: no hay evidencia final -n 5.** evaluacion/informes solo trae .gitkeep en la rama revisada. Las ejecuciones históricas -n 1 relatadas por el compañero no fueron reproducidas aquí y no cumplen por sí solas la entrega.

## Controles comprobados por inspección y pruebas existentes

Identidad desde sesión y búsqueda conjunta de titularidad; ajeno e inexistente indistinguibles; consulta minimizada; categorías/plazos inclusive último día y extra preferente; solo entregado; reclamo abierto sin duplicación; selección posterior con revalidación; escalamientos con resumen; conteo de fallos desde un protocolo de sesión; un solo enrutador de pendientes. La selección de causal pública y la suficiencia semántica del motivo siguen dependiendo parcialmente del LLM. Ninguna prueba unitaria demuestra estabilidad del modelo real.

Hay 17 escenarios y 17 pedidos de semilla, dos más que los 15 de origin/main: P-1016 y P-1017. Se cumple la cantidad de pedidos propios mínima. Faltan pruebas financieras y fortalecer las comprobaciones de texto: el evaluador actual no comprueba que explique el estado, pida datos o no invente, solo llamadas/argumentos y estado JSON.

## Preparación de entrega

ANALISIS.md conserva las decisiones del compañero y añade tablas financieras, ambigüedades, riesgos, matriz de controles propuestos y evidencia independiente. No se presenta código pendiente como implementado. Grupo e integrantes siguen sin datos aportados. Falta implementación, evaluación final, commit/PR con plantilla e informe, y enlace del PR en NPlad.


## Resolución posterior de la revisión

Los hallazgos anteriores documentan el estado del commit revisado, no fallos que se oculten en la implementación final. La rama entrega implementa ahora herramientas financieras, confirmación exacta posterior, tope acumulado, reserva de saldo, escritura consistente y recuperación. El motivo exige declaración explícita, conserva relato entre turnos y no se registra con petición genérica más opción numérica. La precisión de 24 h usa instante opcional y reloj simulado; datos de ayer sin hora no autorizan. La inyección de producto forma parte del ejecutor estándar en cada repetición y comprueba exposición. Se ampliaron pruebas y escenarios; los resultados reales finales se documentan separadamente en los informes, sin convertir el antecedente 103/103 en una tasa del modelo.


Cierre: suite local final de 175 pruebas aprobadas. Evaluación completa corregida: 150/150 (30 escenarios, cinco repeticiones), en `evaluacion/informes/informe-20261109-002259.md` y JSON adjunto. El primer informe 139/150 permanece versionado. Publicación final en `Prueba` por solicitud del Grupo 5.
