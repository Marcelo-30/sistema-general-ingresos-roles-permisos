from datetime import datetime
from decimal import Decimal
from pathlib import Path
import pytest
from graphql import build_schema, Undefined
from sqlalchemy import select, text, func
from sqlalchemy.exc import IntegrityError
from app import models as m
from app.schema import schema
from test_graphql import setup, company, credentials, login, ADMIN, USER

ACCOUNT = 'mutation($input:CreateAccountInput!){createAccount(input:$input){id companyId accountType name bankName accountNumber clabe cardLastDigits shortDescription longDescription isActive createdAt updatedAt company{id}}}'
CONCEPT = 'mutation($input:CreateConceptInput!){createConcept(input:$input){id companyId conceptType name shortDescription longDescription isActive createdAt updatedAt}}'
ASSIGN = 'mutation($input:AssignConceptToAccountInput!){assignConceptToAccount(input:$input){id accountId conceptId isActive createdAt account{id company{id}} concept{id}}}'
REMOVE = 'mutation($a:ID!,$c:ID!){removeConceptFromAccount(accountId:$a,conceptId:$c)}'
LINKS = 'query($a:ID!){accountConcepts(accountId:$a){id conceptId isActive}}'
TX = 'mutation($input:CreateTransactionInput!){createTransaction(input:$input){id accountId conceptId transactionType amount transactionDate capturedAt capturedBy isActive createdAt updatedAt shortDescription longDescription account{id} concept{id} capturedByUser{id email}}}'
TXS = 'query($a:ID,$t:TransactionType,$l:Int,$o:Int){transactions(accountId:$a,transactionType:$t,limit:$l,offset:$o){id amount transactionType isActive capturedBy}}'
BALANCE = 'query($a:ID!){accountBalance(accountId:$a)}'
DELETE = 'mutation($id:ID!){deleteTransaction(id:$id){id isActive amount capturedBy}}'
ACCOUNTS = 'query($id:ID!,$t:AccountType,$active:Boolean){accounts(companyId:$id,accountType:$t,activeOnly:$active){id name accountType isActive}}'
CONCEPTS = 'query($id:ID!,$t:ConceptType,$active:Boolean){concepts(companyId:$id,conceptType:$t,activeOnly:$active){id name conceptType isActive}}'


@pytest.fixture
def finance(api):
    cid, member, auth = setup(api)
    a = api.call(ACCOUNT, {'input': {'companyId':cid,'name':'Caja principal','accountType':'CASH'}}, auth)['createAccount']
    concepts = []
    for kind in ('INCOME','EXPENSE'):
        c = api.call(CONCEPT, {'input': {'companyId':cid,'name':kind,'conceptType':kind}}, auth)['createConcept']
        api.call(ASSIGN, {'input':{'accountId':a['id'],'conceptId':c['id']}}, auth)
        concepts.append(c['id'])
    return cid, member, auth, a['id'], *concepts


def movement(f, amount='1.00', kind='INCOME', **extra):
    return {'accountId':f[3], 'conceptId':f[4] if kind=='INCOME' else f[5],
            'transactionType':kind, 'amount':amount, **extra}


def test_finance_pdf_contract():
    expected = build_schema(Path('tests/schema_pdf.graphql').read_text(encoding='utf-8')+'\n'+Path('tests/finance_pdf.graphql').read_text(encoding='utf-8-sig'))
    actual = schema._schema
    for name, old in expected.type_map.items():
        if name.startswith('__'):
            continue
        new = actual.get_type(name)
        assert new is not None
        if hasattr(old, 'values'):
            assert set(old.values) == set(new.values)
        if not hasattr(old, 'fields'):
            continue
        extra = {'accountBalance'} if name == 'Query' else set()
        assert set(new.fields) == set(old.fields) | extra
        for key, field in old.fields.items():
            current = new.fields[key]
            assert str(current.type) == str(field.type), (name,key)
            if hasattr(field, 'args'):
                assert set(current.args) == set(field.args)
                for arg, value in field.args.items():
                    assert str(current.args[arg].type) == str(value.type)
                    assert current.args[arg].default_value is Undefined
            elif hasattr(field, 'default_value'):
                assert current.default_value is Undefined


