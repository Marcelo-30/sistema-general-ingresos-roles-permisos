# Evidencia de la Unidad II · Actividad 4

La secuencia se ejecutó en `http://127.0.0.1:8007/graphql` con la API y MySQL de Docker Compose. Los ID de la empresa demo fueron: Ana 1, Luis 2, María 3, José 4 y Pedro 5. Las consultas y mutaciones se hicieron en GraphiQL; el SELECT final se ejecutó directamente en MySQL.

## Capturas observadas en GraphiQL

Las capturas se mostraron durante la sesión de trabajo, pero **no están exportadas como archivos JPG en esta carpeta**: la política del navegador bloqueó la exportación local. Para una entrega que exija archivos de imagen, guarda esas capturas desde la conversación o repite los pasos de `docs/actividad4-configuracion-permisos.md` y guárdalas manualmente. Los resultados de base de datos y las pruebas sí están guardados en los archivos enlazados abajo.

| Captura | Resultado observado | Frase junto a la captura |
|---|---|---|
| 1 · Capturista inicial | `accounts.read`, `concepts.read`, `transactions.read`, `transactions.write` | CAPTURISTA puede registrar movimientos, pero no crear cuentas. |
| 2 · María antes | `createAccount` → `FORBIDDEN` | María carece de `accounts.write` por su rol. |
| 3 · José antes | `createAccount` → `FORBIDDEN` | José comparte el mismo límite del rol CAPTURISTA. |
| 4 · Ana agrega | `assignPermissionToRole` → pareja 27 activa | Ana puede configurar el rol porque tiene `roles.write`. |
| 5 · Dos cuentas | María creó la cuenta 2 y José la 3 | Una relación nueva del rol cambia a ambas personas sin editar sus usuarios. |
| 6 · Ana quita | `removePermissionFromRole` → `true` | Retirar el permiso desactiva la pareja. |
| 7–8 · Ambos revocados | María y José vuelven a recibir `FORBIDDEN` | La revocación afecta a los dos capturistas y no guarda cuentas. |
| 9 · Pedro consulta | `createTransaction` → `FORBIDDEN` | CONSULTA carece de `transactions.write`. |
| 10 · Cambio de Pedro | `assignRole` → CAPTURISTA | El rol anterior de Pedro queda inactivo y solo uno está activo. |
| 11 · Pedro capturista | Movimiento 1 por 13.37 | El nuevo rol de Pedro permite guardar el movimiento. |
| 12–14 · Luis y contador | Luis creó la cuenta 4; CONTADOR conserva `accounts.write` y carece de `roles.write` | Cambiar a Pedro no cambia la matriz del contador. |
| 15 · Consulta tras Pedro | Cuatro permisos `.read` | Pedro deja CONSULTA sin modificar su lista. |
| 16 · José cambia lista | `assignPermissionToRole` → `FORBIDDEN` | Un capturista no puede editar `role_permissions`. |
| 17 · Ana cambia lista | Pareja 28 activa, `concepts.write` en CONSULTA | El administrador sí puede modificar la lista. |
| 18–19 · Ana restaura | Eliminación lógica y CONSULTA vuelve a cuatro `.read` | El permiso temporal se retira sin borrar la fila histórica. |
| 20 · Reinicio | Cuatro roles sin duplicados | El arranque conserva los catálogos y la matriz final. |

## SELECT y comprobaciones guardados

- [SELECT final en texto](select-final.txt): 28 filas históricas, de las cuales 26 están activas. Las filas 27 y 28 están inactivas.
- [Resultado estructurado](select-final.json): roles, permisos, parejas, roles históricos de Pedro y conteos de la empresa.
- [SELECT después del reinicio](tras-reinicio.txt) y [comprobaciones después del reinicio](tras-reinicio.json): 4 roles, 10 permisos y 26 relaciones activas sin duplicación.
- [Respuestas GraphQL de la suite MySQL](../unidad2/graphql-mysql.json): incluye la prueba de la secuencia completa en una base temporal de MySQL.

La suite completa terminó con **42 pruebas aprobadas en MySQL** y una advertencia de deprecación de Starlette/AnyIO.

El SELECT final coincide con la matriz inicial al filtrar `is_active=1`. Las filas inactivas de `(CAPTURISTA, accounts.write)` y `(CONSULTA, concepts.write)` se conservan para demostrar la desactivación lógica. La base de prueba automatizada es temporal y separada de la empresa demo; las respuestas visibles de GraphiQL y el SELECT final corresponden a la empresa demo.
