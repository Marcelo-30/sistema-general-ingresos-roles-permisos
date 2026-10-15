from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter
from .config import Settings
from .db import Base, database
from .schema import schema
from .access import initialize


def create_app(settings: Settings):
    app = FastAPI(title='Sistema General de Ingresos: roles y permisos', debug=False)
    engine, sessions = database(settings.database_url)
    initialize(engine, sessions)
    app.state.engine, app.state.sessions, app.state.settings = engine, sessions, settings
    app.include_router(GraphQLRouter(schema, graphql_ide='graphiql'), prefix='/graphql')
    return app
