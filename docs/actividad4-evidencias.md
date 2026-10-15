# Evidencias y lista de verificación — Actividad 4

Se leyó completo `session_3_4_actividad.pdf` (7 páginas). La solución extiende la actividad anterior y no atribuye requisitos de autenticación adicionales al PDF. Las decisiones no concretadas por el documento se explican en README.

## Ejecuciones reales

- Entorno: Windows, Python 3.13, dependencias instaladas exclusivamente en `env` para esta actividad.
- `python -m pip check`: **No broken requirements found.** Registro: [dependencias](evidencias/actividad4-dependencias.txt).
- Suite completa: **42 pruebas aprobadas**, sin fallos. Incluye regresión de la actividad 3. Registro: [pytest](evidencias/actividad4-pytest.txt); [JUnit](evidencias/actividad4-junit.xml).
- Se ejecutó Uvicorn en `http://127.0.0.1:8004/graphql` y se verificó mediante un cliente HTTP independiente: **7 comprobaciones correctas**. [Operaciones, expectativas y respuestas reales](evidencias/actividad4-http.json).
- `app.seed` se ejecutó dos veces en la base de trabajo: ambos resultados fueron 3 cuentas, 5 conceptos INCOME, 5 EXPENSE, 10 relaciones y 20 movimientos. Además, `test_seed_repeatable_and_graphql_data` repite la carga en una base temporal, compara ambos resultados y consulta los datos por GraphQL. [Verificación de mínimos](evidencias/actividad4-datos.txt).
- [Evidencia GraphQL completa](evidencias/graphql.json): por operación incluye caso, consulta/mutación, variables, nombres de cabeceras, resultado esperado, respuesta real y estado de la prueba. No contiene contraseñas ni tokens. Las pruebas también verifican aserciones sobre valores devueltos y almacenamiento; el estado corresponde al resultado final del caso, no solo al HTTP 200.

El aviso de deprecación de Starlette/AnyIO (`BlockingPortal`) procede de las dependencias existentes y no impidió ninguna prueba. Se conservó el conjunto de versiones instalado y compatible (`pip check`). Los comandos Linux/macOS están documentados; no se afirma haberlos ejecutado.

## Casos comprobados

| Operación / caso | Resultado esperado | Resultado obtenido | Estado |
|---|---|---|---|
| Comparación del esquema con la transcripción independiente del PDF | Mismos nombres, campos, tipos, argumentos, enums y nulabilidad; solo extensión accountBalance | Contrato validado y actividad 3 preservada | PASS |
| Crear/consultar cuentas y conceptos | Persistencia, campos opcionales y filtros por tipo/actividad | Datos correctos; filtro activo excluye filas inactivas | PASS |
| Duplicados con espacios/mayúsculas | CONFLICT; concepto del otro tipo permitido | CONFLICT y creación del tipo diferente | PASS |
| Asignación repetida | CONFLICT; UNIQUE en base de datos | Error GraphQL y restricción SQL comprobados | PASS |
| Desactivar y reasignar concepto | Ausente en consulta; rechazo de movimiento; mismo ID al reactivar | Coincide | PASS |
| Ingresos/egresos y fechas | Montos positivos; captura del actor; fecha UTC | Coincide; fecha -06:00 convertida a Z | PASS |
| Montos cero/negativos | BAD_INPUT y ausencia de escritura | Coincide | PASS |
| Cuenta/concepto inexistente, ID inválido | NOT_FOUND / BAD_INPUT | Coincide | PASS |
| Concepto no permitido o inactivo | BAD_INPUT | Coincide | PASS |
| Tipo diferente al concepto | BAD_INPUT | Coincide | PASS |
| Todas las operaciones financieras sin autenticación | UNAUTHENTICATED | Coincide | PASS |
| Consultas/mutaciones con IDs de otra empresa | FORBIDDEN y lista global aislada | Coincide; también se rechaza mezclar empresas con dos membresías | PASS |
| Usuario normal registra movimiento | capturedBy igual a su ID | Coincide | PASS |
| Cliente intenta enviar capturedBy/capturedAt | Error de validación del input | Rechazado antes del resolver | PASS |
| Consulta paginada y filtros | Orden estable; limit=0 vacío; negativos inválidos | Coincide | PASS |
| Eliminación lógica y repetición | isActive=false; excluido de consulta y saldo | Coincide | PASS |
| Precisión monetaria | 0.1 + 0.2 − 0.3 = 0; preservación de decimal largo | Igualdad exacta y typeof(amount)=text en SQLite | PASS |
| Saldo negativo | Egreso permitido sin restricción adicional | Saldo -1 | PASS |
| NaN, infinito, float, booleano y exponente excesivo | Error del escalar | Rechazados | PASS |
| Fecha sin zona o inválida | Error del escalar Time | Rechazadas | PASS |
| Fallo SQL inducido al insertar movimiento | Rollback y error público sin detalle SQL | CONFLICT, cero movimientos | PASS |
| Carga repetida | Conteos idénticos y mínimos accesibles por GraphQL | 3 / 5 / 5 / 10 / 20 | PASS |
| HTTP contra Uvicorn real | Login, datos, 3 balances y rechazo sin token | 7 comprobaciones correctas | PASS |

