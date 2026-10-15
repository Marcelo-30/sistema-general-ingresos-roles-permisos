"""Comprueba mínimos sin modificar la base configurada."""
import json
from sqlalchemy import select
from .config import Settings
from .db import database
from .models import Company
from .seed import counts, DEMO_TAX_ID

if __name__ == '__main__':
    engine, sessions = database(Settings.from_env().database_url)
    try:
        with sessions() as db:
            company = db.scalar(select(Company).where(Company.tax_id == DEMO_TAX_ID))
            if company is None:
                raise SystemExit('Ejecuta primero: python -m app.seed')
            actual = counts(db, company.id)
            minimum = dict(accounts=3, income_concepts=5, expense_concepts=5, account_concepts=10, transactions=20)
            print(json.dumps({'companyId':str(company.id),'actual':actual,'minimum':minimum},indent=2))
            if not all(actual[key] >= value for key,value in minimum.items()):
                raise SystemExit('No se cumplen los mínimos.')
            print('Mínimos verificados. Los conteos incluyen registros conservados por eliminación lógica.')
    finally:
        engine.dispose()