def test_catalogs_filters_duplicates(api, finance):
    cid, _, auth, a, inc, exp = finance
    for name in (' CAJA   principal ', 'caja PRINCIPAL'):
        api.call(ACCOUNT, {'input':{'companyId':cid,'name':name,'accountType':'DEBIT'}}, auth, 'CONFLICT')
    api.call(CONCEPT, {'input':{'companyId':cid,'name':' income ','conceptType':'INCOME'}}, auth, 'CONFLICT')
    other = api.call(CONCEPT, {'input':{'companyId':cid,'name':'INCOME','conceptType':'EXPENSE'}}, auth)['createConcept']
    api.call(ACCOUNT, {'input':{'companyId':cid,'name':'Banco','accountType':'DEBIT','accountNumber':'001234','clabe':'000000000000000001','cardLastDigits':'0001','bankName':'Banco ficticio','shortDescription':'A','longDescription':'B'}}, auth)
    for query, kind, expected in [(ACCOUNTS,'CASH',a),(CONCEPTS,'INCOME',inc)]:
        rows = next(iter(api.call(query, {'id':cid,'t':kind,'active':True},auth).values()))
        assert [x['id'] for x in rows] == [expected]
    with api.app.state.sessions.begin() as db:
        db.get(m.Account,int(a)).is_active = False
        db.get(m.Concept,int(other['id'])).is_active = False
    for query in (ACCOUNTS,CONCEPTS):
        all_rows = next(iter(api.call(query, {'id':cid},auth).values()))
        active = next(iter(api.call(query, {'id':cid,'active':True},auth).values()))
        assert len(all_rows) == len(active)+1
        assert all(x['isActive'] for x in active)
        assert next(iter(api.call(query, {'id':cid,'active':False},auth).values())) == all_rows
    api.call(TX, {'input':movement(finance)}, auth, 'BAD_INPUT')


def test_relation_lifecycle_constraints(api, finance):
    _, _, auth, a, c, _ = finance
    inp = {'input':{'accountId':a,'conceptId':c}}
    original = api.call(LINKS,{'a':a},auth)['accountConcepts'][0]
    api.call(ASSIGN,inp,auth,'CONFLICT')
    assert api.call(REMOVE,{'a':a,'c':c},auth)['removeConceptFromAccount']
    assert not api.call(REMOVE,{'a':a,'c':c},auth)['removeConceptFromAccount']
    assert c not in [x['conceptId'] for x in api.call(LINKS,{'a':a},auth)['accountConcepts']]
    api.call(TX,{'input':movement(finance)},auth,'BAD_INPUT')
    restored = api.call(ASSIGN,inp,auth)['assignConceptToAccount']
    assert restored['id'] == original['id'] and restored['isActive']
    with pytest.raises(IntegrityError), api.app.state.sessions.begin() as db:
        db.add(m.AccountConcept(account_id=int(a),concept_id=int(c)))
        db.flush()
    with pytest.raises(IntegrityError), api.app.state.sessions.begin() as db:
        db.add(m.AccountConcept(account_id=99999,concept_id=int(c)))
        db.flush()


@pytest.mark.parametrize('amount', ['0','-1','-0.001'])
def test_invalid_amount(api, finance, amount):
    api.call(TX,{'input':movement(finance,amount)},finance[2],'BAD_INPUT')


@pytest.mark.parametrize('extra,code', [({'accountId':'999999'},'NOT_FOUND'),({'conceptId':'999999'},'NOT_FOUND'),({'accountId':'abc'},'BAD_INPUT'),({'transactionType':'EXPENSE'},'BAD_INPUT')])
def test_invalid_references_and_type(api, finance, extra, code):
    api.call(TX,{'input':movement(finance,**extra)},finance[2],code)


