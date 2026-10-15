from sqlalchemy import create_engine, event, Text, text, DateTime
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import DeclarativeBase, sessionmaker

Timestamp = DateTime().with_variant(DATETIME(fsp=6), 'mysql')


class Base(DeclarativeBase):
    type_annotation_map = {str: Text()}


def database(url):
    sqlite = url.startswith('sqlite:')
    engine = create_engine(url, pool_pre_ping=True,
                           connect_args={'check_same_thread': False, 'timeout': 30} if sqlite else {})

    @event.listens_for(engine, 'connect')
    def configure(connection, _):
        if sqlite:
            connection.execute('PRAGMA foreign_keys=ON')

    return engine, sessionmaker(engine, expire_on_commit=False)


def lock_operation(session):
    """Serializa autorización y cambios; evita revocaciones entre check y commit."""
    if session.bind.dialect.name == 'sqlite':
        session.execute(text('BEGIN IMMEDIATE'))
    else:
        # Un orden común evita inversiones de bloqueos entre distintas operaciones.
        session.execute(text('SELECT id FROM roles ORDER BY id FOR UPDATE')).all()
