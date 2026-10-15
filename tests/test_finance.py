from decimal import Decimal
import pytest
from sqlalchemy import select,func,text
from app import models as m
from operations import *
from test_access import data,tx_input,count,make_company


@pytest.mark.parametrize('amount',['0','-1','-0.01'])
def test_amount_must_be_positive(api,data,amount):
    api.call(TX,{'actor':data['members']['CAPTURISTA'],'input':tx_input(data,amount)},code='BAD_INPUT')
    assert count(api,m.Transaction)==0


@pytest.mark.parametrize('extra,code',[
    ({'accountId':'999999'},'NOT_FOUND'),({'conceptId':'999999'},'NOT_FOUND'),
    ({'transactionType':'EXPENSE'},'BAD_INPUT'),({'accountId':'no-es-id'},'BAD_INPUT'),
])
def test_financial_references_and_type(api,data,extra,code):
    api.call(TX,{'actor':data['members']['CAPTURISTA'],'input':tx_input(data,**extra)},code=code)
    assert count(api,m.Transaction)==0


@pytest.mark.parametrize('extra',[
    {'amount':'NaN'},{'amount':'Infinity'},{'amount':0.1},{'amount':True},
    {'transactionDate':'2026-10-10T10:00:00'},{'capturedBy':'99'},
])
def test_scalars_and_capture_cannot_be_supplied(api,data,extra):
    api.call(TX,{'actor':data['members']['CAPTURISTA'],'input':tx_input(data,**extra)},code='GRAPHQL_VALIDATION')


def test_catalog_duplicate_normalization_and_filters(api,data):
    actor=data['admin']; cid=data['cid']
    api.call(ACCOUNT,{'actor':actor,'input':{'companyId':cid,'name':' CAJA ','accountType':'DEBIT'}},code='CONFLICT')
    api.call(CONCEPT,{'actor':actor,'input':{'companyId':cid,'name':' income ','conceptType':'INCOME'}},code='CONFLICT')
    new=api.call(ACCOUNT,{'actor':actor,'input':{'companyId':cid,'name':'Banco','accountType':'DEBIT','accountNumber':'0001','clabe':'000000000000000001','cardLastDigits':'0001','bankName':'Ficticio','shortDescription':'Corto','longDescription':'Largo'}})['createAccount']
    assert new['accountNumber']=='0001'
    assert len(api.call(ACCOUNTS,{'actor':actor,'id':cid,'type':'DEBIT'})['accounts'])==1
    with api.app.state.sessions.begin() as db:
        db.get(m.Account,int(new['id'])).is_active=False
        db.get(m.Concept,int(data['concepts']['EXPENSE'])).is_active=False
    for query in (ACCOUNTS,CONCEPTS):
        assert len(next(iter(api.call(query,{'actor':actor,'id':cid,'active':True}).values())))==1
        assert len(next(iter(api.call(query,{'actor':actor,'id':cid,'active':False}).values())))==2
    api.call(TX,{'actor':actor,'input':tx_input(data,kind='EXPENSE')},code='BAD_INPUT')


def test_relationship_lifecycle_and_permissions(api,data):
    actor=data['admin']; aid=data['account']; cid=data['concepts']['INCOME']
    inp={'actor':actor,'input':{'accountId':aid,'conceptId':cid}}
    api.call(LINK,inp,code='CONFLICT')
    before=count(api,m.AccountConcept)
    api.call(REMOVE_LINK,{'actor':data['members']['CAPTURISTA'],'a':aid,'c':cid},code='FORBIDDEN')
    assert api.call(REMOVE_LINK,{'actor':actor,'a':aid,'c':cid})['removeConceptFromAccount']
    assert not api.call(REMOVE_LINK,{'actor':actor,'a':aid,'c':cid})['removeConceptFromAccount']
    api.call(TX,{'actor':actor,'input':tx_input(data)},code='BAD_INPUT')
    api.call(LINK,inp)
    assert count(api,m.AccountConcept)==before
    other=api.call(CONCEPT,{'actor':actor,'input':{'companyId':data['cid'],'name':'No permitido','conceptType':'INCOME'}})['createConcept']['id']
    api.call(TX,{'actor':actor,'input':tx_input(data,conceptId=other)},code='BAD_INPUT')


def test_precision_pagination_dates_soft_delete_and_balance(api,data):
    actor=data['members']['CAPTURISTA']; aid=data['account']
    values=[('0.1','INCOME'),('0.2','INCOME'),('0.3','EXPENSE'),('123456789012345678901234567890.12345678901234567890','INCOME')]
    ids=[]
    for amount,kind in values:
        row=api.call(TX,{'actor':actor,'input':tx_input(data,amount,kind)})['createTransaction']
        assert row['amount']==amount and row['transactionDate']==row['capturedAt']
        ids.append(row['id'])
    assert api.call(BALANCE,{'actor':actor,'a':aid})['accountBalance']==values[-1][0]
    with api.app.state.sessions() as db:
        assert list(db.scalars(text('SELECT amount FROM transactions ORDER BY id')))==[x[0] for x in values]
    rows=api.call(TXS,{'actor':actor,'a':aid,'limit':2,'offset':1})['transactions']
    assert [x['id'] for x in rows]==ids[1:3]
    assert len(api.call(TXS,{'actor':actor,'type':'EXPENSE'})['transactions'])==1
    assert api.call(TXS,{'actor':actor,'limit':0})['transactions']==[]
    api.call(TXS,{'actor':actor,'limit':-1},code='BAD_INPUT')
    api.call(DELETE,{'actor':data['members']['CONSULTA'],'id':ids[-1]},code='FORBIDDEN')
    assert not api.call(DELETE,{'actor':actor,'id':ids[-1]})['deleteTransaction']['isActive']
    api.call(DELETE,{'actor':actor,'id':ids[-1]})
    assert Decimal(api.call(BALANCE,{'actor':actor,'a':aid})['accountBalance'])==0
    assert count(api,m.Transaction)==4
    assert len(api.call(TXS,{'actor':actor})['transactions'])==3
    row=api.call(TX,{'actor':actor,'input':tx_input(data,'2','EXPENSE',transactionDate='2026-10-10T10:00:00-06:00')})['createTransaction']
    assert row['transactionDate']=='2026-10-10T16:00:00Z'
    assert Decimal(api.call(BALANCE,{'actor':actor,'a':aid})['accountBalance'])==-2


def test_other_company_concept_is_rejected(api,data):
    cid,admin=make_company(api,'Otra','other@example.com')
    concept=api.call(CONCEPT,{'actor':admin['id'],'input':{'companyId':cid,'name':'Ingreso','conceptType':'INCOME'}})['createConcept']['id']
    api.call(TX,{'actor':data['admin'],'input':tx_input(data,conceptId=concept)},code='FORBIDDEN')
    api.call(LINK,{'actor':data['admin'],'input':{'accountId':data['account'],'conceptId':concept}},code='FORBIDDEN')


def test_seed_financial_is_repeatable(api):
    from app.seed import seed
    first=seed(api.settings,'Demo-only-test-password!')
    assert seed(api.settings,'Demo-only-test-password!')==first
    assert {k:v for k,v in first.items() if k!='companyId'}==dict(accounts=3,income_concepts=5,expense_concepts=5,account_concepts=10,transactions=20)
