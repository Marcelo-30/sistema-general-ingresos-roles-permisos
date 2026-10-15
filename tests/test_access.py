from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
import pytest
from sqlalchemy import select,func,text
from sqlalchemy.exc import IntegrityError
from app import models as m
from app.access import Role,Permission,RolePermission,CompanyUserRole,initialize,MATRIX as INITIAL_MATRIX
from operations import *

PASSWORD='Solo-pruebas-2026!'


def user_input(cid,email):
    return {'companyId':cid,'name':'Persona de prueba','email':email,'password':PASSWORD}


def make_company(api,label='Empresa',email='admin@example.com'):
    cid=api.call(COMPANY,{'input':{'name':label}},api.bootstrap)['createCompany']['id']
    admin=api.call(ADMIN,{'input':user_input(cid,email)},api.bootstrap)['createCompanyAdmin']
    return cid,admin


@pytest.fixture
def data(api):
    cid,admin=make_company(api)
    aid=admin['id']
    catalog=api.call(ROLES,{'actor':aid})
    roles={x['code']:x['id'] for x in catalog['roles']}
    permissions={x['code']:x['id'] for x in catalog['permissions']}
    members={'ADMINISTRADOR':aid}
    for role in ('CONTADOR','CAPTURISTA','CONSULTA'):
        member=api.call(USER,{'actor':aid,'input':user_input(cid,role.lower()+'@example.com')})['createCompanyUser']
        api.call(ASSIGN_ROLE,{'actor':aid,'input':{'companyUserId':member['id'],'roleId':roles[role]}})
        members[role]=member['id']
    account=api.call(ACCOUNT,{'actor':aid,'input':{'companyId':cid,'name':'Caja','accountType':'CASH'}})['createAccount']['id']
    concepts={}
    for kind in ('INCOME','EXPENSE'):
        concept=api.call(CONCEPT,{'actor':aid,'input':{'companyId':cid,'name':kind,'conceptType':kind}})['createConcept']['id']
        api.call(LINK,{'actor':aid,'input':{'accountId':account,'conceptId':concept}})
        concepts[kind]=concept
    return dict(cid=cid,admin=aid,roles=roles,permissions=permissions,members=members,account=account,concepts=concepts)


def tx_input(data,amount='1.00',kind='INCOME',**extra):
    return {'accountId':data['account'],'conceptId':data['concepts'][kind],'transactionType':kind,'amount':amount,**extra}


def count(api,model):
    with api.app.state.sessions() as db:
        return db.scalar(select(func.count()).select_from(model))


def test_exact_matrix_and_membership_roles(api,data):
    assert set(data['roles'])=={'ADMINISTRADOR','CONTADOR','CAPTURISTA','CONSULTA'}
    assert len(data['permissions'])==10
    for role,expected in INITIAL_MATRIX.items():
        rows=api.call(MATRIX,{'actor':data['admin'],'role':data['roles'][role]})['rolePermissions']
        assert {x['permission']['code'] for x in rows}==set(expected)
    with api.app.state.sessions() as db:
        for member in db.scalars(select(m.CompanyUser)):
            rows=list(db.scalars(select(CompanyUserRole).where(CompanyUserRole.company_user_id==member.id,CompanyUserRole.is_active.is_(True))))
            assert len(rows)==1 and rows[0].role.is_active
        assert db.get(m.CompanyUser,int(data['admin'])).is_admin
        assert db.scalar(select(CompanyUserRole).where(CompanyUserRole.company_user_id==int(data['admin']))).role.code=='ADMINISTRADOR'


def test_capturista_records_consulta_cannot_and_zero_partial_writes(api,data):
    before=count(api,m.Transaction)
    result=api.call(TX,{'actor':data['members']['CAPTURISTA'],'input':tx_input(data)})['createTransaction']
    with api.app.state.sessions() as db:
        assert result['capturedBy']==str(db.get(m.CompanyUser,int(data['members']['CAPTURISTA'])).user_id)
    assert count(api,m.Transaction)==before+1
    api.call(TX,{'actor':data['members']['CONSULTA'],'input':tx_input(data)},code='FORBIDDEN')
    assert count(api,m.Transaction)==before+1


