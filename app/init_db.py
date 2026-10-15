from .config import Settings
from .db import Base, database
from . import models
from .access import initialize

if __name__ == '__main__':
    engine, sessions = database(Settings.from_env().database_url)
    initialize(engine, sessions)
    engine.dispose()
    print('Base de datos inicializada.')