Para reproducir todos los casos usa los comandos del README. `pytest` regenera el JSON de GraphQL; la salida de entrega y el JUnit se generaron con:

```powershell
.\env\Scripts\python.exe -m pytest -v --tb=short -p no:cacheprovider --basetemp=tmp/actividad4-tests --junitxml=docs/evidencias/actividad4-junit.xml *> docs/evidencias/actividad4-pytest.txt
```

## Lista de verificación del PDF

| Requisito del PDF | Implementación | Evidencia |
|---|---|---|
| Día 1: cuentas (p. 1, 3–4) | Account, CreateAccountInput, createAccount, accounts | test_catalogs_filters_duplicates; contrato |
| Día 1: conceptos INCOME/EXPENSE (p. 1, 4) | Concept y sus operaciones | test_catalogs_filters_duplicates; carga |
| Relación N:M permitida (p. 1, 4–5) | AccountConcept, claves foráneas, validación de empresa | test_relation_lifecycle_constraints; aislamiento |
| Crear, consultar, asignar, consultar asociados, quitar relación (p. 1, 5) | Cuatro operaciones de catálogo y tres de relación | Pruebas de catálogo y ciclo de relación |
| 3 cuentas, 5 ingresos, 5 egresos, 10 relaciones (p. 1) | app.seed / app.verify_seed | actividad4-datos.txt; test_seed_repeatable_and_graphql_data |
| Evitar registros y relaciones duplicados (p. 1) | Claves normalizadas y UNIQUE | Pruebas de duplicados y restricción SQL |
| Pruebas GraphQL y evidencias Día 1 (p. 1) | TestClient HTTP con login real | graphql.json, pytest y ejemplos |
| Día 2: Transaction (p. 1, 6) | Modelo SQL y tipo GraphQL completo | Comparación de contrato; creación con selección de campos |
| Crear, consultar, eliminar ingresos/egresos (p. 1, 6–7) | createTransaction, transactions, deleteTransaction | Pruebas de movimientos, paginación y eliminación |
| Monto > 0 (p. 2, 7) | Validación de servicio y tipo de almacenamiento | test_invalid_amount |
| Cuenta/concepto existen y están permitidos (p. 2) | pair, owned, relation | Referencias, concepto sin relación y relación desactivada |
| Autenticación y empresa coherente (p. 2) | JWT existente y membresías activas por operación | Autenticación y aislamiento entre empresas |
| Tipo de movimiento compatible (p. 2) | Comparación con concept_type | test_invalid_references_and_type |
| Usuario responsable (p. 2, 6) | capturedBy obtenido del token; capturedByUser | Usuario normal y rechazo de suplantación |
| 20 movimientos con ambos tipos (p. 2) | Carga de 10 ingresos y 10 egresos | Carga repetida y HTTP real |
| Casos correctos y errores mediante GraphQL (p. 2) | Suite HTTP y errores públicos | graphql.json con esperado, real y estado |
| Enums, campos, escalares, inputs y firmas (p. 3–7) | schema.graphql; finance_schema.py | test_finance_pdf_contract |
| Balance = ingresos − egresos (p. 7) | accountBalance (extensión) sin paginación | Decimal largo, cancelación exacta, eliminación y HTTP |
| Integridad, errores y operaciones funcionales (evaluación, p. 2) | SQL, servicios y resolvers transaccionales | Restricciones, rollback, contrato y suite completa |
| Redacción y evidencias (evaluación, p. 2) | README y documentación en español | Archivos de entrega enlazados arriba |
| Equipo de cinco y entrega en tiempo/forma (p. 1–2) | Entrega individual a nombre de Enrique Zavala, según indicación del autor | Autor identificado en ENTREGA.md; el envío al docente no se ha realizado |

La implementación no agrega roles o requisitos de actividades anteriores: reutiliza los que ya estaban en el proyecto. El autor indicado para esta entrega individual es Enrique Zavala. La evaluación del formato individual y la fecha de entrega corresponde al docente.