def test_contador_create_capturista_rejected_then_role_change(api,data):
    inp={'companyId':data['cid'],'name':'Banco','accountType':'DEBIT'}
    api.call(ACCOUNT,{'actor':data['members']['CONTADOR'],'input':inp})
    before=count(api,m.Account)
    inp['name']='Cuenta promovida'
    capt=data['members']['CAPTURISTA']
    api.call(ACCOUNT,{'actor':capt,'input':inp},code='FORBIDDEN')
    assert count(api,m.Account)==before
    changed=api.call(ASSIGN_ROLE,{'actor':data['admin'],'input':{'companyUserId':capt,'roleId':data['roles']['CONTADOR']}})['assignRole']
    assert changed['role']['code']=='CONTADOR'
    api.call(ACCOUNT,{'actor':capt,'input':inp})
    again=api.call(ASSIGN_ROLE,{'actor':data['admin'],'input':{'companyUserId':capt,'roleId':data['roles']['CAPTURISTA']}})['assignRole']
    assert again['role']['code']=='CAPTURISTA'
    with api.app.state.sessions() as db:
        assert db.scalar(select(func.count()).select_from(CompanyUserRole).where(CompanyUserRole.company_user_id==int(capt),CompanyUserRole.is_active.is_(True)))==1


def test_second_admin_is_rejected_without_orphan_user(api,data):
    before=count(api,m.User)
    api.call(ADMIN,{'input':user_input(data['cid'],'second@example.com')},api.bootstrap,'CONFLICT')
    assert count(api,m.User)==before


def test_restart_idempotency_and_preserves_revocations(api,data):
    role=data['roles']['CAPTURISTA']; permission=data['permissions']['transactions.write']
    inp={'actor':data['admin'],'input':{'roleId':role,'permissionId':permission}}
    api.call(ADD_PERMISSION,inp,code='CONFLICT')
    old=next(x for x in api.call(MATRIX,{'actor':data['admin'],'role':role})['rolePermissions'] if x['permission']['id']==permission)
    assert api.call(REMOVE_PERMISSION,{'actor':data['admin'],'role':role,'permission':permission})['removePermissionFromRole']
    before=[count(api,x) for x in (Role,Permission,RolePermission,CompanyUserRole)]
    initialize(api.app.state.engine,api.app.state.sessions)
    initialize(api.app.state.engine,api.app.state.sessions)
    assert [count(api,x) for x in (Role,Permission,RolePermission,CompanyUserRole)]==before
    api.call(TX,{'actor':data['members']['CAPTURISTA'],'input':tx_input(data)},code='FORBIDDEN')
    restored=api.call(ADD_PERMISSION,inp)['assignPermissionToRole']
    assert restored['id']==old['id']
    assert count(api,RolePermission)==26


def test_all_revoked_role_not_restored_at_startup(api,data):
    role=data['roles']['CONSULTA']
    for row in api.call(MATRIX,{'actor':data['admin'],'role':role})['rolePermissions']:
        api.call(REMOVE_PERMISSION,{'actor':data['admin'],'role':role,'permission':row['permission']['id']})
    initialize(api.app.state.engine,api.app.state.sessions)
    assert api.call(MATRIX,{'actor':data['admin'],'role':role})['rolePermissions']==[]


@pytest.mark.parametrize('target',['role','membership','company','user','permission','relation'])
def test_inactive_nodes_never_authorize(api,data,target):
    actor=data['members']['CAPTURISTA']
    with api.app.state.sessions.begin() as db:
        objects={
            'role':db.get(Role,int(data['roles']['CAPTURISTA'])),
            'membership':db.get(m.CompanyUser,int(actor)),
            'company':db.get(m.Company,int(data['cid'])),
            'user':db.get(m.CompanyUser,int(actor)).user,
            'permission':db.get(Permission,int(data['permissions']['transactions.write'])),
            'relation':db.scalar(select(RolePermission).where(RolePermission.role_id==int(data['roles']['CAPTURISTA']),RolePermission.permission_id==int(data['permissions']['transactions.write']))),
        }
        objects[target].is_active=False
    api.call(TX,{'actor':actor,'input':tx_input(data)},code='FORBIDDEN')
    assert count(api,m.Transaction)==0


def test_is_admin_is_not_a_permission_bypass(api,data):
    with api.app.state.sessions.begin() as db:
        row=db.scalar(select(CompanyUserRole).where(CompanyUserRole.company_user_id==int(data['admin']),CompanyUserRole.is_active.is_(True)))
        row.role_id=int(data['roles']['CONSULTA'])
    api.call(ACCOUNT,{'actor':data['admin'],'input':{'companyId':data['cid'],'name':'No permitido','accountType':'CASH'}},code='FORBIDDEN')
    assert count(api,m.Account)==1


