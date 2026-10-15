# Unidad II · Actividad 4: configuración de permisos

Esta actividad continúa el mismo Sistema General de Ingresos de la actividad 3. La matriz inicial está en `app/access.py` y las relaciones se guardan en `role_permissions`. La prueba automatizada de la secuencia completa está en `tests/test_actividad4_permisos.py`.

## Preparar la empresa

Con Docker Desktop iniciado, desde la raíz del proyecto:

```powershell
# Instala requirements.txt en env si todavía no existe (véase README.md).
.\env\Scripts\python.exe -m app.init_docker
docker compose --env-file .env.docker up -d --build
$env:SETTINGS_FILE = '.env.docker'
.\env\Scripts\python.exe -m app.demo_actividad4
```

Omite `app.init_docker` si `.env.docker` ya existe. La carga crea una empresa separada con Ana (ADMINISTRADOR), Luis (CONTADOR), María y José (CAPTURISTA) y Pedro (CONSULTA). Crea además una cuenta y un concepto INCOME asociado para probar `createTransaction`. Imprime los ID y los guarda en `docs/evidencias/unidad2/actividad4-ids.json`. Las contraseñas se guardan solo en `.actividad4-credentials.json`, excluido de Git. La carga se puede repetir sin duplicar usuarios; si un rol fue cambiado deliberadamente, informa el conflicto en vez de restaurarlo.

Antes de la demostración comprueba que la matriz esté en su estado inicial. `app.demo_actividad4` conserva las revocaciones previas del catálogo global; si ya se hizo la actividad en esta base, revierte sus cambios con las mutaciones de Ana. En una base nueva, la matriz contiene 26 parejas activas.

Abre `http://127.0.0.1:8007/graphql`. En los ejemplos siguientes, sustituye los ID según `actividad4-ids.json`: `ANA`, `LUIS`, `MARIA`, `JOSE`, `PEDRO`, `COMPANY`, `CAPTURISTA`, `CONSULTA`, `CONTADOR`, `ACCOUNTS_WRITE`, `CONCEPTS_WRITE`, `ACCOUNT` y `CONCEPT`. Los ID del rol y permiso se obtienen con la primera consulta. Ejecuta cada mutación por separado y toma la captura de GraphiQL inmediatamente después de cada paso. Usa nombres de cuenta diferentes para las operaciones aceptadas.

## 1. Matriz antes del cambio

```graphql
query Inicial($actor: ID!, $capturista: ID!, $consulta: ID!, $contador: ID!) {
  roles(actorCompanyUserId: $actor) { id code }
  permissions(actorCompanyUserId: $actor) { id code }
  capturista: rolePermissions(actorCompanyUserId: $actor, roleId: $capturista) { permission { code } }
  consulta: rolePermissions(actorCompanyUserId: $actor, roleId: $consulta) { permission { code } }
  contador: rolePermissions(actorCompanyUserId: $actor, roleId: $contador) { permission { code } }
}
```

Variables: `{"actor":"ANA","capturista":"CAPTURISTA","consulta":"CONSULTA","contador":"CONTADOR"}`. Captura la lista del capturista. **Regla:** contiene `transactions.write` y carece de `accounts.write`; consulta no tiene permisos `.write` y contador sí tiene `accounts.write`, pero no `roles.write`.

## 2. Dos rechazos y dos cuentas aceptadas

```graphql
mutation Cuenta($actor: ID!, $company: ID!, $name: String!) {
  createAccount(actorCompanyUserId: $actor,
    input: {companyId: $company, accountType: CASH, name: $name}) {
    id name companyId
  }
}
```

Primero ejecuta con `actor=MARIA`, `name="Cuenta María antes"`; luego con `actor=JOSE`, `name="Cuenta José antes"`. Cada respuesta debe contener `FORBIDDEN`. Captura ambos resultados. **Regla:** el capturista carece de `accounts.write` y un rechazo no inserta una cuenta.

## 3. Ana agrega `accounts.write` al rol

```graphql
mutation Agregar($actor: ID!, $role: ID!, $permission: ID!) {
  assignPermissionToRole(actorCompanyUserId: $actor,
    input: {roleId: $role, permissionId: $permission}) {
    id isActive role { code } permission { code }
  }
}
```

Usa `actor=ANA`, `role=CAPTURISTA`, `permission=ACCOUNTS_WRITE`. Captura el `id` de la pareja. **Regla:** Ana puede modificar `role_permissions` porque su rol tiene `roles.write`.

Repite la mutación **Cuenta** con `actor=MARIA`, `name="Cuenta María después"` y con `actor=JOSE`, `name="Cuenta José después"`. Captura ambos ID devueltos. **Regla:** una sola relación activa en el rol cambia los permisos de María y José sin editar sus usuarios.

