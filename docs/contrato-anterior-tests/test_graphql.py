from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import jwt
import pytest
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from app import models as m
from app.schema import schema, parse_time, serialize_time
from conftest import records, redact

COMPANY = 'mutation($input:CreateCompanyInput!){createCompany(input:$input){id name email legalName isActive createdAt updatedAt}}'
UPDATE = 'mutation($input:UpdateCompanyInput!){updateCompany(input:$input){id name email legalName isActive createdAt updatedAt}}'
ADMIN = 'mutation($input:CreateCompanyAdminInput!){createCompanyAdmin(input:$input){id companyId userId isAdmin isActive company{id} user{id name email emailVerified isActive}}}'
USER = 'mutation($input:CreateCompanyUserInput!){createCompanyUser(input:$input){id companyId userId isAdmin isActive user{id email}}}'
LOGIN = 'mutation($input:LoginInput!){login(input:$input){token tokenType user{id name email}}}'
MEMBERS = 'query($id:ID!){companyUsers(companyId:$id){id isAdmin isActive company{id} user{id name email isActive}}}'
DEACTIVATE = 'mutation($id:ID!){deactivateCompanyUser(id:$id){id isActive}}'
PASSWORD = 'Academico-2026!'


def company(api, label='Empresa'):
    return api.call(COMPANY, {'input': {'name': label}}, api.bootstrap)['createCompany']['id']


def credentials(cid, mail='admin@example.com'):
    return {'companyId': cid, 'name': 'Persona', 'email': mail, 'password': PASSWORD}


def login(api, mail='admin@example.com', code=None, password=PASSWORD):
    result = api.call(LOGIN, {'input': {'email': mail, 'password': password}}, code=code)
    return {'Authorization': 'Bearer ' + result['login']['token']} if result else None


def setup(api):
    cid = company(api)
    member = api.call(ADMIN, {'input': credentials(cid)}, api.bootstrap)['createCompanyAdmin']
    return cid, member, login(api)


def test_company_crud_filter_null_dates(api):
    cid = company(api)
    other = company(api, 'Otra')
    query = 'query($id:ID!){company(id:$id){id name email createdAt updatedAt}}'
    initial = api.call(query, {'id': cid}, api.bootstrap)['company']
    updated = api.call(UPDATE, {'input': {'id': cid, 'email': 'COMPANY@EXAMPLE.COM', 'legalName': 'Legal'}}, api.bootstrap)['updateCompany']
    assert updated['email'] == 'company@example.com'
    assert updated['createdAt'] == initial['createdAt']
    assert updated['updatedAt'] > initial['updatedAt']
    updated = api.call(UPDATE, {'input': {'id': cid, 'legalName': None}}, api.bootstrap)['updateCompany']
    assert updated['legalName'] is None and updated['email'] == 'company@example.com'
    api.call('mutation($id:ID!){deactivateCompany(id:$id){isActive}}', {'id': cid}, api.bootstrap)
    for flag, expected in [(True, [other]), (False, [cid, other]), (None, [cid, other])]:
        actual = api.call('query($flag:Boolean){companies(activeOnly:$flag){id}}', {'flag': flag}, api.bootstrap)
        assert [x['id'] for x in actual['companies']] == expected
    assert api.call(query, {'id': '9999'}, api.bootstrap)['company'] is None
    api.call(UPDATE, {'input': {'id': '9999', 'name': 'X'}}, api.bootstrap, 'NOT_FOUND')
    api.call(UPDATE, {'input': {'id': cid, 'isActive': True}}, api.bootstrap)


@pytest.mark.parametrize('fields', [{'name': ' '}, {'name': 'X', 'email': 'mal'}, {'name': 'X', 'phone': ''}])
def test_invalid_company(api, fields):
    api.call(COMPANY, {'input': fields}, api.bootstrap, 'BAD_INPUT')


@pytest.mark.parametrize('fields', [{'name': None}, {'isActive': None}, {'name': ''}])
def test_invalid_update(api, fields):
    api.call(UPDATE, {'input': {'id': company(api), **fields}}, api.bootstrap, 'BAD_INPUT')


