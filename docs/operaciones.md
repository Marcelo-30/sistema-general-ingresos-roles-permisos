# Operaciones para GraphiQL

Abre http://127.0.0.1:8000/graphql. Copia una operación al panel principal y su JSON al panel **Variables**. Coloca las cabeceras en **Headers**. Usa los IDs que devuelva tu instalación; no asumas que siempre son 1.

Los valores entre `<...>` se sustituyen manualmente. Las contraseñas de ejemplo son sólo para pruebas locales; no son secretos de la aplicación. Las respuestas reales de las pruebas automatizadas están en [evidencias/graphql.json](evidencias/graphql.json), con credenciales ocultas. Los resultados descritos aquí son expectativas para ejecución manual.

## 1. Crear empresa (operador)

Cabeceras, usando BOOTSTRAP_KEY de tu `.env`:

```json
{"X-Bootstrap-Key":"<BOOTSTRAP_KEY>"}
```

```graphql
mutation CrearEmpresa($input: CreateCompanyInput!) {
  createCompany(input: $input) {
    id name legalName taxId email phone isActive createdAt updatedAt
  }
}
```

```json
{"input":{"name":"Empresa académica","legalName":"Empresa de ejemplo","taxId":"DEMO-001","email":"empresa@example.com","phone":"5551234567"}}
```

Esperado: empresa activa con ID y fechas. Guarda el ID como `<EMPRESA_ID>`.

## 2. Consultar empresas (misma cabecera de operador)

```graphql
query Empresas($activeOnly: Boolean) {
  companies(activeOnly: $activeOnly) { id name isActive }
}
```

```json
{"activeOnly":true}
```

Esperado: sólo activas. False, null u omisión devuelven todas.

```graphql
query Empresa($id: ID!) {
  company(id: $id) { id name legalName email isActive createdAt updatedAt }
}
```

```json
{"id":"<EMPRESA_ID>"}
```

Esperado: empresa solicitada o null si no existe.

## 3. Actualizar (operador)

```graphql
mutation EditarEmpresa($input: UpdateCompanyInput!) {
  updateCompany(input: $input) { id name legalName email isActive updatedAt }
}
```

```json
{"input":{"id":"<EMPRESA_ID>","name":"Nuevo nombre","legalName":null}}
```

Esperado: cambia nombre, borra legalName y conserva email porque se omitió. `{"input":{"id":"<EMPRESA_ID>","name":null}}` produce BAD_INPUT.

## 4. Crear administrador inicial (operador)

```graphql
mutation CrearAdministrador($input: CreateCompanyAdminInput!) {
  createCompanyAdmin(input: $input) {
    id companyId userId isAdmin isActive joinedAt
    company { id name }
    user { id name email emailVerified isActive createdAt updatedAt }
  }
}
```

```json
{"input":{"companyId":"<EMPRESA_ID>","name":"Administrador","email":"admin@example.com","password":"Academico-2026!"}}
```

Esperado: isAdmin=true, emailVerified=false. Repetir con otro correo debe dar CONFLICT. Sin clave de inicialización da FORBIDDEN.

## 5. Login (sin cabeceras)

Quita X-Bootstrap-Key; deja `{}` en Headers.

```graphql
mutation Entrar($input: LoginInput!) {
  login(input: $input) { token tokenType user { id name email } }
}
```

```json
{"input":{"email":"admin@example.com","password":"Academico-2026!"}}
```

Esperado: tokenType="Bearer" y un token. Una contraseña incorrecta produce UNAUTHENTICATED. Copia el token a Headers para los pasos 6–8:

```json
{"Authorization":"Bearer <TOKEN>"}
```

## 6. Registrar usuario (administrador autenticado)

```graphql
mutation CrearUsuario($input: CreateCompanyUserInput!) {
  createCompanyUser(input: $input) {
    id companyId userId isAdmin isActive joinedAt
    company { id name }
    user { id name email emailVerified isActive }
  }
}
```

```json
{"input":{"companyId":"<EMPRESA_ID>","name":"Usuario de ejemplo","email":"usuario@example.com","password":"Usuario-2026!"}}
```

Esperado: isAdmin=false. Guarda el ID superior (membresía) como `<MEMBRESIA_ID>`; es distinto del concepto de userId. Repetir el correo produce CONFLICT; usar otra empresa produce FORBIDDEN; omitir el token produce UNAUTHENTICATED.

## 7. Consultar miembros

```graphql
query Miembros($companyId: ID!) {
  companyUsers(companyId: $companyId) {
    id companyId userId isAdmin isActive joinedAt
    company { id name }
    user { id name email emailVerified isActive createdAt updatedAt }
  }
}
```

```json
{"companyId":"<EMPRESA_ID>"}
```

Esperado: sólo vínculos de esa empresa, incluidos los inactivos. Ningún tipo de salida expone password ni passwordHash.

## 8. Desactivar usuario en la empresa

```graphql
mutation DesactivarMiembro($id: ID!) {
  deactivateCompanyUser(id: $id) { id isActive user { id email } }
}
```

```json
{"id":"<MEMBRESIA_ID>"}
```

Esperado: isActive=false. No cambia la cuenta global. El login de usuario sin otra membresía operativa devuelve FORBIDDEN. Usar el ID de la membresía principal produce CONFLICT.

## 9. Desactivar y reactivar empresa (operador)

Sustituye Headers por `{"X-Bootstrap-Key":"<BOOTSTRAP_KEY>"}`.

```graphql
mutation DesactivarEmpresa($id: ID!) {
  deactivateCompany(id: $id) { id name isActive updatedAt }
}
```

```json
{"id":"<EMPRESA_ID>"}
```

Esperado: isActive=false; datos conservados. Login queda bloqueado si ésta era la única empresa operativa. El token previo tampoco permite gestionar miembros. Para reactivar, usa EditarEmpresa del paso 3 con:

```json
{"input":{"id":"<EMPRESA_ID>","isActive":true}}
```

La reactivación no reactiva una membresía desactivada individualmente.

## Formato de error

Un error de negocio devuelve `errors` con mensaje y `extensions.code`; por ejemplo, un registro público de administrador devuelve FORBIDDEN. La nulabilidad de GraphQL puede hacer que `data` sea null. Los fallos estándar de validación GraphQL (campo desconocido, tipo incorrecto, argumento obligatorio omitido) se rechazan antes de ejecutar el resolver.
