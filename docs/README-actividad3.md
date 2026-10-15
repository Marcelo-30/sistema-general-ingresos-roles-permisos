# Actividad 3. Empresa–Usuario y User Admin

Implementación de los días 1 y 2 de `session_1_2_actividad.pdf`: gestión de empresas, relación Company–CompanyUser–User, administrador empresarial y autenticación. Python, FastAPI, Strawberry GraphQL, SQLAlchemy y SQLite.

## Ejecutar en Windows PowerShell

Desde la carpeta del proyecto, con Python 3.13:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m app.init_config
.\.venv\Scripts\python.exe -m app.init_db
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Si `.env` ya existe, omite `app.init_config`: no lo sobrescribe. Abre http://127.0.0.1:8000/graphql. Detén el servidor con Ctrl+C.

`.venv` contiene Python y los paquetes del proyecto; `.env` contiene configuración y claves privadas. El generador crea claves aleatorias. No se entregan secretos ni bases de datos personales. Las tablas se crean también al iniciar el servidor.

La activación es opcional: PowerShell `.\.venv\Scripts\Activate.ps1`; CMD `.venv\Scripts\activate.bat`. Los comandos con ruta completa funcionan sin activar. En Linux/macOS crea el entorno con `python3 -m venv .venv`, actívalo con `source .venv/bin/activate` y sustituye `.\.venv\Scripts\python.exe` por `.venv/bin/python` en los comandos. Para salir: `deactivate`.

## Demostración en GraphQL

Las [operaciones copiables](docs/operaciones.md) incluyen variables y cabeceras.

1. Obtén `BOOTSTRAP_KEY` de tu archivo local `.env`. Usa la cabecera `X-Bootstrap-Key` para crear una empresa y su primer administrador.
2. Ejecuta `login` con el correo y contraseña registrados.
3. Usa `Authorization: Bearer <token>` para consultar, crear y desactivar usuarios de esa empresa.

El PDF no establece quién crea empresas ni al primer administrador. La clave de inicialización es la decisión local para autorizar esas operaciones; no es otro rol de usuario ni otra operación GraphQL. La clave también permite consultar, actualizar y desactivar empresas.

## Entregables

- [Análisis](docs/analisis.md): actores, entidades, atributos, relaciones, cardinalidades, reglas y distribución del equipo.
- [Esquema](schema.graphql): los tipos, campos, argumentos y nulabilidad del PDF, sin operaciones adicionales.
- `app/`: configuración, base de datos, modelos, lógica de negocio y GraphQL.
- `tests/`: pruebas mediante HTTP GraphQL y comparación automática con el esquema del PDF.
- [Evidencias](docs/evidencias.md): casos solicitados y resultados reales.

`deactivateCompany` implementa la eliminación lógica especificada en el esquema: conserva los datos y cambia `isActive` a false. `CompanyUser` evita poner companyId en User. Las contraseñas se guardan con Argon2id y nunca se exponen. El administrador sólo gestiona su empresa; el correo es único y no se admiten dos administradores principales.

No se agregan operaciones financieras: el PDF sólo concreta empresas y usuarios. Time y Decimal se declaran como solicita el esquema.

## Verificar

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest -v
.\.venv\Scripts\python.exe -m app.export_schema
```

Las pruebas usan bases SQLite temporales separadas de `app.db`. Al ejecutarse regeneran `docs/evidencias/graphql.json` con operaciones, variables, resultado esperado y respuesta real, ocultando contraseñas y tokens. `pytest.txt` guarda la ejecución de entrega.

## Antes de entregar

Completa en el análisis los nombres y las responsabilidades reales de los cinco integrantes. No se atribuye trabajo a personas no identificadas. La fecha y el medio de entrega se acuerdan con el docente.

Referencias: `session_1_2_actividad.pdf` (páginas 1–7), [GraphQL](https://graphql.org/learn/), [Strawberry con FastAPI](https://strawberry.rocks/docs/integrations/fastapi).