def test_admin_users_duplicates_and_transaction(api):
    cid, admin, auth = setup(api)
    assert admin['isAdmin'] and not admin['user']['emailVerified']
    api.call(ADMIN, {'input': credentials(cid, 'second@example.com')}, api.bootstrap, 'CONFLICT')
    result = api.call(USER, {'input': credentials(cid, 'MEMBER@EXAMPLE.COM')}, auth)['createCompanyUser']
    assert not result['isAdmin'] and result['user']['email'] == 'member@example.com'
    api.call(USER, {'input': credentials(cid, 'member@example.com')}, auth, 'CONFLICT')
    api.call(USER, {'input': credentials(cid, ' ADMIN@EXAMPLE.COM ')}, auth, 'CONFLICT')
    api.call(ADMIN, {'input': credentials('99999')}, api.bootstrap, 'NOT_FOUND')
    api.call(USER, {'input': credentials('99999')}, auth, 'FORBIDDEN')
    invalid = credentials(cid, 'short@example.com')
    invalid['password'] = '123'
    api.call(USER, {'input': invalid}, auth, 'BAD_INPUT')
    with api.app.state.sessions() as db:
        assert db.scalar(select(func.count()).select_from(m.User)) == 2
        assert db.get(m.User, int(admin['userId'])).password_hash.startswith('$argon2id$')


def test_login_and_tokens(api):
    cid, _, auth = setup(api)
    login(api, password='incorrecta', code='UNAUTHENTICATED')
    login(api, mail='nobody@example.com', code='UNAUTHENTICATED')
    for token in ['bad', jwt.encode({'sub': '1', 'iat': m.now() - timedelta(hours=2),
                                    'exp': m.now() - timedelta(hours=1), 'iss': 'empresa-api', 'aud': 'empresa-api'},
                                   api.settings.jwt_secret, algorithm='HS256')]:
        api.call(MEMBERS, {'id': cid}, {'Authorization': 'Bearer ' + token}, 'UNAUTHENTICATED')
    api.call(MEMBERS, {'id': cid}, auth)


def test_authorization_and_tenant_isolation(api):
    cid, admin, auth = setup(api)
    second = company(api, 'Segunda')
    other = api.call(ADMIN, {'input': credentials(second, 'other@example.com')}, api.bootstrap)['createCompanyAdmin']
    api.call(COMPANY, {'input': {'name': 'Pública'}}, code='FORBIDDEN')
    api.call(ADMIN, {'input': credentials(company(api, 'Vacía'))}, code='FORBIDDEN')
    api.call(MEMBERS, {'id': cid}, code='UNAUTHENTICATED')
    api.call(USER, {'input': credentials(cid, 'new@example.com')}, code='UNAUTHENTICATED')
    api.call(MEMBERS, {'id': second}, auth, 'FORBIDDEN')
    api.call(USER, {'input': credentials(second, 'new@example.com')}, auth, 'FORBIDDEN')
    api.call(DEACTIVATE, {'id': other['id']}, auth, 'FORBIDDEN')
    api.call(DEACTIVATE, {'id': admin['id']}, auth, 'CONFLICT')
    member = api.call(USER, {'input': credentials(cid, 'normal@example.com')}, auth)['createCompanyUser']
    normal_auth = login(api, 'normal@example.com')
    api.call(MEMBERS, {'id': cid}, normal_auth, 'FORBIDDEN')
    api.call(DEACTIVATE, {'id': member['id']}, normal_auth, 'FORBIDDEN')
    api.call('query{companies{id}}', headers=auth, code='FORBIDDEN')


def test_inactive_states(api):
    cid, admin, auth = setup(api)
    member = api.call(USER, {'input': credentials(cid, 'member@example.com')}, auth)['createCompanyUser']
    api.call(DEACTIVATE, {'id': member['id']}, auth)
    login(api, 'member@example.com', code='FORBIDDEN')
    assert any(not x['isActive'] for x in api.call(MEMBERS, {'id': cid}, auth)['companyUsers'])
    with api.app.state.sessions.begin() as db:
        db.get(m.CompanyUser, int(admin['id'])).is_active = False
    api.call(MEMBERS, {'id': cid}, auth, 'FORBIDDEN')
    login(api, code='FORBIDDEN')
    with api.app.state.sessions.begin() as db:
        db.get(m.CompanyUser, int(admin['id'])).is_active = True
        db.get(m.User, int(admin['userId'])).is_active = False
    login(api, code='UNAUTHENTICATED')
    api.call(MEMBERS, {'id': cid}, auth, 'UNAUTHENTICATED')
    with api.app.state.sessions.begin() as db:
        db.get(m.User, int(admin['userId'])).is_active = True
    api.call(UPDATE, {'input': {'id': cid, 'isActive': False}}, api.bootstrap)
    login(api, code='FORBIDDEN')
    api.call(MEMBERS, {'id': cid}, auth, 'FORBIDDEN')
    api.call(USER, {'input': credentials(cid, 'blocked@example.com')}, auth, 'FORBIDDEN')
    empty = company(api, 'Inactiva')
    api.call(UPDATE, {'input': {'id': empty, 'isActive': False}}, api.bootstrap)
    api.call(ADMIN, {'input': credentials(empty, 'blocked@example.com')}, api.bootstrap, 'FORBIDDEN')
    api.call(UPDATE, {'input': {'id': cid, 'isActive': True}}, api.bootstrap)
    api.call(MEMBERS, {'id': cid}, auth)


