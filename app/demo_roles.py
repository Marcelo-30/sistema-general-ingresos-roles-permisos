"""Preparación idempotente de la empresa ficticia para comprobar los cuatro roles."""
import json
import secrets
from pathlib import Path
from sqlalchemy import select
from .config import Settings
from .db import database,lock_operation
from .access import initialize,Role,CompanyUserRole,role_by_code,assign
from .finance_service import FinanceService
from . import models as m


def prepare(settings):
    private=Path('.roles-demo.json')
    if private.exists():
        passwords=json.loads(private.read_text(encoding='utf-8'))
    else:
        passwords={kind:secrets.token_urlsafe(24) for kind in ('ADMINISTRADOR','CONTADOR','CAPTURISTA','CONSULTA')}
        private.write_text(json.dumps(passwords),encoding='utf-8')
    engine,sessions=database(settings.database_url)
    initialize(engine,sessions)
    try:
        with sessions.begin() as db:
            lock_operation(db)
            svc=FinanceService(db,settings,{'x-bootstrap-key':settings.bootstrap_key})
            company=db.scalar(select(m.Company).where(m.Company.tax_id=='DEMO-ROLES-U2'))
            if company is None:
                company=svc.create_company({'name':'Empresa de evidencia RBAC','tax_id':'DEMO-ROLES-U2'})
                admin=svc.create_member({'company_id':company.id,'name':'Administrador RBAC','email':'admin.roles@example.com','password':passwords['ADMINISTRADOR']},True)
            else:
                admin=db.scalar(select(m.CompanyUser).where(m.CompanyUser.company_id==company.id,m.CompanyUser.is_admin.is_(True)))
            svc.actor_company_user_id=admin.id
            actors={'ADMINISTRADOR':str(admin.id)}
            svc.require('roles.write')
            for role in ('CONTADOR','CAPTURISTA','CONSULTA'):
                email=role.lower()+'.roles@example.com'
                member=db.scalar(select(m.CompanyUser).join(m.User).where(m.CompanyUser.company_id==company.id,m.User.email==email))
                if member is None:
                    member=svc.create_member({'company_id':company.id,'name':role.capitalize()+' RBAC','email':email,'password':passwords[role]},False)
                    assign(db,member,role_by_code(db,role))
                actors[role]=str(member.id)
            account=db.scalar(select(m.Account).where(m.Account.company_id==company.id,m.Account.name_key=='cuenta de evidencia'))
            if account is None:
                svc.require('accounts.write')
                account=svc.create_catalog(m.Account,{'company_id':company.id,'name':'Cuenta de evidencia','account_type':'CASH'})
            concepts={}
            for kind in ('INCOME','EXPENSE'):
                concept=db.scalar(select(m.Concept).where(m.Concept.company_id==company.id,m.Concept.name_key==kind.lower(),m.Concept.concept_type==kind))
                if concept is None:
                    svc.require('concepts.write')
                    concept=svc.create_catalog(m.Concept,{'company_id':company.id,'name':kind,'concept_type':kind})
                if svc.relation(account.id,concept.id) is None:
                    svc.require('concepts.write')
                    svc.assign(account.id,concept.id)
                concepts[kind]=str(concept.id)
            svc.check_before_commit()
            return {'companyId':str(company.id),'actors':actors,'roles':{r.code:str(r.id) for r in db.scalars(select(Role))},'accountId':str(account.id),'concepts':concepts}
    finally:
        engine.dispose()


if __name__=='__main__':
    result=prepare(Settings.from_env())
    path=Path('docs/evidencias/unidad2/demo-ids.json')
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
    print('Contraseñas locales en .roles-demo.json; no versionar.')