## 4. Ana retira el permiso

```graphql
mutation Quitar($actor: ID!, $role: ID!, $permission: ID!) {
  removePermissionFromRole(actorCompanyUserId: $actor,
    roleId: $role, permissionId: $permission)
}
```

Usa `actor=ANA`, `role=CAPTURISTA`, `permission=ACCOUNTS_WRITE`. Repite **Cuenta** con María y José y nombres nuevos. Ambos deben recibir `FORBIDDEN`. Consulta en MySQL:

```sql
SELECT rp.id, r.code AS rol, p.code AS permiso, rp.is_active
FROM role_permissions rp
JOIN roles r ON r.id = rp.role_id
JOIN permissions p ON p.id = rp.permission_id
WHERE r.code = 'CAPTURISTA' AND p.code = 'accounts.write';
```

La fila debe conservar el mismo `id` y `is_active=0`. Captura el SELECT y los rechazos. **Regla:** retirar un permiso desactiva la pareja, no la borra, y afecta a ambos capturistas.

## 5. Pedro cambia de puesto

```graphql
mutation Movimiento($actor: ID!, $account: ID!, $concept: ID!) {
  createTransaction(actorCompanyUserId: $actor,
    input: {accountId: $account, conceptId: $concept,
      transactionType: INCOME, amount: "13.37"}) {
    id amount capturedBy
  }
}
```

Con `actor=PEDRO` y la cuenta y concepto de la carga, debe responder `FORBIDDEN`. Comprueba que `SELECT COUNT(*) FROM transactions` no creció. Después:

```graphql
mutation Puesto($actor: ID!, $person: ID!, $role: ID!) {
  assignRole(actorCompanyUserId: $actor,
    input: {companyUserId: $person, roleId: $role}) {
    id isActive role { code } companyUser { id }
  }
}
```

Usa `actor=ANA`, `person=PEDRO`, `role=CAPTURISTA`. Repite **Movimiento** con Pedro: ahora debe devolver un ID. Captura el rechazo y la aceptación. **Regla:** `assignRole` cambia el permiso efectivo de Pedro y solo la operación autorizada guarda un movimiento.

En MySQL, verifica las filas de Pedro (sustituye su ID):

```sql
SELECT cur.id, r.code AS rol, cur.is_active
FROM company_user_roles cur JOIN roles r ON r.id = cur.role_id
WHERE cur.company_user_id = PEDRO ORDER BY cur.id;
```

Debe haber un solo rol activo: CAPTURISTA; CONSULTA queda inactivo. Vuelve a consultar **Inicial**: la lista de CONTADOR y la de CONSULTA son iguales a las de antes. Luis aún puede usar **Cuenta**. Captura la lista del contador. **Regla:** cambiar el puesto de una persona no altera la matriz de los otros roles.

## 6. José no cambia la matriz; Ana sí

Ejecuta **Agregar** con `actor=JOSE`, `role=CONSULTA`, `permission=CONCEPTS_WRITE`. Debe recibir `FORBIDDEN`; confirma con un SELECT que no hay pareja activa. Captura el rechazo. **Regla:** cambiar la lista requiere `roles.write`.

Ejecuta la misma operación con `actor=ANA`: debe aceptarse. Captura la respuesta. **Regla:** el administrador sí puede configurar la lista. Ejecuta **Quitar** con Ana para la misma pareja y confirma que CONSULTA vuelve a tener únicamente permisos `.read`.

## 7. SELECT final y reinicio

Ejecuta `docs/comprobacion-mysql.sql`. El SELECT de `role_permissions` mostrará las 26 relaciones iniciales activas y dos filas históricas inactivas: `(CAPTURISTA, accounts.write)` y `(CONSULTA, concepts.write)`. La matriz **activa** vuelve a coincidir con la tabla de `README.md`; las dos filas inactivas demuestran la eliminación lógica. Guarda el resultado junto a las capturas.

```powershell
docker compose --env-file .env.docker restart api
$env:TEST_MYSQL = '1'
.\env\Scripts\python.exe -m pytest tests/test_actividad4_permisos.py -q
```

Después del reinicio consulta de nuevo **Inicial** y `SELECT COUNT(*)` en `roles` y `permissions`: deben seguir siendo 4 y 10. La prueba automatizada usa una base temporal y recorre todos los pasos, incluidos los conteos antes y después de los rechazos, los dos registros inactivos y el reinicio idempotente. Su resultado detallado se guarda en `docs/evidencias/unidad2/graphql-mysql.json`. Las capturas deben hacerse sobre el servidor real; no se sustituyen por la prueba automatizada.
