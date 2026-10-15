"""Prepara sin sobrescribir datos la empresa de Ana, Luis, María, José y Pedro."""
import json
import secrets
from pathlib import Path

from sqlalchemy import select

from . import models as m
from .access import CompanyUserRole, Role, assign, initialize, role_by_code
from .config import Settings
from .db import database, lock_operation
from .finance_service import FinanceService


TAX_ID = 'DEMO-PERMISOS-U2-A4'
PEOPLE = (
    ('Ana', 'ADMINISTRADOR', 'ana.permisos@example.com'),
    ('Luis', 'CONTADOR', 'luis.permisos@example.com'),
    ('María', 'CAPTURISTA', 'maria.permisos@example.com'),
    ('José', 'CAPTURISTA', 'jose.permisos@example.com'),
    ('Pedro', 'CONSULTA', 'pedro.permisos@example.com'),
)
PRIVATE = Path('.actividad4-credentials.json')


def prepare(settings):
    engine, sessions = database(settings.database_url)
    initialize(engine, sessions)
    try:
        with sessions.begin() as db:
            lock_operation(db)
            company = db.scalar(select(m.Company).where(m.Company.tax_id == TAX_ID))
            if company is not None and not PRIVATE.exists():
                raise RuntimeError('Existe la empresa demo, pero falta su archivo privado de credenciales.')
            credentials = json.loads(PRIVATE.read_text(encoding='utf-8')) if PRIVATE.exists() else {
                person: secrets.token_urlsafe(24) for person, _, _ in PEOPLE
            }
            if set(credentials) != {person for person, _, _ in PEOPLE}:
                raise RuntimeError('El archivo privado no contiene las cinco credenciales demo.')
            svc = FinanceService(db, settings, {'x-bootstrap-key': settings.bootstrap_key})
            if company is None:
                company = svc.create_company({'name': 'Empresa de configuración de permisos', 'tax_id': TAX_ID})
                ana = svc.create_member({
                    'company_id': company.id, 'name': 'Ana', 'email': PEOPLE[0][2],
                    'password': credentials['Ana'],
                }, True)
            else:
                ana = db.scalar(select(m.CompanyUser).join(m.User).where(
                    m.CompanyUser.company_id == company.id, m.User.email == PEOPLE[0][2]
                ))
                if ana is None:
                    raise RuntimeError('La empresa demo existe sin la membresía de Ana.')
            svc.actor_company_user_id = ana.id
            svc.require('roles.write')
            people = {'Ana': str(ana.id)}
            for person, role, email in PEOPLE[1:]:
                member = db.scalar(select(m.CompanyUser).join(m.User).where(
                    m.CompanyUser.company_id == company.id, m.User.email == email
                ))
                if member is None:
                    member = svc.create_member({
                        'company_id': company.id, 'name': person, 'email': email,
                        'password': credentials[person],
                    }, False)
                    assign(db, member, role_by_code(db, role))
                active = list(db.scalars(select(CompanyUserRole).where(
                    CompanyUserRole.company_user_id == member.id,
                    CompanyUserRole.is_active.is_(True),
                )))
                if len(active) != 1 or active[0].role.code != role:
                    raise RuntimeError(f'{person} ya tiene otro rol; no se cambia automáticamente.')
                people[person] = str(member.id)
            account = db.scalar(select(m.Account).where(
                m.Account.company_id == company.id, m.Account.name_key == 'cuenta base actividad 4'
            ))
            if account is None:
                svc.require('accounts.write')
                account = svc.create_catalog(m.Account, {
                    'company_id': company.id, 'name': 'Cuenta base actividad 4', 'account_type': 'CASH',
                })
            concept = db.scalar(select(m.Concept).where(
                m.Concept.company_id == company.id,
                m.Concept.name_key == 'ingreso actividad 4',
                m.Concept.concept_type == 'INCOME',
            ))
            if concept is None:
                svc.require('concepts.write')
                concept = svc.create_catalog(m.Concept, {
                    'company_id': company.id, 'name': 'Ingreso actividad 4',
                    'concept_type': 'INCOME',
                })
            if svc.relation(account.id, concept.id) is None:
                svc.require('concepts.write')
                svc.assign(account.id, concept.id)
            svc.check_before_commit()
            result = {
                'companyId': str(company.id), 'people': people,
                'roles': {role.code: str(role.id) for role in db.scalars(select(Role))},
                'accountId': str(account.id), 'conceptId': str(concept.id),
            }
        if not PRIVATE.exists():
            PRIVATE.write_text(json.dumps(credentials, ensure_ascii=False, indent=2), encoding='utf-8')
        return result
    finally:
        engine.dispose()


if __name__ == '__main__':
    result = prepare(Settings.from_env())
    path = Path('docs/evidencias/unidad2/actividad4-ids.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print('Contraseñas privadas en .actividad4-credentials.json.')