def test_cross_company_resources_and_memberships(api,data):
    cid,other=make_company(api,'Otra empresa','other@example.com')
    for query,variables in [
        (ACCOUNTS,{'id':data['cid']}),(CONCEPTS,{'id':data['cid']}),(MEMBERS,{'id':data['cid']}),
        (TXS,{'a':data['account']}),(BALANCE,{'a':data['account']}),
        (TX,{'input':tx_input(data)}),(ACCOUNT,{'input':{'companyId':data['cid'],'name':'X','accountType':'CASH'}}),
        (CONCEPT,{'input':{'companyId':data['cid'],'name':'X','conceptType':'INCOME'}}),
        (LINK,{'input':{'accountId':data['account'],'conceptId':data['concepts']['INCOME']}}),
        (ASSIGN_ROLE,{'input':{'companyUserId':data['members']['CAPTURISTA'],'roleId':data['roles']['CONTADOR']}}),
    ]:
        api.call(query,{'actor':other['id'],**variables},code='FORBIDDEN')
    assert api.call(TXS,{'actor':other['id']})['transactions']==[]
    # Los catálogos de roles sí son globales.
    assert len(api.call(ROLES,{'actor':other['id']})['roles'])==4


def test_catalog_crud_codes_filters_and_no_physical_delete(api,data):
    actor=data['admin']
    role=api.call(CREATE_ROLE,{'actor':actor,'input':{'code':' auditor ','name':'Auditor','description':'Rol de ejemplo'}})['createRole']
    assert role['code']=='AUDITOR'
    api.call(CREATE_ROLE,{'actor':actor,'input':{'code':'AUDITOR','name':'Duplicado'}},code='CONFLICT')
    p=api.call(CREATE_PERMISSION,{'actor':actor,'input':{'code':'audit.read','name':'Leer auditoría'}})['createPermission']
    api.call(CREATE_PERMISSION,{'actor':actor,'input':{'code':'AUDIT.READ','name':'Duplicado'}},code='CONFLICT')
    api.call(DEACTIVATE_ROLE,{'actor':actor,'id':role['id']})
    assert count(api,Role)==5
    query='query($a:ID!,$active:Boolean){roles(actorCompanyUserId:$a,activeOnly:$active){id}}'
    assert len(api.call(query,{'a':actor,'active':True})['roles'])==4
    assert len(api.call(query,{'a':actor,'active':False})['roles'])==5
    api.call(ASSIGN_ROLE,{'actor':actor,'input':{'companyUserId':data['members']['CONSULTA'],'roleId':role['id']}},code='BAD_INPUT')
    api.call(DEACTIVATE_ROLE,{'actor':actor,'id':data['roles']['CONSULTA']},code='CONFLICT')
    for query,values in [(CREATE_ROLE,{'input':{'code':'X','name':'X'}}),(CREATE_PERMISSION,{'input':{'code':'x.read','name':'X'}}),(DEACTIVATE_ROLE,{'id':role['id']})]:
        api.call(query,{'actor':data['members']['CONTADOR'],**values},code='FORBIDDEN')


def test_precommit_authorization_rolls_back_self_revocation(api,data):
    # El primer check pasa; quitarse roles.write debe fallar en el segundo check.
    before=count(api,RolePermission)
    api.call(REMOVE_PERMISSION,{'actor':data['admin'],'role':data['roles']['ADMINISTRADOR'],'permission':data['permissions']['roles.write']},code='FORBIDDEN')
    assert count(api,RolePermission)==before
    assert 'roles.write' in {x['permission']['code'] for x in api.call(MATRIX,{'actor':data['admin'],'role':data['roles']['ADMINISTRADOR']})['rolePermissions']}


def test_previous_membership_transition_is_consulta_not_admin(api):
    from app.service import hasher
    with api.app.state.sessions.begin() as db:
        company=m.Company(name='Anterior')
        user=m.User(name='Anterior',email='old@example.com',password_hash=hasher.hash(PASSWORD))
        member=m.CompanyUser(company=company,user=user,is_admin=True)
        db.add(member); db.flush(); mid=member.id
    initialize(api.app.state.engine,api.app.state.sessions)
    with api.app.state.sessions() as db:
        row=db.scalar(select(CompanyUserRole).where(CompanyUserRole.company_user_id==mid))
        assert row.role.code=='CONSULTA'
        assert row.company_user.is_admin
    api.call(ROLES,{'actor':str(mid)},code='FORBIDDEN')


