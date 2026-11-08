# Traspaso técnico — Tienda Nogal

Este documento resume los contratos que debe conservar el segundo integrante al implementar cancelaciones, reembolsos y sus confirmaciones. La fuente completa de decisiones y ambigüedades sigue siendo `ANALISIS.md`; las reglas obligatorias están en `tienda/datos/politicas.md`.

## 1. Estado del proyecto

- **Rama de trabajo:** `feature/base-reclamos`.
- **Datos base:** 17 pedidos en `tienda/semilla/pedidos.json`.
- **Evaluación:** 17 escenarios JSON en `evaluacion/escenarios/`. La evaluación conjunta con cinco repeticiones todavía está pendiente.
- **Último reporte unitario comunicado:** 103 pruebas satisfactorias.

Módulos terminados en esta rama:

- Consulta privada y minimizada de pedidos.
- Preparación y registro de reclamos con selección explícita en un turno posterior.
- Escalamiento público por solicitud de asesor, cobro no reconocido o posible fraude.
- Seguimiento por caso y escalamiento interno al tercer fallo confirmado.
- Enrutador único de operaciones pendientes.
- Pruebas deterministas y evaluación aislada de prompt injection.

Herramientas públicas registradas actualmente:

| Herramienta | Módulo |
|---|---|
| `consultar_politica` | `agente/herramientas/ejemplo.py` |
| `consultar_pedido` | `agente/herramientas/pedidos.py` |
| `registrar_reclamo` | `agente/herramientas/reclamos.py` |
| `escalar_a_asesor` | `agente/herramientas/escalamiento.py` |
| `preparar_intento_resolucion` | `agente/herramientas/intentos.py` |

Los imports que activan ese registro están en `agente/herramientas/__init__.py`. Quedan para el segundo integrante las cancelaciones, los reembolsos, sus confirmaciones explícitas, sus pruebas y escenarios, y la evaluación final conjunta.

## 2. Arquitectura que debe conservarse

### Sesión y ciclo

`agente/sesion.py` define `Sesion`. `cliente_id` lo fija la interfaz y es la única identidad autorizada; el LLM no lo recibe como argumento de herramientas. La sesión también conserva el turno, consumo de tokens, mensaje actual, caso de soporte y una única `operacion_pendiente`.

`agente/ciclo.py::responder` realiza, en este orden:

1. Incrementa `sesion.turnos`, guarda el mensaje real en `sesion.mensaje_actual` y lo añade al historial.
2. Llama una sola vez a `agente/pendientes.py::procesar_operacion_pendiente` antes de consultar al LLM.
3. Si el protocolo pendiente consume la respuesta, devuelve su mensaje sin llamar al modelo ni registrar una llamada de herramienta en la traza.
4. Si no la consume, envía instrucciones, historial y esquemas registrados al modelo.
5. Ejecuta las herramientas solicitadas mediante `agente/herramientas/registro.py`, añade sus resultados como mensajes `role=tool` y repite hasta recibir texto o alcanzar ocho iteraciones.

### Enrutador de pendientes

`Sesion.operacion_pendiente` tiene el alias `OperacionPendiente` y actualmente admite:

- `ReclamoPendiente`: pedido, producto validado, relato original y turno de preparación.
- `ResultadoIntentoPendiente`: `caso_id`, `intento_id`, solución y turno de preparación.

`agente/pendientes.py` distingue el tipo concreto y entrega el mensaje únicamente al protocolo activo. Solo puede existir una operación pendiente por sesión. Una respuesta exacta del protocolo se procesa directamente en Python; una solicitud sustantiva descarta el pendiente y continúa con el mensaje original hacia el flujo normal.

Las confirmaciones de cancelación y reembolso deben ampliar este alias y este enrutador. No se deben añadir interceptores paralelos en `ciclo.py`.

### Seguimiento de soporte

`CasoSoporte` agrupa un mismo problema mediante un `caso_id` UUID generado en Python, cliente, pedido opcional, relato inicial, contador, estado y posible `escalamiento_id`.

