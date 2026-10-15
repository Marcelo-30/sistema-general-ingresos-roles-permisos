"""Secuencia completa de la Unidad II, actividad 4, por GraphQL y SQL."""
from sqlalchemy import func, select

from app import models as m
from app.access import (
    MATRIX as INITIAL_MATRIX,
    CompanyUserRole,
    Permission,
    Role,
    RolePermission,
    initialize,
)
from operations import (
    ACCOUNT,
    ADD_PERMISSION,
    ADMIN,
    ASSIGN_ROLE,
    COMPANY,
    CONCEPT,
    LINK,
    MATRIX,
    REMOVE_PERMISSION,
    ROLES,
    TX,
    USER,
)


def test_configuracion_dinamica_de_cinco_personas(api):
    company = api.call(
        COMPANY, {'input': {'name': 'Empresa de actividad 4'}}, api.bootstrap
    )['createCompany']['id']
    ana = api.call(ADMIN, {'input': {
        'companyId': company, 'name': 'Ana', 'email': 'ana@actividad4.example',
        'password': 'Solo-prueba-actividad-4!',
    }}, api.bootstrap)['createCompanyAdmin']['id']

    catalog = api.call(ROLES, {'actor': ana})
    roles = {row['code']: row['id'] for row in catalog['roles']}
    permissions = {row['code']: row['id'] for row in catalog['permissions']}
    assert set(roles) == set(INITIAL_MATRIX)
    assert len(permissions) == 10

    def matrix(code):
        rows = api.call(MATRIX, {'actor': ana, 'role': roles[code]})['rolePermissions']
        return {row['permission']['code'] for row in rows}

    for code, expected in INITIAL_MATRIX.items():
        assert matrix(code) == set(expected)

    people = {'Ana': ana}
    for person, slug, role in (
        ('Luis', 'luis', 'CONTADOR'), ('María', 'maria', 'CAPTURISTA'),
        ('José', 'jose', 'CAPTURISTA'), ('Pedro', 'pedro', 'CONSULTA'),
    ):
        member = api.call(USER, {'actor': ana, 'input': {
            'companyId': company, 'name': person,
            'email': f'{slug}@actividad4.example',
            'password': 'Solo-prueba-actividad-4!',
        }})['createCompanyUser']['id']
        api.call(ASSIGN_ROLE, {'actor': ana, 'input': {
            'companyUserId': member, 'roleId': roles[role],
        }})
        people[person] = member

    def count(model):
        with api.app.state.sessions() as db:
            return db.scalar(select(func.count()).select_from(model))

    def account(actor, label, code=None):
        return api.call(ACCOUNT, {'actor': actor, 'input': {
            'companyId': company, 'name': label, 'accountType': 'CASH',
        }}, code=code)

    # El contador conserva accounts.write y prepara una cuenta para el movimiento.
    base_account = account(people['Luis'], 'Cuenta base')['createAccount']['id']
    concept = api.call(CONCEPT, {'actor': ana, 'input': {
        'companyId': company, 'name': 'Ingreso actividad 4',
        'conceptType': 'INCOME',
    }})['createConcept']['id']
    api.call(LINK, {'actor': ana, 'input': {
        'accountId': base_account, 'conceptId': concept,
    }})

    before_accounts = count(m.Account)
    account(people['María'], 'Cuenta María rechazada', 'FORBIDDEN')
    account(people['José'], 'Cuenta José rechazada', 'FORBIDDEN')
    assert count(m.Account) == before_accounts

    captain = roles['CAPTURISTA']
    accounts_write = permissions['accounts.write']
    added = api.call(ADD_PERMISSION, {'actor': ana, 'input': {
        'roleId': captain, 'permissionId': accounts_write,
    }})['assignPermissionToRole']
    assert added['isActive'] and 'accounts.write' in matrix('CAPTURISTA')
    account(people['María'], 'Cuenta María aceptada')
    account(people['José'], 'Cuenta José aceptada')
    assert count(m.Account) == before_accounts + 2

    assert api.call(REMOVE_PERMISSION, {
        'actor': ana, 'role': captain, 'permission': accounts_write,
    })['removePermissionFromRole']
    before_accounts = count(m.Account)
    account(people['María'], 'Cuenta María revocada', 'FORBIDDEN')
    account(people['José'], 'Cuenta José revocada', 'FORBIDDEN')
    assert count(m.Account) == before_accounts
    with api.app.state.sessions() as db:
        row = db.scalar(select(RolePermission).where(
            RolePermission.role_id == int(captain),
            RolePermission.permission_id == int(accounts_write),
        ))
        assert row.id == int(added['id']) and not row.is_active

    tx_input = {
        'accountId': base_account, 'conceptId': concept,
        'transactionType': 'INCOME', 'amount': '13.37',
    }
    before_transactions = count(m.Transaction)
    api.call(TX, {'actor': people['Pedro'], 'input': tx_input}, code='FORBIDDEN')
    assert count(m.Transaction) == before_transactions

    old_counter = matrix('CONTADOR')
    old_consulta = matrix('CONSULTA')
    changed = api.call(ASSIGN_ROLE, {'actor': ana, 'input': {
        'companyUserId': people['Pedro'], 'roleId': captain,
    }})['assignRole']
    assert changed['role']['code'] == 'CAPTURISTA'
    api.call(TX, {'actor': people['Pedro'], 'input': tx_input})
    assert count(m.Transaction) == before_transactions + 1
    assert matrix('CONTADOR') == old_counter
    assert matrix('CONSULTA') == old_consulta
    assert all(not code.endswith('.write') for code in old_consulta)
    account(people['Luis'], 'Cuenta Luis después del cambio')
    with api.app.state.sessions() as db:
        rows = list(db.scalars(select(CompanyUserRole).where(
            CompanyUserRole.company_user_id == int(people['Pedro'])
        )))
        assert len([row for row in rows if row.is_active]) == 1
        assert any(row.role.code == 'CONSULTA' and not row.is_active for row in rows)

    consulta = roles['CONSULTA']
    concepts_write = permissions['concepts.write']
    before_pairs = count(RolePermission)
    api.call(ADD_PERMISSION, {'actor': people['José'], 'input': {
        'roleId': consulta, 'permissionId': concepts_write,
    }}, code='FORBIDDEN')
    assert count(RolePermission) == before_pairs
    assert matrix('CONSULTA') == old_consulta

    api.call(ADD_PERMISSION, {'actor': ana, 'input': {
        'roleId': consulta, 'permissionId': concepts_write,
    }})
    assert 'concepts.write' in matrix('CONSULTA')
    api.call(REMOVE_PERMISSION, {
        'actor': ana, 'role': consulta, 'permission': concepts_write,
    })
    assert matrix('CONSULTA') == old_consulta

    # El SELECT final incluye las dos parejas desactivadas; la matriz activa es 26.
    with api.app.state.sessions() as db:
        final_rows = list(db.execute(select(
            Role.code, Permission.code, RolePermission.is_active,
        ).join(RolePermission, Role.id == RolePermission.role_id)
         .join(Permission, Permission.id == RolePermission.permission_id)
         .order_by(Role.id, Permission.id)))
        assert len(final_rows) == 28
        assert sum(bool(active) for _, _, active in final_rows) == 26
        assert {(role, permission) for role, permission, active in final_rows if active} == {
            (role, permission)
            for role, expected in INITIAL_MATRIX.items() for permission in expected
        }
    counts = (count(Role), count(Permission), count(RolePermission))
    initialize(api.app.state.engine, api.app.state.sessions)
    assert (count(Role), count(Permission), count(RolePermission)) == counts == (4, 10, 28)
    assert 'accounts.write' not in matrix('CAPTURISTA')
    assert matrix('CONSULTA') == old_consulta