def test_database_unique_relations_and_one_active_role(api,data):
    with pytest.raises(IntegrityError),api.app.state.sessions.begin() as db:
        db.add(RolePermission(role_id=int(data['roles']['CAPTURISTA']),permission_id=int(data['permissions']['transactions.write'])))
        db.flush()
    with pytest.raises(IntegrityError),api.app.state.sessions.begin() as db:
        db.add(CompanyUserRole(company_user_id=int(data['admin']),role_id=int(data['roles']['CONTADOR'])))
        db.flush()
    with pytest.raises(IntegrityError),api.app.state.sessions.begin() as db:
        db.add(m.CompanyUser(company_id=int(data['cid']),user_id=int(data['members']['CONSULTA']),is_admin=True))
        db.flush()


def test_concurrent_role_changes_leave_one_active(api,data):
    def change(role):
        return api.client.post('/graphql',json={'query':ASSIGN_ROLE,'variables':{'actor':data['admin'],'input':{'companyUserId':data['members']['CAPTURISTA'],'roleId':data['roles'][role]}}}).json()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(change,['CONTADOR','CONSULTA']))
    assert all('errors' not in x for x in results),results
    with api.app.state.sessions() as db:
        assert db.scalar(select(func.count()).select_from(CompanyUserRole).where(CompanyUserRole.company_user_id==int(data['members']['CAPTURISTA']),CompanyUserRole.is_active.is_(True)))==1


def test_login_unchanged_hash_not_public_and_actor_required(api,data):
    result=api.call(LOGIN,{'input':{'email':'admin@example.com','password':PASSWORD}})['login']
    assert result['token'] and result['tokenType']=='Bearer'
    api.call(LOGIN,{'input':{'email':'admin@example.com','password':'incorrecto'}},code='UNAUTHENTICATED')
    with api.app.state.sessions() as db:
        assert db.get(m.CompanyUser,int(data['admin'])).user.password_hash.startswith('$argon2id$')
    fields=api.call('{__type(name:"User"){fields{name}}}')['__type']['fields']
    assert not {'password','passwordHash'} & {f['name'] for f in fields}
    api.call('{roles{code}}',code='GRAPHQL_VALIDATION')
    api.call(ROLES,{'actor':'999999'},code='FORBIDDEN')
    # Mecanismo académico: actor explícito funciona sin cabecera JWT.
    assert len(api.call(ROLES,{'actor':data['admin']})['roles'])==4


def test_read_permissions_and_member_write_permissions(api,data):
    for kind in ('CONTADOR','CAPTURISTA','CONSULTA'):
        actor=data['members'][kind]
        for query in (ACCOUNTS,CONCEPTS):
            api.call(query,{'actor':actor,'id':data['cid']})
        api.call(TXS,{'actor':actor})
        api.call(USER,{'actor':actor,'input':user_input(data['cid'],kind.lower()+'new@example.com')},code='FORBIDDEN')
        api.call(ROLES,{'actor':actor},code=None if kind=='CONTADOR' else 'FORBIDDEN')
        api.call(MEMBERS,{'actor':actor,'id':data['cid']},code='FORBIDDEN' if kind=='CAPTURISTA' else None)

def test_mysql_migration_preserves_every_legacy_field(api,tmp_path):
    if api.app.state.engine.dialect.name!='mysql':
        pytest.skip('Migración de SQLite a MySQL; se ejecuta en la suite MySQL.')
    from app.config import Settings
    from app.db import database
    from app.seed import seed
    from app.migrate_sqlite import migrate
    source_file=tmp_path/'legacy.db'
    settings=Settings('sqlite:///'+source_file.as_posix(),api.settings.jwt_secret,api.settings.bootstrap_key)
    seed(settings,'Migration-test-password!')
    result=migrate(source_file,api.settings)
    assert result['transactions']==20
    source,_=database(settings.database_url)
    with source.connect() as old,api.app.state.engine.connect() as new:
        for model in (m.Company,m.User,m.CompanyUser,m.Account,m.Concept,m.AccountConcept,m.Transaction):
            old_rows=list(old.execute(select(model.__table__).order_by(model.id)).mappings())
            new_rows=list(new.execute(select(model.__table__).order_by(model.id)).mappings())
            assert old_rows==new_rows
    source.dispose()
    with api.app.state.sessions() as db:
        assert {row.role.code for row in db.scalars(select(CompanyUserRole))}=={'CONSULTA'}
    with pytest.raises(ValueError,match='ya contiene datos'):
        migrate(source_file,api.settings)