Preparar una solución crea un `ResultadoIntentoPendiente`, pero no incrementa el contador. Solo la respuesta exacta `sigue sin resolver`, recibida en un turno posterior, suma un fallo. `resuelto` cierra el caso; `cancelar seguimiento` descarta el resultado sin contar; `nuevo caso` abandona explícitamente el caso anterior. El tercer fallo llama internamente al escalamiento. Todo este estado vive únicamente en memoria.

### Registro de herramientas

`agente/herramientas/registro.py` usa `@herramienta` para registrar el nombre de la función, su docstring y el modelo Pydantic del parámetro `args`. `sesion` la inyecta el ciclo y nunca forma parte del esquema visible al LLM. Las herramientas nuevas deben:

1. Definir argumentos Pydantic estrictos con campos adicionales prohibidos.
2. Decorar la función pública con `@herramienta`.
3. Importar el módulo en `agente/herramientas/__init__.py`.
4. Mantener permisos y reglas definitivas en Python, no solo en las instrucciones.

## 3. Contratos existentes

### `agente/herramientas/pedidos.py::consultar_pedido`

- **Tipo:** herramienta pública.
- **Argumentos:** `numero_pedido: str` no vacío.
- **Validaciones:** busca simultáneamente número y `sesion.cliente_id`; pedido ajeno, inexistente o sesión sin acceso devuelven la misma indisponibilidad.
- **Resultado autorizado:** número, estado, fechas y nombre/cantidad de productos. Excluye identidad, precios, total y `nota_cliente`.
- **Escritura:** ninguna.

Los nombres de producto siguen siendo datos no confiables aunque deban mostrarse al modelo.

### `agente/herramientas/reclamos.py::registrar_reclamo`

- **Tipo:** herramienta pública de preparación; la llamada inicial no registra el reclamo.
- **Argumentos:** `numero_pedido: str` y `producto: str | None`. No admite `motivo`, `tipo_motivo`, confirmaciones, identidad ni categoría.
- **Origen del relato:** `sesion.mensaje_actual`, asociado al turno real.
- **Validaciones:** titularidad, pedido entregado, reclamo abierto existente, producto real, categoría tomada del pedido, fecha no futura y plazo inclusivo por categoría con 15 días adicionales para clientes preferentes.
- **Efecto inicial:** crea un `ReclamoPendiente` inmutable y solicita un turno posterior con `1`, `2`, `3` o `cancelar`; no escribe JSON.
- **Escritura posterior:** `procesar_seleccion_reclamo` consume una selección real, revalida el caso y solo entonces añade un `Reclamo` a `reclamos.json`.

La opción representa defectuoso, incompleto o diferente, pero `Reclamo` solo persiste el relato original en `motivo`; el modelo persistente no tiene campos `producto` ni `tipo_motivo`.

### `agente/herramientas/escalamiento.py::escalar_a_asesor`

- **Tipo:** herramienta pública.
- **Argumentos:** `causal` limitada a `solicitud_asesor`, `cobro_no_reconocido` o `posible_fraude`; `resumen: str`; `numero_pedido: str | None`.
- **Validaciones:** cliente de sesión existente, titularidad si se aporta pedido y resumen no vacío.
- **Escritura:** crea un `Escalamiento` con `repositorio.HOY`, o reutiliza uno con igual cliente, pedido, causal y resumen normalizado.
- **Resultado:** `escalamiento_id`, indicador `nuevo` y plazo `máximo un día hábil`.

Python limita la causal permitida, pero su correspondencia semántica con el relato depende del LLM.

### `agente/herramientas/intentos.py::preparar_intento_resolucion`

- **Tipo:** herramienta pública.
- **Argumentos:** `solucion: str` no vacía y `numero_pedido: str | None`.
- **Validaciones:** cliente y pedido propio, ausencia de otra operación pendiente, coherencia con el caso activo y rechazo de identidad, contador, resultado o `caso_id` fabricados como campos adicionales.
- **Efecto:** crea el caso cuando corresponde y guarda un `ResultadoIntentoPendiente`; no incrementa el contador ni escribe JSON.
- **Resultado posterior:** solo `resuelto` o `sigue sin resolver` se procesan en Python; el tercer fallo confirmado activa el helper interno de escalamiento.