def test_concurrent_admin_and_db_constraints(api):
    cid = company(api)
    def attempt(i):
        return api.client.post('/graphql', json={'query': ADMIN, 'variables': {
            'input': credentials(cid, f'admin{i}@example.com')}}, headers=api.bootstrap).json()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, [1, 2]))
    for i, result in enumerate(results, 1):
        records.append({'caso': 'test_concurrent_admin_and_db_constraints', 'operacion': ADMIN,
                        'variables': redact({'input': credentials(cid, f'admin{i}@example.com')}),
                        'cabeceras': ['X-Bootstrap-Key'],
                        'esperado': 'Una solicitud exitosa y la otra CONFLICT; cero cuentas huérfanas',
                        'real': redact(result)})
    assert sum('errors' not in r for r in results) == 1
    assert [r['errors'][0]['extensions']['code'] for r in results if 'errors' in r] == ['CONFLICT']
    with api.app.state.sessions() as db:
        assert db.scalar(select(func.count()).select_from(m.User)) == 1
        existing = db.scalar(select(m.CompanyUser))
        uid, mid = existing.user_id, existing.id
    for duplicate_admin in [False, True]:
        with pytest.raises(IntegrityError), api.app.state.sessions.begin() as db:
            user_id = uid
            if duplicate_admin:
                new = m.User(name='Rollback', email='rollback@example.com', password_hash='test-only')
                db.add(new)
                db.flush()
                user_id = new.id
            db.add(m.CompanyUser(company_id=int(cid), user_id=user_id, is_admin=duplicate_admin))
            db.flush()
    with api.app.state.sessions() as db:
        assert db.scalar(select(func.count()).select_from(m.User)) == 1


def test_schema_no_passwords_and_scalars(api):
    result = api.call('{__type(name:"User"){fields{name}}}')
    fields = {f['name'] for f in result['__type']['fields']}
    assert not fields & {'password', 'passwordHash', 'companyId'}
    assert {'Time', 'Decimal'} <= set(schema._schema.type_map)
    assert serialize_time(parse_time('2026-01-01T00:00:00Z')) == '2026-01-01T00:00:00Z'
    decimal = schema._schema.type_map['Decimal']
    assert str(decimal.parse_value('123.45')) == '123.45'
    assert decimal.serialize(decimal.parse_value('123.45')) == '123.45'


def test_graphql_transaction_rolls_back_partial_registration(api):
    from sqlalchemy import text
    cid, _, auth = setup(api)
    # Simulate a failure after User insertion but before CompanyUser insertion.
    with api.app.state.engine.begin() as connection:
        connection.execute(text("CREATE TRIGGER fail_membership BEFORE INSERT ON company_users "
                                "BEGIN SELECT RAISE(ABORT, 'simulated failure'); END"))
    api.call(USER, {'input': credentials(cid, 'rollback@example.com')}, auth, 'CONFLICT')
    with api.app.state.sessions() as db:
        assert db.scalar(select(func.count()).select_from(m.User)) == 1
        assert db.scalar(select(func.count()).select_from(m.CompanyUser)) == 1


def test_many_to_many_and_company_specific_inactivation(api):
    first, admin, first_auth = setup(api)
    second = company(api, 'Segunda')
    api.call(ADMIN, {'input': credentials(second, 'second@example.com')}, api.bootstrap)
    second_auth = login(api, 'second@example.com')
    member = api.call(USER, {'input': credentials(first, 'shared@example.com')}, first_auth)['createCompanyUser']
    # No public invitation operation was requested; seed a second membership explicitly.
    with api.app.state.sessions.begin() as db:
        db.add(m.CompanyUser(company_id=int(second), user_id=int(member['userId'])))
    api.call(DEACTIVATE, {'id': member['id']}, first_auth)
    login(api, 'shared@example.com')
    visible = api.call(MEMBERS, {'id': second}, second_auth)['companyUsers']
    assert any(x['user']['id'] == member['userId'] and x['isActive'] for x in visible)


def test_invalid_ids_and_signed_token(api):
    cid, _, auth = setup(api)
    api.call('query($id:ID!){company(id:$id){id}}', {'id': 'invalid'}, api.bootstrap, 'BAD_INPUT')
    api.call(DEACTIVATE, {'id': '99999'}, auth, 'FORBIDDEN')
    invalid = jwt.encode({'sub': '1', 'iat': m.now(), 'exp': m.now() + timedelta(hours=1),
                          'iss': 'empresa-api', 'aud': 'empresa-api'}, 'unrelated-test-secret-of-32-characters', algorithm='HS256')
    api.call(MEMBERS, {'id': cid}, {'Authorization': 'Bearer ' + invalid}, 'UNAUTHENTICATED')
