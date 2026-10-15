# Operaciones GraphQL de la actividad 4

Usa `/graphql`, pestaña Query para la operación y Variables para el JSON. Los IDs son ejemplos: sustitúyelos por los devueltos en tu base. En todas las operaciones financieras agrega `{"Authorization":"Bearer <token>"}` en Headers. La lista completa de tipos, campos y nulabilidad está en `schema.graphql`.

## Login

```graphql
mutation Login($input: LoginInput!) {
  login(input: $input) { token tokenType user { id name email } }
}
```

```json
{"input":{"email":"actividad4@example.com","password":"<contraseña de .demo-credentials.json>"}}
```

No compartas las credenciales ni el token en evidencias.

## Crear una cuenta

```graphql
mutation Cuenta($input: CreateAccountInput!) {
  createAccount(input: $input) {
    id companyId accountType name bankName accountNumber clabe cardLastDigits
    shortDescription longDescription isActive createdAt updatedAt company { id name }
  }
}
```

```json
{"input":{"companyId":"1","accountType":"DEBIT","name":"Cuenta de ejemplos","bankName":"Banco ficticio","accountNumber":"000123","clabe":"000000000000000001","cardLastDigits":"0123","shortDescription":"Uso académico","longDescription":null}}
```

## Consultar cuentas con filtros

```graphql
query Cuentas($companyId: ID!, $type: AccountType, $active: Boolean) {
  accounts(companyId: $companyId, accountType: $type, activeOnly: $active) {
    id name accountType isActive company { id }
  }
}
```

```json
{"companyId":"1","type":"DEBIT","active":true}
```

## Crear conceptos

```graphql
mutation Concepto($input: CreateConceptInput!) {
  createConcept(input: $input) {
    id companyId conceptType name shortDescription longDescription isActive createdAt updatedAt
  }
}
```

Ingreso:

```json
{"input":{"companyId":"1","conceptType":"INCOME","name":"Venta de ejemplo","shortDescription":"Ingreso de clase","longDescription":null}}
```

Egreso (ejecuta de nuevo la misma mutación):

```json
{"input":{"companyId":"1","conceptType":"EXPENSE","name":"Compra de ejemplo"}}
```

## Consultar conceptos

```graphql
query Conceptos($companyId: ID!, $type: ConceptType, $active: Boolean) {
  concepts(companyId: $companyId, conceptType: $type, activeOnly: $active) {
    id name conceptType isActive
  }
}
```

```json
{"companyId":"1","type":"INCOME","active":true}
```

## Asignar un concepto a una cuenta

```graphql
mutation Asignar($input: AssignConceptToAccountInput!) {
  assignConceptToAccount(input: $input) {
    id accountId conceptId isActive createdAt account { id name } concept { id name conceptType }
  }
}
```

```json
{"input":{"accountId":"1","conceptId":"1"}}
```

Si el seed ya creó este par, la respuesta correcta es CONFLICT. Usa IDs de los registros nuevos para crear otra relación. Después de desactivarla, la misma mutación recupera su ID original.

## Consultar relaciones activas

```graphql
query Relaciones($accountId: ID!) {
  accountConcepts(accountId: $accountId) {
    id accountId conceptId isActive concept { id name conceptType }
  }
}
```

```json
{"accountId":"1"}
```

## Desactivar una relación

```graphql
mutation Quitar($accountId: ID!, $conceptId: ID!) {
  removeConceptFromAccount(accountId: $accountId, conceptId: $conceptId)
}
```

```json
{"accountId":"1","conceptId":"1"}
```

Devuelve true en la primera desactivación y false si ya no está activa. Vuelve a asignarla antes de intentar nuevos movimientos con ese concepto.

## Registrar ingreso o egreso

```graphql
mutation Movimiento($input: CreateTransactionInput!) {
  createTransaction(input: $input) {
    id accountId conceptId transactionType amount transactionDate capturedAt capturedBy
    shortDescription longDescription isActive createdAt updatedAt
    account { id name } concept { id name } capturedByUser { id name }
  }
}
```

Ingreso con zona horaria explícita:

```json
{"input":{"accountId":"1","conceptId":"1","transactionType":"INCOME","amount":"1500.10","transactionDate":"2026-09-25T10:00:00-06:00","shortDescription":"Ingreso académico","longDescription":null}}
```

Egreso: usa el ID real de un concepto EXPENSE permitido en esa cuenta. En la carga inicial sin otros datos, el par cuenta 3 / concepto 6 cumple esa condición:

```json
{"input":{"accountId":"3","conceptId":"6","transactionType":"EXPENSE","amount":"250.20","shortDescription":"Egreso académico"}}
```

No se envían capturedBy ni capturedAt. Una fecha omitida o null se establece en servidor. Los importes se envían como cadenas para conservar precisión.

## Consultar y paginar movimientos

```graphql
query Movimientos($accountId: ID, $type: TransactionType, $limit: Int, $offset: Int) {
  transactions(accountId: $accountId, transactionType: $type, limit: $limit, offset: $offset) {
    id amount transactionType transactionDate capturedBy isActive
    account { id name } concept { id name } capturedByUser { id name }
  }
}
```

```json
{"accountId":null,"type":"INCOME","limit":10,"offset":0}
```

Incrementa offset para ver la siguiente página. Usa type=null para ambos tipos. Solo se devuelven movimientos activos de empresas autorizadas.

## Eliminar un movimiento

```graphql
mutation Eliminar($id: ID!) {
  deleteTransaction(id: $id) { id isActive capturedBy capturedAt amount updatedAt }
}
```

```json
{"id":"1"}
```

Conserva el registro con isActive=false. Ya no aparece en transactions ni contribuye al balance.

## Balance (extensión)

```graphql
query Saldo($accountId: ID!) {
  accountBalance(accountId: $accountId)
}
```

```json
{"accountId":"1"}
```

Devuelve una cadena decimal exacta, calculada sobre todos los movimientos activos de esa cuenta.

## Casos de error reproducibles

Repite la creación de cuenta variando solo espacios o mayúsculas: CONFLICT. Repite la asignación activa: CONFLICT. En Movimiento, usa amount="0" o "-1": BAD_INPUT. Usa un ID inexistente: NOT_FOUND. Usa un concepto sin asignación activa o cambia el tipo respecto del concepto: BAD_INPUT. Omite el token: UNAUTHENTICATED. Usa IDs de otra empresa: FORBIDDEN. Agrega capturedBy al input: error de validación GraphQL. Los mismos casos están automatizados y sus respuestas reales aparecen en `docs/evidencias/graphql.json`.
