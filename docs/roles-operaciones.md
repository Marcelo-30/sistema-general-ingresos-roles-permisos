# Operaciones GraphQL reproducibles — Unidad II

Abre `/graphql` y copia la operación en Query y el JSON en Variables. Los IDs corresponden a la ejecución documentada; usa los valores que imprima `app.demo_roles` en tu instalación. Los catálogos y las mutaciones protegidas reciben actorCompanyUserId como argumento; los inputs mantienen los campos del PDF.

La membresía 4 se devolvió explícitamente a CAPTURISTA después de capturar el ascenso a CONTADOR. El script de carga no restaura permisos retirados ni reemplaza roles que ya fueron cambiados.

Las operaciones de creación de empresa/administrador inicial conservan X-Bootstrap-Key. Las operaciones siguientes prueban la identidad académica sin depender del token. No publiques claves, contraseñas ni respuestas de login sin ocultar el token.

## roles-permisos

Consultar los catálogos globales; requiere roles.read.

```graphql
query ($actor: ID!) {
  roles(actorCompanyUserId: $actor) {
    id
    code
    name
    description
    isActive
  }
  permissions(actorCompanyUserId: $actor) {
    id
    code
    name
    description
    isActive
  }
}
```

```json
{
  "actor": "2"
}
```

## matriz-capturista

CAPTURISTA contiene transactions.write y no accounts.write. Para CONSULTA usa role=4.

```graphql
query ($actor: ID!, $role: ID!) {
  rolePermissions(actorCompanyUserId: $actor, roleId: $role) {
    id
    isActive
    role {
      code
    }
    permission {
      id
      code
      isActive
    }
  }
}
```

```json
{
  "actor": "2",
  "role": "3"
}
```

## crear-rol

Requiere roles.write; el código es único.

```graphql
mutation ($actor: ID!, $input: CreateRoleInput!) {
  createRole(actorCompanyUserId: $actor, input: $input) {
    id
    code
    name
    description
    isActive
  }
}
```

```json
{
  "actor": "2",
  "input": {
    "code": "AUDITOR",
    "name": "Auditor",
    "description": "Rol personalizado de ejemplo"
  }
}
```

## desactivar-rol

Usa el ID del rol creado. Debe carecer de membresías activas; no se elimina la fila.

```graphql
mutation ($actor: ID!, $id: ID!) {
  deactivateRole(actorCompanyUserId: $actor, id: $id) {
    id
    isActive
  }
}
```

```json
{
  "actor": "2",
  "id": "5"
}
```

## crear-permiso

Ejemplo de ampliación del catálogo. La carga inicial sigue siendo exactamente de diez permisos.

```graphql
mutation ($actor: ID!, $input: CreatePermissionInput!) {
  createPermission(actorCompanyUserId: $actor, input: $input) {
    id
    code
    name
    description
    isActive
  }
}
```

```json
{
  "actor": "2",
  "input": {
    "code": "audit.read",
    "name": "Leer auditoría",
    "description": null
  }
}
```

## asignar-permiso

Ejemplo: autorizar accounts.write al capturista. Modifica la matriz global; repetir una pareja activa produce CONFLICT.

```graphql
mutation ($actor: ID!, $input: AssignPermissionToRoleInput!) {
  assignPermissionToRole(actorCompanyUserId: $actor, input: $input) {
    id
    isActive
    role {
      code
    }
    permission {
      code
    }
  }
}
```

```json
{
  "actor": "2",
  "input": {
    "roleId": "3",
    "permissionId": "4"
  }
}
```

## quitar-permiso

Retira el permiso del ejemplo anterior y recupera la matriz inicial. El reinicio no lo reactiva.

```graphql
mutation ($actor: ID!, $role: ID!, $permission: ID!) {
  removePermissionFromRole(
    actorCompanyUserId: $actor
    roleId: $role
    permissionId: $permission
  )
}
```

```json
{
  "actor": "2",
  "role": "3",
  "permission": "4"
}
```

## asignar-rol

Convierte la membresía capturista en contador. Para volver a CAPTURISTA usa roleId=3.

```graphql
mutation ($actor: ID!, $input: AssignRoleInput!) {
  assignRole(actorCompanyUserId: $actor, input: $input) {
    id
    isActive
    role {
      id
      code
    }
    companyUser {
      id
      companyId
      isAdmin
    }
  }
}
```

```json
{
  "actor": "2",
  "input": {
    "companyUserId": "4",
    "roleId": "2"
  }
}
```

## crear-cuenta

CONTADOR puede crearla; cambia actor a la membresía CAPTURISTA para comprobar el rechazo.

```graphql
mutation ($actor: ID!, $input: CreateAccountInput!) {
  createAccount(actorCompanyUserId: $actor, input: $input) {
    id
    companyId
    name
    accountType
    bankName
    accountNumber
    clabe
    cardLastDigits
    shortDescription
    longDescription
    isActive
    createdAt
    updatedAt
    company {
      id
    }
  }
}
```

