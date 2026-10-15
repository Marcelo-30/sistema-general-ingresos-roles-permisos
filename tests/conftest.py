"""Pruebas de HTTP GraphQL en bases temporales: SQLite o MySQL real."""
import json
import os
import secrets
import uuid
from pathlib import Path
import pytest
from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from fastapi.testclient import TestClient
from app.config import Settings
from app.factory import create_app

records=[]
reports={}


def redact(obj):
    if isinstance(obj,dict):
        return {k:'<oculto>' if k in {'password','token','passwordHash'} else redact(v) for k,v in obj.items()}
    if isinstance(obj,list):
        return [redact(x) for x in obj]
    return obj


@pytest.fixture
def api(tmp_path,request):
    admin_engine=None
    dbname='ingresos_test_'+uuid.uuid4().hex
    if os.getenv('TEST_MYSQL')=='1':
        env=dotenv_values('.env.docker')
        root=URL.create('mysql+pymysql',username='root',password=env['MYSQL_ROOT_PASSWORD'],host='127.0.0.1',port=int(env['MYSQL_PORT']))
        admin_engine=create_engine(root,isolation_level='AUTOCOMMIT')
        with admin_engine.connect() as db:
            db.execute(text(f'CREATE DATABASE `{dbname}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs'))
        url=root.set(database=dbname).render_as_string(hide_password=False)
    else:
        url='sqlite:///'+(tmp_path/'test.db').as_posix()
    settings=Settings(url,secrets.token_urlsafe(48),secrets.token_urlsafe(48))
    app=create_app(settings)
    with TestClient(app) as client:
        class API:
            bootstrap={'X-Bootstrap-Key':settings.bootstrap_key}
            def call(self,query,variables=None,headers=None,code=None):
                response=client.post('/graphql',json={'query':query,'variables':variables or {}},headers=headers or {})
                result=response.json()
                records.append({'caso':request.node.name,'operacion':query,'variables':redact(variables or {}),
                                'esperado':code or 'Sin errores GraphQL','obtenido':redact(result),'http':response.status_code})
                assert response.status_code==200,result
                if code=='GRAPHQL_VALIDATION':
                    assert result.get('errors'),result
                elif code:
                    assert result['errors'][0]['extensions']['code']==code,result
                else:
                    assert 'errors' not in result,result
                return result.get('data')
        obj=API()
        obj.app,obj.settings,obj.client=app,settings,client
        yield obj
    app.state.engine.dispose()
    if admin_engine:
        # Solo elimina la base temporal aleatoria creada por ESTE fixture.
        assert dbname.startswith('ingresos_test_') and len(dbname)==46
        with admin_engine.connect() as db:
            db.execute(text(f'DROP DATABASE `{dbname}`'))
        admin_engine.dispose()


def pytest_runtest_logreport(report):
    if report.when=='call' or report.failed:
        reports[report.nodeid.split('::')[-1]]=report.outcome


def pytest_sessionfinish(session,exitstatus):
    directory=Path('docs/evidencias/unidad2')
    directory.mkdir(parents=True,exist_ok=True)
    backend='mysql' if os.getenv('TEST_MYSQL')=='1' else 'sqlite'
    (directory/f'graphql-{backend}.json').write_text(json.dumps({'backend':backend,'exitstatus':exitstatus,'pruebas':reports,
        'casos':[{**r,'estado':reports.get(r['caso'],'no ejecutado')} for r in records]},indent=2,ensure_ascii=False),encoding='utf-8')