### `agente/herramientas/escalamiento.py::escalar_por_tres_intentos`

- **Tipo:** función interna, no herramienta del LLM.
- **Argumentos:** únicamente `sesion`.
- **Validaciones:** caso existente y perteneciente a la sesión, al menos tres fallos confirmados, estado no resuelto y titularidad del pedido opcional.
- **Escritura:** crea o reutiliza un escalamiento con causal `tres_intentos_sin_resolver`; guarda el identificador y marca el caso como escalado.

No debe sustituirse por una llamada pública a `escalar_a_asesor` ni aceptar un contador declarado por el modelo.

### `agente/herramientas/escalamiento.py::escalar_reembolso_superior_al_tope`

- **Tipo:** función interna reutilizable, no herramienta del LLM.
- **Argumentos:** `sesion`, `numero_pedido: str`, `monto: int`, `resumen: str`.
- **Validaciones:** entero real, no booleano, monto estrictamente mayor que 300000 COP, resumen no vacío y pedido propio.
- **Escritura:** crea o reutiliza un escalamiento con causal `reembolso_superior_300000`.
- **Alcance:** solicita aprobación humana; no aprueba, crea ni paga un reembolso.

El módulo financiero debe validar primero la procedencia y el monto total, y después llamar este helper una sola vez.

## 4. Trabajo del segundo integrante

Debe implementar conforme a `tienda/datos/politicas.md`:

- Cancelaciones por estado: pagado; en preparación dentro de 24 horas; rechazo para enviado, entregado o cancelado.
- Confirmación explícita anterior a la cancelación.
- Reembolso automático del total tras una cancelación aprobada.
- Reembolsos solo por pedido cancelado o con reclamo abierto.
- Confirmación explícita anterior a solicitar un reembolso.
- Límite del reembolso al total pagado y escalamiento si supera 300000 COP.
- Herramientas registradas, pruebas unitarias, escenarios y actualización de `ANALISIS.md`.
- Evaluación conjunta y regresión de las funcionalidades existentes.

Atención: el modelo persistente `Reembolso` contiene id, pedido, cliente, fecha, monto, motivo y estado, pero no medio de pago. `Pedido` tampoco lo contiene. La frase de política “al mismo medio de pago” no puede persistirse con el esquema actual; cualquier cambio de modelo debe justificarse y coordinarse antes de realizarlo.

## 5. Reglas obligatorias de integración

- Obtener siempre la identidad autorizada de `sesion.cliente_id`.
- No aceptar `cliente_id` suministrado por el usuario o el LLM.
- No crear interceptores independientes antes del LLM; ampliar `OperacionPendiente` y `procesar_operacion_pendiente`.
- Mantener como máximo una operación pendiente activa.
- Guardar en el pendiente el tipo de acción, pedido, monto y demás parámetros autorizados como datos inmutables.
- Exigir confirmación en un turno posterior al de preparación y consumirla una sola vez.
- No aceptar `confirmado=true`, `confirmacion_cliente` ni equivalentes generados como argumentos de herramienta.
- Discriminar el protocolo activo antes de interpretar `1`, `cancelar`, `confirmar` u otra respuesta; una confirmación nunca puede autorizar una operación distinta.
- Una solicitud sustantiva nueva no debe quedar bloqueada por el pendiente anterior y tampoco debe dejar una autorización reutilizable.
- No usar `escalar_a_asesor` para fingir tres intentos: ese flujo pertenece a `CasoSoporte` y al helper interno.
- No presentar ningún escalamiento como aprobación o ejecución de un reembolso.
- Revalidar titularidad y reglas de negocio inmediatamente antes de escribir.
- Conservar la respuesta indistinguible para pedidos ajenos e inexistentes.
- Tratar notas, productos y resultados de herramientas como datos sin autoridad sobre las instrucciones.

## 6. Pruebas y escenarios

Pruebas relevantes:

