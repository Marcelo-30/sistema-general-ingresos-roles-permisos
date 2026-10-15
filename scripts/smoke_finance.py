"""Prueba HTTP del servidor local, sin imprimir credenciales."""
import json
import sys
from datetime import datetime, timezone
from decimal import Decimal, localcontext
from pathlib import Path
import httpx

url = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:8000/graphql'
actor = sys.argv[2] if len(sys.argv) > 2 else '1'
credentials = json.loads(Path('.demo-credentials.json').read_text(encoding='utf-8'))
records = []


def request(client, operation, variables=None, headers=None):
    response = client.post(url, json={'query': operation, 'variables': variables or {}}, headers=headers or {})
    response.raise_for_status()
    return response.json()


with httpx.Client(timeout=20) as client:
    logged = request(client, 'mutation($input:LoginInput!){login(input:$input){token user{id}}}', {'input':credentials})
    assert 'errors' not in logged, 'Falló login de demostración.'
    auth = {'Authorization':'Bearer '+logged['data']['login']['token']}
    records.append({'operacion':'login','esperado':'Token válido y usuario autenticado','obtenido':'Autenticado; credenciales y token omitidos','estado':'PASS'})
    query = 'query($actor:ID!){transactions(actorCompanyUserId:$actor,limit:100){id amount transactionType capturedBy account{id companyId} concept{id}}}'
    result = request(client,query,{'actor':actor},auth)
    assert 'errors' not in result
    rows = result['data']['transactions']
    assert len(rows) >= 20
    assert all(x['capturedBy']==logged['data']['login']['user']['id'] for x in rows)
    records.append({'operacion':query,'esperado':'Al menos 20 movimientos; captura del usuario demo','obtenido':result['data'],'estado':'PASS'})
    cid = rows[0]['account']['companyId']
    query = 'query($id:ID!,$actor:ID!){accounts(actorCompanyUserId:$actor,companyId:$id){id} concepts(actorCompanyUserId:$actor,companyId:$id){id conceptType}}'
    result = request(client,query,{'id':cid,'actor':actor},auth)
    data = result['data']
    assert len(data['accounts']) >= 3
    assert all(sum(x['conceptType']==kind for x in data['concepts'])>=5 for kind in ('INCOME','EXPENSE'))
    records.append({'operacion':query,'variables':{'id':cid},'esperado':'Mínimos: 3 cuentas, 5 INCOME y 5 EXPENSE','obtenido':data,'estado':'PASS'})
    relations = 0
    for account in data['accounts']:
        aid = account['id']
        query = 'query($a:ID!,$actor:ID!){accountConcepts(actorCompanyUserId:$actor,accountId:$a){id} accountBalance(actorCompanyUserId:$actor,accountId:$a)}'
        result = request(client,query,{'a':aid,'actor':actor},auth)
        assert 'errors' not in result
        relations += len(result['data']['accountConcepts'])
        with localcontext() as ctx:
            ctx.prec=350
            expected=sum((Decimal(x['amount']) if x['transactionType']=='INCOME' else -Decimal(x['amount']) for x in rows if x['account']['id']==aid),Decimal(0))
        assert Decimal(result['data']['accountBalance'])==expected
        records.append({'operacion':query,'variables':{'a':aid},'esperado':{'balance':str(expected)},'obtenido':result['data'],'estado':'PASS'})
    assert relations >= 10
    result = request(client,'{transactions{id}}')
    assert result.get('errors') and 'actorCompanyUserId' in result['errors'][0]['message']
    records.append({'operacion':'{transactions{id}} sin actor','esperado':'actorCompanyUserId obligatorio','obtenido':result,'estado':'PASS'})

path = Path('docs/evidencias/unidad2/smoke-finance.json')
path.write_text(json.dumps({'fechaUTC':datetime.now(timezone.utc).isoformat(),'url':url,'casos':records},indent=2,ensure_ascii=False),encoding='utf-8')
print(f'{len(records)} verificaciones HTTP correctas. Evidencia: {path}')