```json
{
  "actor": "3",
  "input": {
    "companyId": "2",
    "accountType": "DEBIT",
    "name": "Cuenta de ejemplo nueva"
  }
}
```

## crear-concepto

Requiere concepts.write.

```graphql
mutation ($actor: ID!, $input: CreateConceptInput!) {
  createConcept(actorCompanyUserId: $actor, input: $input) {
    id
    companyId
    name
    conceptType
    shortDescription
    longDescription
    isActive
    createdAt
    updatedAt
  }
}
```

```json
{
  "actor": "3",
  "input": {
    "companyId": "2",
    "conceptType": "INCOME",
    "name": "Ingreso nuevo"
  }
}
```

## asignar-concepto

Requiere concepts.write. Si este par ya está activo por la carga demo, devuelve CONFLICT.

```graphql
mutation ($actor: ID!, $input: AssignConceptToAccountInput!) {
  assignConceptToAccount(actorCompanyUserId: $actor, input: $input) {
    id
    isActive
    createdAt
    account {
      id
    }
    concept {
      id
    }
  }
}
```

```json
{
  "actor": "3",
  "input": {
    "accountId": "4",
    "conceptId": "11"
  }
}
```

## movimiento-aceptado

CAPTURISTA puede registrar el movimiento. capturedBy se obtiene de su membresía.

```graphql
mutation ($actor: ID!, $input: CreateTransactionInput!) {
  createTransaction(actorCompanyUserId: $actor, input: $input) {
    id
    amount
    transactionType
    transactionDate
    capturedAt
    capturedBy
    isActive
    account {
      id
    }
    concept {
      id
    }
    capturedByUser {
      id
    }
  }
}
```

```json
{
  "actor": "4",
  "input": {
    "accountId": "4",
    "conceptId": "11",
    "transactionType": "INCOME",
    "amount": "13.37"
  }
}
```

## movimiento-rechazado

CONSULTA recibe FORBIDDEN; el conteo SQL de transactions no cambia.

```graphql
mutation ($actor: ID!, $input: CreateTransactionInput!) {
  createTransaction(actorCompanyUserId: $actor, input: $input) {
    id
    amount
    transactionType
    transactionDate
    capturedAt
    capturedBy
    isActive
    account {
      id
    }
    concept {
      id
    }
    capturedByUser {
      id
    }
  }
}
```

```json
{
  "actor": "5",
  "input": {
    "accountId": "4",
    "conceptId": "11",
    "transactionType": "INCOME",
    "amount": "13.37"
  }
}
```

## consultar-movimientos

Requiere transactions.read y solo consulta la empresa actora.

```graphql
query ($actor: ID!, $a: ID, $type: TransactionType, $limit: Int, $offset: Int) {
  transactions(
    actorCompanyUserId: $actor
    accountId: $a
    transactionType: $type
    limit: $limit
    offset: $offset
  ) {
    id
    amount
    isActive
    capturedBy
  }
}
```

```json
{
  "actor": "5",
  "a": "4",
  "limit": 10,
  "offset": 0
}
```

## consultar-membresias

Requiere company.users.read.

```graphql
query ($actor: ID!, $id: ID!) {
  companyUsers(actorCompanyUserId: $actor, companyId: $id) {
    id
    isAdmin
    isActive
    user {
      id
    }
  }
}
```

```json
{
  "actor": "2",
  "id": "2"
}
```

## crear-usuario

Requiere company.users.write. Nace con CONSULTA; assignRole puede cambiarlo.

```graphql
mutation ($actor: ID!, $input: CreateCompanyUserInput!) {
  createCompanyUser(actorCompanyUserId: $actor, input: $input) {
    id
    userId
    isAdmin
  }
}
```

```json
{
  "actor": "2",
  "input": {
    "companyId": "2",
    "name": "Usuario de ejemplo",
    "email": "nuevo@example.com",
    "password": "<elige-una-contraseña-de-prueba>"
  }
}
```

## login

Login conserva su contrato, hash y token. No uses la contraseña del ejemplo como una credencial real.

```graphql
mutation ($input: LoginInput!) {
  login(input: $input) {
    token
    tokenType
    user {
      id
      email
    }
  }
}
```

```json
{
  "input": {
    "email": "admin.roles@example.com",
    "password": "<valor-ADMINISTRADOR-de-.roles-demo.json>"
  }
}
```

## Consultar un rol por ID

```graphql
query { role(actorCompanyUserId: "2", id: "3") { id code name isActive } }
```

Devuelve null para un ID inexistente, después de validar roles.read.

## Segundo administrador principal

La captura `12-administrador-duplicado.graphql` contiene la operación real. Requiere la cabecera privada X-Bootstrap-Key. En una empresa que ya tiene administrador devuelve CONFLICT antes de insertar un usuario.
