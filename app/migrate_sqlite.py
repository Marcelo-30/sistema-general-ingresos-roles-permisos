"""Copia los datos anteriores a MySQL sin cambiar SQLite ni reemplazar filas."""
from pathlib import Path
from sqlalchemy import select, func
from .db import database, lock_operation
from .config import Settings
from .access import initialize, seed_catalogs
from . import models as m


def migrate(source_path, settings):
    if not Path(source_path).is_file():
        raise ValueError('No existe la base SQLite de origen.')
    source, _ = database('sqlite:///'+Path(source_path).resolve().as_posix())
    target, sessions = database(settings.database_url)
    if target.dialect.name != 'mysql':
        raise ValueError('La base de destino debe ser MySQL.')
    initialize(target,sessions)
    models = [m.Company,m.User,m.CompanyUser,m.Account,m.Concept,m.AccountConcept,m.Transaction]
    result={}
    try:
        with source.connect() as old, sessions.begin() as db:
            lock_operation(db)
            if any(db.scalar(select(func.count()).select_from(model)) for model in models):
                raise ValueError('El destino ya contiene datos empresariales; no se sobrescribe. La copia solo admite destino vacío.')
            for model in models:
                rows=[dict(row) for row in old.execute(select(model.__table__)).mappings()]
                if rows:
                    db.execute(model.__table__.insert(),rows)
                result[model.__tablename__]=len(rows)
            seed_catalogs(db)
        return result
    finally:
        source.dispose()
        target.dispose()


if __name__=='__main__':
    import argparse, json
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',default='app.db')
    args=parser.parse_args()
    print(json.dumps(migrate(args.source,Settings.from_env()),indent=2))
    print('SQLite conservado. Membresías anteriores sin rol: CONSULTA.')
