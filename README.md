# Sistema General de Ingresos — Unidad II, Actividades 3 y 4

La secuencia de **configuración de permisos para diferentes roles** de la actividad 4 está en [la guía de ejecución y capturas](docs/actividad4-configuracion-permisos.md). `app.demo_actividad4` prepara a Ana, Luis, María, José y Pedro en una empresa separada; `tests/test_actividad4_permisos.py` verifica por GraphQL y SQL los cambios de permisos, el cambio de rol, los rechazos sin escritura y el reinicio idempotente.

**Gestión de roles y permisos. Autor: Enrique Zavala. Entrega individual.**

[Repositorio GitHub](https://github.com/Marcelo-30/sistema-general-ingresos-roles-permisos) · [Evidencias y capturas](docs/evidencias/unidad2/README.md) · [Operaciones GraphQL](docs/roles-operaciones.md) · [Consultas SQL](docs/comprobacion-mysql.sql)

Se continúa el proyecto existente de empresas, usuarios, cuentas, conceptos y movimientos. Se agregan Role, Permission, RolePermission y CompanyUserRole, separados en modelos SQLAlchemy y tipos Strawberry. Se conserva FastAPI, el endpoint `/graphql`, el hash Argon2id y la operación `login` con JWT. Se incorpora MySQL 8.4 y Docker Compose porque la versión local anterior utilizaba SQLite. El archivo SQLite anterior no se elimina.

## Inicio con Docker Desktop — Windows PowerShell

Abre Docker Desktop y espera a que el motor esté disponible. Desde la carpeta extraída del proyecto, con Python 3.13:

```powershell
python -m venv env
.\env\Scripts\python.exe -m pip install -r requirements.txt
# Solo la primera vez; no sobrescribe una configuración existente:
.\env\Scripts\python.exe -m app.init_docker

docker compose --env-file .env.docker up -d --build
$env:SETTINGS_FILE = '.env.docker'
.\env\Scripts\python.exe -m app.seed
.\env\Scripts\python.exe -m app.demo_roles
```

Abre **http://127.0.0.1:8007/graphql**. El servidor API usa el puerto 8007 del equipo; MySQL usa 3307. Dentro de Docker, los servicios se comunican por `mysql:3306`. Ambos puertos del equipo están limitados a localhost. El volumen `mysql_data` conserva la base entre reinicios.

`env` es el entorno virtual. `.env.docker` es un archivo privado con configuración y claves aleatorias; no es una carpeta ni se entrega en Git. El `.env` previo se conserva para SQLite. `SETTINGS_FILE` elige la configuración de los comandos Python locales. `.env.docker.example` muestra los nombres de variables sin claves reales. No copies sus valores vacíos sobre la configuración generada.

La activación es opcional: `.\env\Scripts\Activate.ps1`. Todos los comandos usan directamente el intérprete de `env`.

## Linux/macOS

```bash
python3 -m venv env
./env/bin/python -m pip install -r requirements.txt
./env/bin/python -m app.init_docker  # Omitir si .env.docker ya existe

docker compose --env-file .env.docker up -d --build
SETTINGS_FILE=.env.docker ./env/bin/python -m app.seed
SETTINGS_FILE=.env.docker ./env/bin/python -m app.demo_roles
```

Opcional: `source env/bin/activate`. La imagen Linux de la API se construyó y ejecutó en Docker Desktop; los comandos de shell de macOS no se probaron en un Mac.

## Reinicio y parada

```powershell
docker compose --env-file .env.docker ps
docker compose --env-file .env.docker restart api
docker compose --env-file .env.docker logs --tail 50 api
docker compose --env-file .env.docker stop
# Para volver a iniciar:
docker compose --env-file .env.docker up -d
```

No uses `down -v` si necesitas conservar los datos: esa opción elimina el volumen. Cambiar las contraseñas de `.env.docker` no cambia automáticamente las credenciales de un volumen MySQL ya inicializado.

## Migración de la base anterior

En esta entrega se copió `app.db` a MySQL y se verificó, campo por campo, la conservación de 1 empresa, 1 usuario, 1 membresía, 3 cuentas, 10 conceptos, 10 relaciones y 20 movimientos. Se conserva SQLite y un respaldo local previo al trabajo. Los respaldos y la base no se incluyen en el ZIP ni en GitHub.

Para una instalación que tenga una base SQLite anterior, ejecuta **antes de cargar los datos demo**:

```powershell
$env:SETTINGS_FILE = '.env.docker'
.\env\Scripts\python.exe -m app.migrate_sqlite --source app.db
```

La copia requiere que las tablas empresariales de MySQL estén vacías; si ya contienen datos, se detiene sin reemplazarlos. Preserva IDs, hashes, importes exactos y fechas con microsegundos. Se usa `DATETIME(6)` en MySQL. Las tablas se crean mediante `Base.metadata.create_all`, como en el proyecto anterior; una ampliación no destructiva de precisión de fechas se aplica si hace falta.

**Transición de membresías antiguas:** las membresías activas sin ninguna asignación histórica reciben `CONSULTA`, incluso si tenían `isAdmin=true`. No se concede administración automáticamente. Se conserva la marca de administrador principal, pero esa marca no otorga permisos. Las asignaciones existentes, incluidas sus desactivaciones, no se reemplazan al reiniciar.

Para continuar el uso de una empresa migrada, sus cambios de rol deben ser decididos explícitamente por el responsable de la base; la aplicación no eleva automáticamente al administrador antiguo. La demostración usa una empresa ficticia nueva cuyo administrador nace por el flujo autorizado `createCompanyAdmin`.

## Datos de prueba e identidad académica

`app.seed` conserva el comando idempotente de la actividad anterior y genera 3 cuentas, 5 conceptos INCOME, 5 EXPENSE, 10 relaciones y 20 movimientos. `app.demo_roles` agrega una empresa ficticia separada con las cuatro membresías, una cuenta y conceptos permitidos. Ambos comandos preservan datos ya existentes.

`app.demo_roles` imprime los IDs reales y guarda su mapa en `docs/evidencias/unidad2/demo-ids.json`. Las contraseñas demo se guardan únicamente en `.demo-credentials.json` y `.roles-demo.json`, excluidos de Git y del ZIP. No se imprimen. No elimines estos archivos privados mientras quieras reutilizar sus usuarios.

En esta unidad las operaciones protegidas reciben **`actorCompanyUserId: ID!` como argumento de GraphQL**. Es el ID de la membresía, no el ID del usuario ni el ID del rol. Los inputs del PDF mantienen sus campos. El argumento explícito se agregó también a las consultas y mutaciones de roles para proteger los catálogos.

Este es el mecanismo académico que pide el PDF: el cliente elige la membresía para probarla; los permisos se consultan siempre en la base. **No autentica que el cliente sea dueño de esa membresía.** La vinculación de la identidad al token corresponde a la siguiente unidad. La API de esta entrega se ofrece solamente en localhost y no debe exponerse como un servicio de producción con este mecanismo.

`login` no cambió: recibe email/password y devuelve token, tokenType y datos mínimos del usuario. La contraseña sigue almacenada con Argon2id y User no expone el hash. En las operaciones de esta unidad el token no sustituye `actorCompanyUserId`.

Para crear empresas y su primer administrador se conserva el flujo inicial con cabecera `X-Bootstrap-Key` y la clave del archivo de configuración. No requiere una membresía inexistente. `createCompanyAdmin` asigna `isAdmin=true` y `ADMINISTRADOR` en una misma transacción, y rechaza un segundo administrador principal.

## Matriz inicial exacta

| Permiso | ADMINISTRADOR | CONTADOR | CAPTURISTA | CONSULTA |
|---|:---:|:---:|:---:|:---:|
| company.users.read | Sí | Sí | No | Sí |
| company.users.write | Sí | No | No | No |
| accounts.read | Sí | Sí | Sí | Sí |
| accounts.write | Sí | Sí | No | No |
| concepts.read | Sí | Sí | Sí | Sí |
| concepts.write | Sí | Sí | No | No |
| transactions.read | Sí | Sí | Sí | Sí |
| transactions.write | Sí | Sí | Sí | No |
| roles.read | Sí | Sí | No | No |
| roles.write | Sí | No | No | No |

Los catálogos se comparten entre empresas. La configuración inicial consta de **4 roles, 10 permisos y 26 relaciones**. Roles y permisos solo se cargan si su tabla completa está vacía. La matriz de un rol solo se carga si no tiene ninguna relación histórica, contando también las inactivas. Por ello un reinicio no restaura una revocación deliberada. Un catálogo parcial que impida cargar la matriz produce un error explícito y requiere que su responsable lo complete.

## Autorización y decisiones de integridad

- `exigir_permiso(db, company_user_id, codigo)` verifica usuario, membresía y empresa activos, exactamente una asignación activa, rol activo, relación activa y permiso activo. Nunca usa `isAdmin` para saltar la autorización.
- Cada resolver protegido exige el permiso **antes de escribir y de nuevo antes del commit**. Los errores GraphQL provocan rollback del resolver. Por ello retirarse el propio último permiso `roles.write` falla y revierte el cambio. Varias mutaciones distintas dentro de un documento GraphQL se confirman individualmente; no forman un lote atómico.
- Las operaciones empresariales se restringen a la empresa de la membresía actora. Las consultas sin filtro de cuenta también mantienen ese alcance. Las configuraciones de roles son globales.
- `assignRole` desactiva la asignación anterior y activa o reutiliza la nueva dentro de la misma transacción. Una restricción única protege el par y otra garantiza como máximo una asignación activa. El flujo de creación asegura una asignación para cada membresía activa: `CONSULTA` por defecto y `ADMINISTRADOR` para el administrador inicial.
- En MySQL se usan índices únicos de expresión para una sola asignación activa y un solo administrador principal. SQLite conserva índices parciales. Las operaciones bloquean las filas de roles en orden para serializar comprobaciones y cambios concurrentes; es una decisión sencilla para este proyecto académico, no una optimización para grandes volúmenes.
- `assignPermissionToRole` rechaza una pareja activa y reactiva la misma fila si estaba inactiva. `removePermissionFromRole` la desactiva; repetir la eliminación devuelve false. `rolePermissions` devuelve relaciones activas.
- `deactivateRole` conserva la fila. Si tiene membresías activas asignadas, exige reasignarlas primero para no dejarlas sin rol activo. Roles inactivos no autorizan.
- Se protegen también `removeConceptFromAccount` con `concepts.write`, `deleteTransaction` con `transactions.write` y `accountBalance` con `transactions.read`.
- Se mantienen las reglas financieras: Decimal exacto almacenado como texto, monto positivo, empresa coherente, cuenta/concepto activos, relación permitida y tipo compatible. No se introduce restricción de saldo insuficiente. El balance resta egresos de ingresos activos; la eliminación es lógica. Fechas UTC con microsegundos. Los detalles originales de duplicados y precisión siguen en `docs/README-actividad4.md`.

## Estructura

| Ruta | Responsabilidad |
|---|---|
| `app/models.py`, `finance_models.py` | Entidades anteriores conservadas y tipos compatibles con MySQL |
| `app/access_models.py` | Cuatro modelos SQLAlchemy de acceso |
| `app/access.py` | Matriz, arranque idempotente, transición y `exigir_permiso` |
| `app/access_service.py` | Operaciones de roles, permisos y asignaciones |
| `app/access_schema.py` | Tipos, inputs y resolvers Strawberry de la nueva unidad |
| `app/schema.py`, `finance_schema.py` | Operaciones anteriores con el nuevo argumento de actor |
| `app/service.py`, `finance_service.py` | Reglas existentes, pertenencia y control antes del commit |
| `app/db.py`, `factory.py` | Conexión, precisión, bloqueo transaccional y arranque |
| `app/demo_roles.py`, `seed.py` | Datos ficticios idempotentes |
| `app/migrate_sqlite.py` | Copia segura a MySQL vacío |
| `tests/` | Suite actual HTTP GraphQL y comprobación de contrato |
| `docs/contrato-anterior-tests/` | Pruebas históricas del contrato anterior exclusivamente JWT |
| `docs/evidencias/unidad2/` | Capturas reales, resultados, consultas y comprobaciones SQL |
| `Dockerfile`, `compose.yaml` | API Python y MySQL con volumen persistente |

Las pruebas anteriores se conservan como referencia histórica: su contrato no incluía actorCompanyUserId. La suite actual prueba expresamente el nuevo contrato y las reglas financieras conservadas. Las evidencias anteriores también permanecen identificadas por actividad.

## Pruebas reproducibles

```powershell
# MySQL debe estar encendido y .env.docker debe existir.
$env:TEST_MYSQL = '1'
.\env\Scripts\python.exe -m pytest -v
Remove-Item Env:TEST_MYSQL
# Compatibilidad con SQLite, sin afectar app.db:
.\env\Scripts\python.exe -m pytest -v
.\env\Scripts\python.exe -m pip check
```

Linux/macOS:

```bash
TEST_MYSQL=1 ./env/bin/python -m pytest -v
./env/bin/python -m pytest -v
./env/bin/python -m pip check
```

Cada prueba MySQL crea una base aleatoria `ingresos_test_<uuid>` y elimina solamente esa base al terminar. Usa las credenciales locales de root para crear esas bases; no modifica la base de la aplicación. SQLite usa archivos temporales. Las respuestas se guardan con secretos ocultos en `graphql-mysql.json` o `graphql-sqlite.json`.

Resultado de entrega: **41 pruebas aprobadas en MySQL 8.4.11; 40 aprobadas en SQLite y 1 omitida por ser específica de migración a MySQL**. Hay un aviso de deprecación de Starlette/AnyIO que no impide las pruebas. Además se ejecutaron 7 comprobaciones HTTP contra la API en Docker y se capturaron 12 evidencias reales de GraphiQL.

Para comprobar SQL y exportar el contrato:

```powershell
$env:SETTINGS_FILE = '.env.docker'
.\env\Scripts\python.exe -m scripts.verify_mysql comprobacion-local
.\env\Scripts\python.exe -m app.export_schema
```

El archivo `docs/comprobacion-mysql.sql` puede ejecutarse en tu cliente MySQL. Incluye matriz, conteos y detección de membresías sin exactamente un rol activo.

## Entrega

El repositorio se creó **privado**; el ZIP permite revisar el proyecto sin acceso a la cuenta GitHub. Para reconstruir el archivo de entrega:

```powershell
.\env\Scripts\python.exe scripts\package_delivery.py
```

El ZIP excluye `env`, `.venv`, `.git`, `.env`, `.env.docker`, credenciales demo, bases, respaldos y cachés. Incluye código, Docker Compose, ejemplos, pruebas y capturas. El script verifica integridad y compara los contenidos con los secretos locales para impedir que estos se empaqueten.
