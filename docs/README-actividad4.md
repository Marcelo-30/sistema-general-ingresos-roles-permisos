# Actividad 4: cuentas, conceptos y movimientos financieros

**Autor: Enrique Zavala. Entrega individual.** Véase `ENTREGA.md`.

Implementación integrada con la **Actividad 3 existente**: FastAPI, Strawberry GraphQL, SQLAlchemy y SQLite. Se conservan Company, User, CompanyUser, contraseñas Argon2id, tokens JWT y las operaciones anteriores. No se creó una autenticación paralela ni se reemplazaron tablas existentes. El README anterior se conserva en `docs/README-actividad3.md`.

Fuente de requisitos: las siete páginas de `session_3_4_actividad.pdf`. Los cuatro modelos, tres enums, cuatro inputs, cuatro consultas y seis mutaciones financieras mantienen nombres, tipos, argumentos y nulabilidad. `accountBalance` es una **extensión** para demostrar la regla del saldo.

## Preparación en Windows PowerShell

Desde la carpeta del proyecto, con Python 3.13 (versión comprobada):

```powershell
python -m venv env
.\env\Scripts\Activate.ps1  # Opcional
.\env\Scripts\python.exe -m pip install -r requirements.txt
# Solo si no existe .env; genera claves aleatorias sin mostrarlas:
.\env\Scripts\python.exe -m app.init_config
.\env\Scripts\python.exe -m app.init_db
.\env\Scripts\python.exe -m app.seed
.\env\Scripts\python.exe -m app.verify_seed
.\env\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Si `.env` ya existe, omite `app.init_config`: conserva su configuración. Abre [GraphQL](http://127.0.0.1:8000/graphql). Detén el servidor con Ctrl+C. La activación no es necesaria para los comandos con ruta completa; si PowerShell bloquea `Activate.ps1`, usa directamente `env\Scripts\python.exe`.

## Preparación en Linux/macOS

```bash
python3 -m venv env
source env/bin/activate  # Opcional
./env/bin/python -m pip install -r requirements.txt
# Omitir si ya existe .env:
./env/bin/python -m app.init_config
./env/bin/python -m app.init_db
./env/bin/python -m app.seed
./env/bin/python -m app.verify_seed
./env/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

`env/` es el entorno virtual; `.env` es un archivo privado de configuración. Son elementos diferentes. `.env.example` describe DATABASE_URL, JWT_SECRET, BOOTSTRAP_KEY y JWT_EXPIRE_MINUTES sin secretos. No copies valores vacíos sobre una configuración funcional. Para salir de un entorno activado, usa `deactivate`.

## Base de datos y demostración

`app.init_db` crea únicamente tablas ausentes; no elimina registros. SQLite usa claves foráneas habilitadas. La configuración predeterminada es `sqlite:///./app.db`; ejecuta los comandos desde la raíz del proyecto. Esta implementación usa específicamente SQLite y `BEGIN IMMEDIATE` para serializar escrituras y sus comprobaciones de permisos.

`app.seed` crea una empresa ficticia identificada por `DEMO-ACTIVIDAD-4`, un administrador, **3 cuentas, 5 conceptos INCOME, 5 conceptos EXPENSE, 10 relaciones y 20 movimientos** (10 ingresos y 10 egresos). Usa los servicios de la aplicación, incluyendo autenticación y validaciones. Todo el lote se confirma en una transacción o se revierte. Puede repetirse sin duplicados: se comprobó ejecutándolo dos veces.

La primera carga genera credenciales aleatorias en `.demo-credentials.json`, excluido de Git. Puedes establecer `DEMO_PASSWORD` antes de la primera carga; no se imprime la contraseña ni el token. Si la empresa ya existe, conserva el archivo de credenciales para ejecutar de nuevo la carga. El script no reactiva movimientos borrados ni modifica registros demo ya existentes: una segunda carga preserva esas decisiones. No borres el archivo de credenciales mientras conserves su empresa en la base.

`app.verify_seed` verifica los mínimos por empresa y muestra conteos sin secretos; incluye registros conservados mediante eliminación lógica. Para comprobar registros operativos activos, consulta GraphQL. No se distribuyen contraseñas reales ni bases de datos en Git.

## Autenticación y uso

1. Abre localmente `.demo-credentials.json` y usa sus valores en `login` (ver ejemplos).
2. Copia el token devuelto a las cabeceras de GraphiQL: `{"Authorization":"Bearer <token>"}`.
3. Consulta las cuentas con el `companyId` impreso por `app.seed` y utiliza los IDs retornados en los ejemplos.

Los tokens expiran a los 30 minutos por defecto. Para crear otras empresas y su primer administrador se conserva `X-Bootstrap-Key` de la actividad anterior; los ejemplos están en [operaciones anteriores](docs/operaciones.md). Esta clave **no sustituye el token** en las operaciones financieras. Los miembros normales activos también pueden registrar movimientos, siempre en sus empresas activas. Una persona con varias membresías ve solamente esas empresas; no puede mezclar cuenta y concepto de empresas distintas.

[Ejemplos de todas las operaciones financieras con variables](docs/actividad4-operaciones.md). [Contrato completo exportado](schema.graphql).