def test_unassigned_concept_and_inactive(api,finance):
    cid,_,auth,a,inc,_ = finance
    c = api.call(CONCEPT,{'input':{'companyId':cid,'name':'Sin asignar','conceptType':'INCOME'}},auth)['createConcept']['id']
    api.call(TX,{'input':movement(finance,conceptId=c)},auth,'BAD_INPUT')
    with api.app.state.sessions.begin() as db:
        db.get(m.Concept,int(inc)).is_active=False
    api.call(TX,{'input':movement(finance)},auth,'BAD_INPUT')
    api.call(ASSIGN,{'input':{'accountId':a,'conceptId':inc}},auth,'BAD_INPUT')


def test_transactions_precision_dates_pagination_deletion(api,finance):
    _,member,auth,a,_,_ = finance
    ids=[]
    amounts=['0.1','0.2','0.3','123456789012345678901234567890.12345678901234567890']
    for amount,kind in zip(amounts,['INCOME','INCOME','EXPENSE','INCOME']):
        result=api.call(TX,{'input':movement(finance,amount,kind)},auth)['createTransaction']
        ids.append(result['id'])
        assert result['amount']==amount
        assert result['capturedBy']==member['userId']==result['capturedByUser']['id']
        assert result['transactionDate']==result['capturedAt']
        assert result['capturedAt'].endswith('Z')
    assert api.call(BALANCE,{'a':a},auth)['accountBalance']==amounts[-1]
    with api.app.state.sessions() as db:
        stored=db.execute(text('SELECT amount, typeof(amount) FROM transactions ORDER BY id')).all()
        assert [r[0] for r in stored]==amounts and all(r[1]=='text' for r in stored)
    assert [x['id'] for x in api.call(TXS,{'a':a,'l':2,'o':1},auth)['transactions']]==ids[1:3]
    assert len(api.call(TXS,{'t':'EXPENSE'},auth)['transactions'])==1
    assert api.call(TXS,{'l':0},auth)['transactions']==[]
    for v in ({'l':-1},{'o':-1}):
        api.call(TXS,v,auth,'BAD_INPUT')
    result=api.call(DELETE,{'id':ids[-1]},auth)['deleteTransaction']
    assert not result['isActive']
    api.call(DELETE,{'id':ids[-1]},auth)
    assert Decimal(api.call(BALANCE,{'a':a},auth)['accountBalance'])==0
    assert len(api.call(TXS,{},auth)['transactions'])==3
    result=api.call(TX,{'input':movement(finance,transactionDate='2026-09-25T10:00:00-06:00')},auth)['createTransaction']
    assert result['transactionDate']=='2026-09-25T16:00:00Z'
    # No se aplica una regla de saldo insuficiente.
    api.call(TX,{'input':movement(finance,'2','EXPENSE')},auth)
    assert Decimal(api.call(BALANCE,{'a':a},auth)['accountBalance']) == -1


def test_all_financial_operations_require_authentication(api,finance):
    cid,_,_,a,c,_=finance
    operations=[(ACCOUNTS,{'id':cid}),(CONCEPTS,{'id':cid}),(LINKS,{'a':a}), (TXS,{}),(BALANCE,{'a':a}),
                (ACCOUNT,{'input':{'companyId':cid,'name':'X','accountType':'CASH'}}),
                (CONCEPT,{'input':{'companyId':cid,'name':'X','conceptType':'INCOME'}}),
                (ASSIGN,{'input':{'accountId':a,'conceptId':c}}),(REMOVE,{'a':a,'c':c}),
                (TX,{'input':movement(finance)}),(DELETE,{'id':'1'})]
    for query,variables in operations:
        api.call(query,variables,code='UNAUTHENTICATED')