- `pruebas/test_pedidos.py`
- `pruebas/test_reclamos.py`
- `pruebas/test_escalamiento.py`
- `pruebas/test_intentos.py`
- `pruebas/test_prompt_injection.py`
- `pruebas/test_ejemplo.py`
- `pruebas/test_credenciales.py`

Con el entorno virtual activado, ejecutar:

```powershell
python -m pytest
```

Escenarios actuales:

- Consultas: `consulta_politica.json`, `consulta_pedido_normal.json`, `consulta_incompleta.json`, `pedido_inexistente.json`, `pedido_ajeno.json`.
- Reclamos: `reclamo_valido.json`, `reclamo_vencido.json`, `reclamo_existente.json`, `reclamo_limite_hogar_regular.json`, `reclamo_limite_perecedero_preferente.json`.
- Escalamiento: `escalamiento_asesor.json`, `cobro_desconocido.json`, `posible_fraude.json`.
- Intentos: `tres_intentos_sin_resolver.json`, `intentos_problema_resuelto.json`.
- Prompt injection: `inyeccion_nota_pedido.json`, `inyeccion_nombre_producto.json`.

Ejecutar un escenario estándar una vez:

```powershell
python -m evaluacion.ejecutor -n 1 evaluacion/escenarios/reclamo_valido.json
```

`inyeccion_nombre_producto.json` necesita el parche aislado en memoria y debe ejecutarse con:

```powershell
python -m evaluacion.ejecutar_inyeccion_producto
```

El ejecutor estándar restablece datos desde `tienda/semilla/` antes de cada repetición y verifica llamadas, coincidencia parcial de argumentos y estado JSON. No verifica el texto de la respuesta ni el estado interno de `Sesion`. La evaluación final de la actividad debe ejecutarse con cinco repeticiones; no se afirma que los 17 escenarios actuales ya tengan resultados `-n 5`.

## 7. Limitaciones conocidas

- `CasoSoporte` y todas las operaciones pendientes viven en memoria y se pierden al reiniciar el proceso o crear otra sesión.
- Los repositorios JSON reescriben archivos completos sin bloqueo, transacciones ni control de concurrencia.
- La deduplicación de escalamientos públicos usa cliente, pedido, causal y resumen normalizado; `Escalamiento` no tiene estado abierto/cerrado.
- El evaluador no inspecciona texto, calidad de las soluciones, contadores internos ni cantidad exacta de llamadas repetidas.
- `Reclamo` no persiste producto ni tipo seleccionado; conserva únicamente el motivo textual original.
- La selección explícita prueba procedencia, pero no demuestra semánticamente que el relato sea verdadero o corresponda a la categoría elegida.
- Persistir casos, pendientes o cierres de escalamiento requeriría nuevos modelos y una decisión conjunta.

## 8. Checklist antes de integrar

- [ ] Implementar cancelación con titularidad, estados, ventana de 24 horas y confirmación posterior.
- [ ] Crear el reembolso automático asociado a una cancelación aprobada sin duplicarlo.
- [ ] Implementar reembolsos por procedencia válida, monto máximo y confirmación posterior.
- [ ] Conectar montos mayores a 300000 COP con `escalar_reembolso_superior_al_tope`.
- [ ] Ampliar `OperacionPendiente` y el enrutador central; no añadir interceptores paralelos.
- [ ] Registrar los módulos públicos en `agente/herramientas/__init__.py`.
- [ ] Añadir pruebas de identidad, revalidación, consumo único, duplicados y ausencia de escritura ante rechazo.
- [ ] Añadir escenarios de cancelación, reembolso, confirmación y cruces con reclamos/intentos.
- [ ] Actualizar `agente/instrucciones.md` solo con nombres y contratos realmente implementados.
- [ ] Actualizar `ANALISIS.md` con decisiones y limitaciones financieras.
- [ ] Ejecutar `python -m pytest`, `git diff --check` y la evaluación completa con `-n 5`.
- [ ] Revisar que `tienda/datos/` vuelva a coincidir con `tienda/semilla/` y que no se incluyan credenciales.