## Organización

| Archivo | Responsabilidad |
|---|---|
| `app/config.py`, `db.py`, `factory.py`, `main.py` | Configuración, conexiones, aplicación y servidor |
| `app/models.py`, `service.py` | Empresas, usuarios y autenticación previos |
| `app/finance_models.py` | Tablas financieras, claves foráneas, restricciones únicas y decimal exacto |
| `app/finance_service.py` | Permisos por membresía, reglas, filtros, eliminación y balance |
| `app/schema.py`, `finance_schema.py` | Contrato GraphQL, escalares, resolvers y transacciones |
| `app/seed.py`, `verify_seed.py` | Datos demostrativos idempotentes y comprobación de mínimos |
| `tests/test_finance.py`, `finance_pdf.graphql` | Pruebas HTTP y contrato transcrito del PDF |
| `scripts/smoke_finance.py` | Verificación contra un servidor HTTP real |
| `docs/actividad4-evidencias.md` | Resultados y lista de verificación del PDF |

## Decisiones y reglas

- **Duplicados:** cuenta = empresa + nombre; concepto = empresa + tipo + nombre. Se colapsan espacios y se aplica `casefold` a la clave del nombre. No se eliminan acentos. Un nombre de concepto puede existir en ambos tipos. Las restricciones únicas también se aplican a registros inactivos. Números bancarios y CLABE se conservan como texto para respetar ceros iniciales; no definen identidad ni se añaden validaciones bancarias que el PDF no establece.
- **Relaciones:** UNIQUE(account_id, concept_id) impide duplicados incluso fuera de GraphQL. Duplicar una relación activa devuelve CONFLICT. Reasignar una inactiva reactiva el mismo ID y conserva createdAt. Quitar una relación existente devuelve true; repetir devuelve false. `accountConcepts` muestra solo relaciones activas.
- **Dinero:** `decimal.Decimal` en Python y texto decimal en SQLite. No se usa float ni SUM de SQLite. Envía `"amount":"0.10"`, no `0.10` como número JSON. El escalar acepta texto decimal o enteros, rechaza NaN, infinito, booleanos y float. Límite técnico: 100 dígitos significativos y exponente entre -100 y 100; no se impone redondeo a dos decimales. El balance usa precisión suficiente para sumar exactamente todos los montos admitidos.
- **Fechas:** Time acepta fecha y hora ISO 8601 con zona horaria. Se normaliza a UTC y se serializa con `Z`. SQLite conserva UTC sin información de zona y la API la restituye. Si transactionDate se omite o es null, toma el mismo instante que capturedAt. capturedAt y capturedBy se generan exclusivamente en servidor; el input no permite suplantarlos.
- **Movimientos:** monto positivo, cuenta y concepto existentes y activos, relación activa, mismo tipo y empresa autorizada. No se prohíben saldos negativos. `balance = ingresos activos − egresos activos`.
- **Eliminación lógica:** deleteTransaction conserva la fila y el responsable, marca isActive=false y es idempotente. Las consultas operativas y el balance excluyen eliminados. Desasignar un concepto no elimina movimientos históricos.
- **Filtros:** activeOnly=true filtra activos; false, null u omisión incluyen ambos estados en cuentas y conceptos. transactions ordena por ID ascendente; limit omitido/null = 100, offset = 0, limit=0 devuelve lista vacía y negativos producen BAD_INPUT. El balance no tiene límite ni paginación.
- **Errores:** UNAUTHENTICATED, FORBIDDEN, NOT_FOUND, CONFLICT y BAD_INPUT se devuelven en `errors[].extensions.code`. Errores del contrato o escalares producen errores estándar GraphQL. Los errores SQL se traducen sin incluir detalles internos. Cada resolver usa una transacción; varias mutaciones dentro de un documento GraphQL se confirman individualmente, no constituyen un lote atómico.

## Pruebas y evidencias

```powershell
.\env\Scripts\python.exe -m pip check
.\env\Scripts\python.exe -m pytest -v
.\env\Scripts\python.exe -m app.export_schema
# Con el servidor y los datos demo disponibles:
.\env\Scripts\python.exe scripts\smoke_finance.py http://127.0.0.1:8000/graphql
```

Linux/macOS: sustituye el intérprete por `./env/bin/python` y usa `scripts/smoke_finance.py`.

Las pruebas usan bases temporales independientes de `app.db`. Incluyen autenticación real y resolvers HTTP, comparación del contrato del PDF, precisión leída de SQLite, restricciones únicas y rollback. `docs/evidencias/graphql.json` contiene operaciones, variables, expectativas, respuestas y estado de cada prueba; contraseñas y tokens se ocultan. Las ejecuciones posteriores regeneran este archivo. Los resultados de entrega y sus limitaciones se detallan en [evidencias y checklist](docs/actividad4-evidencias.md).

La ejecución se verificó en Windows con Python 3.13. Linux/macOS tiene comandos documentados, pero no se ejecutó en esos sistemas. La entrega es individual, a nombre de Enrique Zavala, conforme a su indicación. El envío al docente corresponde al autor.
