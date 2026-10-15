# Evidencias de ejecución

Actividad 3, días 1 y 2. Consulta [la salida de pytest](evidencias/pytest.txt) y [las peticiones y respuestas reales](evidencias/graphql.json).

Las pruebas envían operaciones HTTP al endpoint GraphQL con TestClient. Cada caso usa una base temporal separada. El JSON registra operación, variables, cabeceras utilizadas, resultado esperado y respuesta real. Los tokens y contraseñas se ocultan.

| Requisito del PDF | Prueba | Resultado esperado |
|---|---|---|
| Día 1: crear, consultar, actualizar y eliminar empresa | test_company_crud_filter_null_dates | Creación y consulta correctas, actualización de campos y fechas, eliminación lógica y filtro de activas |
| Día 1: validaciones básicas | test_invalid_company, test_invalid_update | Rechazar nombre vacío, correo inválido y null en campos obligatorios |
| Día 2, caso 1: crear administrador | test_admin_users_duplicates_and_transaction | Vínculo con isAdmin=true |
| Día 2, caso 2: crear usuarios | test_admin_users_duplicates_and_transaction | Usuario y vínculo con isAdmin=false creados por su administrador |
| Día 2, caso 3: correo duplicado | test_admin_users_duplicates_and_transaction | Error CONFLICT, sin crear otra cuenta |
| Día 2, caso 4: segundo administrador | test_admin_users_duplicates_and_transaction | Error CONFLICT |
| Día 2, caso 5: empresa inexistente | test_admin_users_duplicates_and_transaction | Registro rechazado: NOT_FOUND en inicialización, FORBIDDEN para administrador sin autorización en esa empresa |
| Día 2, caso 6: autenticación correcta e incorrecta | test_login_and_tokens | Token válido con credenciales correctas; UNAUTHENTICATED con incorrectas |
| Esquema de páginas 3–6 | test_contrato_exacto_del_pdf | Mismos tipos, campos, argumentos, nulabilidad y valores predeterminados |

La batería también verifica aislamiento, estados inactivos, hash privado, concurrencia y reversión de transacciones. Estas comprobaciones internas no añaden funcionalidades a la actividad.

Para repetir:

```powershell
.\.venv\Scripts\python.exe -m pytest -v | Tee-Object docs/evidencias/pytest.txt
```

La comparación del esquema usa `tests/schema_pdf.graphql`, transcrito de las páginas 3–6. Ignora únicamente el orden y las descripciones: en GraphQL un `extend type` se integra en el tipo correspondiente.