def test_cross_company_isolation_and_normal_user(api,finance):
    cid,_,auth,a,c,_=finance
    second=company(api,'Segunda')
    api.call(ADMIN,{'input':credentials(second,'second@example.com')},api.bootstrap)
    other_auth=login(api,'second@example.com')
    b=api.call(ACCOUNT,{'input':{'companyId':second,'name':'Caja principal','accountType':'CASH'}},other_auth)['createAccount']['id']
    other_c=api.call(CONCEPT,{'input':{'companyId':second,'name':'INCOME','conceptType':'INCOME'}},other_auth)['createConcept']['id']
    tx=api.call(TX,{'input':movement(finance)},auth)['createTransaction']['id']
    for q,v in [(ACCOUNTS,{'id':cid}),(CONCEPTS,{'id':cid}),(LINKS,{'a':a}), (TXS,{'a':a}),(BALANCE,{'a':a}),
                (DELETE,{'id':tx}),(REMOVE,{'a':a,'c':c}),(ASSIGN,{'input':{'accountId':b,'conceptId':c}}),
                (TX,{'input':movement(finance)}),
                (ACCOUNT,{'input':{'companyId':cid,'name':'X','accountType':'CASH'}}),
                (CONCEPT,{'input':{'companyId':cid,'name':'X','conceptType':'INCOME'}})]:
        api.call(q,v,other_auth,'FORBIDDEN')
    api.call(TX,{'input':movement(finance,conceptId=other_c)},auth,'FORBIDDEN')
    assert api.call(TXS,{},other_auth)['transactions']==[]
    user=api.call(USER,{'input':credentials(cid,'normal@example.com')},auth)['createCompanyUser']
    normal=login(api,'normal@example.com')
    result=api.call(TX,{'input':movement(finance)},normal)['createTransaction']
    assert result['capturedBy']==user['userId']
    # Incluso con membresías en ambas empresas no se permiten relaciones cruzadas.
    with api.app.state.sessions.begin() as db:
        db.add(m.CompanyUser(company_id=int(second),user_id=int(user['userId'])))
    api.call(ASSIGN,{'input':{'accountId':a,'conceptId':other_c}},normal,'FORBIDDEN')
    api.call(TX,{'input':movement(finance,conceptId=other_c)},normal,'FORBIDDEN')


@pytest.mark.parametrize('extra', [{'amount':'NaN'},{'amount':'Infinity'},{'amount':0.1},{'amount':True},{'amount':'1e999'},
                                    {'transactionDate':'2026-09-25T10:00:00'},{'transactionDate':'no-fecha'},
                                    {'capturedBy':'123'},{'capturedAt':'2026-01-01T00:00:00Z'}])
def test_scalar_validation_and_no_impersonation(api,finance,extra):
    api.call(TX,{'input':movement(finance,**extra)},finance[2],code='GRAPHQL_VALIDATION')


def test_finance_rollback(api,finance):
    with api.app.state.engine.begin() as connection:
        connection.execute(text("CREATE TRIGGER fail_transaction BEFORE INSERT ON transactions BEGIN SELECT RAISE(ABORT, 'test'); END"))
    api.call(TX,{'input':movement(finance)},finance[2],'CONFLICT')
    with api.app.state.sessions() as db:
        assert db.scalar(select(func.count()).select_from(m.Transaction))==0

def test_seed_repeatable_and_graphql_data(api):
    from app.seed import seed
    first = seed(api.settings, 'Demo-only-test-password!')
    second = seed(api.settings, 'Demo-only-test-password!')
    assert first == second
    assert {k:v for k,v in first.items() if k!='companyId'} == dict(accounts=3,income_concepts=5,expense_concepts=5,account_concepts=10,transactions=20)
    auth = login(api,'actividad4@example.com',password='Demo-only-test-password!')
    assert len(api.call(ACCOUNTS,{'id':first['companyId']},auth)['accounts'])==3
    assert len(api.call(CONCEPTS,{'id':first['companyId'],'t':'INCOME'},auth)['concepts'])==5
    assert len(api.call(CONCEPTS,{'id':first['companyId'],'t':'EXPENSE'},auth)['concepts'])==5
    rows = api.call(TXS,{'l':100},auth)['transactions']
    assert len(rows)==20 and {x['transactionType'] for x in rows}=={'INCOME','EXPENSE'}
