"""Carga demostrativa idempotente, transaccional y aislada de datos existentes."""
import json
import os
import secrets
from pathlib import Path
from decimal import Decimal
from sqlalchemy import select, text, func
from .config import Settings
from .db import Base, database, lock_operation
from .access import initialize
from . import models as m
from .finance_service import FinanceService

DEMO_EMAIL = 'actividad4@example.com'
DEMO_TAX_ID = 'DEMO-ACTIVIDAD-4'


def counts(session, cid):
    result = {}
    for label, model, condition in [
        ('accounts', m.Account, m.Account.company_id == cid),
        ('income_concepts', m.Concept, (m.Concept.company_id == cid) & (m.Concept.concept_type == 'INCOME')),
        ('expense_concepts', m.Concept, (m.Concept.company_id == cid) & (m.Concept.concept_type == 'EXPENSE')),
        ('account_concepts', m.AccountConcept, m.AccountConcept.account_id.in_(select(m.Account.id).where(m.Account.company_id == cid))),
        ('transactions', m.Transaction, m.Transaction.account_id.in_(select(m.Account.id).where(m.Account.company_id == cid)))]:
        result[label] = session.scalar(select(func.count()).select_from(model).where(condition))
    return result


def seed(settings, password):
    engine, sessions = database(settings.database_url)
    initialize(engine, sessions)
    try:
        with sessions.begin() as db:
            lock_operation(db)
            svc = FinanceService(db, settings, {'x-bootstrap-key': settings.bootstrap_key})
            company = db.scalar(select(m.Company).where(m.Company.tax_id == DEMO_TAX_ID))
            if company is None:
                company = svc.create_company({'name': 'Empresa ficticia Actividad 4', 'tax_id': DEMO_TAX_ID})
                svc.create_member({'company_id':company.id,'name':'Usuario de demostración',
                                   'email':DEMO_EMAIL,'password':password}, True)
            token, user = svc.login({'email':DEMO_EMAIL,'password':password})
            svc.headers = {'authorization':'Bearer '+token}
            svc.actor_company_user_id = db.scalar(select(m.CompanyUser.id).where(m.CompanyUser.user_id == user.id, m.CompanyUser.company_id == company.id))
            accounts = []
            for label, kind in [('Caja de demostración','CASH'), ('Banco de demostración','DEBIT'), ('Ahorro de demostración','SAVINGS')]:
                obj = db.scalar(select(m.Account).where(m.Account.company_id==company.id, m.Account.name_key==label.casefold()))
                if obj is None:
                    obj = svc.create_catalog(m.Account, {'company_id':company.id,'name':label,'account_type':kind})
                accounts.append(obj)
            concepts = []
            for kind, names in [('INCOME',['Ventas','Servicios','Intereses','Aportaciones','Reembolsos']),
                                ('EXPENSE',['Renta','Papelería','Servicios públicos','Transporte','Comisiones'])]:
                for label in names:
                    obj = db.scalar(select(m.Concept).where(m.Concept.company_id==company.id,
                                    m.Concept.concept_type==kind, m.Concept.name_key==label.casefold()))
                    if obj is None:
                        obj = svc.create_catalog(m.Concept, {'company_id':company.id,'name':label,'concept_type':kind})
                    concepts.append(obj)
            for i, concept in enumerate(concepts):
                account = accounts[i % len(accounts)]
                link = svc.relation(account.id, concept.id)
                if link is None:
                    svc.assign(account.id, concept.id)
                for j in range(2):
                    marker = f'demo-a4-{i:02}-{j}'
                    exists = db.scalar(select(m.Transaction.id).where(
                        m.Transaction.account_id==account.id, m.Transaction.short_description==marker))
                    if exists is None:
                        svc.create_transaction({'account_id':account.id,'concept_id':concept.id,
                                                'transaction_type':concept.concept_type,
                                                'amount':Decimal('100.25') + Decimal(i*10+j),
                                                'short_description':marker})
            return {'companyId':str(company.id), **counts(db,company.id)}
    finally:
        engine.dispose()


if __name__ == '__main__':
    credentials_path = Path('.demo-credentials.json')
    if credentials_path.exists():
        password = json.loads(credentials_path.read_text(encoding='utf-8'))['password']
    else:
        password = os.getenv('DEMO_PASSWORD') or secrets.token_urlsafe(24)
        with credentials_path.open('x',encoding='utf-8') as file:
            json.dump({'email':DEMO_EMAIL,'password':password},file)
        if os.name != 'nt':
            credentials_path.chmod(0o600)
    print(json.dumps(seed(Settings.from_env(), password), ensure_ascii=False, indent=2))
    print('Credenciales locales en .demo-credentials.json (no versionar ni compartir).')
