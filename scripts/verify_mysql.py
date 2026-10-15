"""Fotografía SQL sin secretos: MySQL real, conteos, matriz y asignaciones."""
import json
from pathlib import Path
from sqlalchemy import text,select,func
from app.config import Settings
from app.db import database
from app import models as m


def snapshot(tag):
    engine,_=database(Settings.from_env().database_url)
    if engine.dialect.name!='mysql':
        raise ValueError('Esta comprobación requiere MySQL.')
    queries={
        'version':'SELECT VERSION() AS version',
        'roles':'SELECT id,code,is_active FROM roles ORDER BY id',
        'permissions':'SELECT id,code,is_active FROM permissions ORDER BY id',
        'matrix':'SELECT r.code AS role_code,p.code AS permission_code,rp.is_active FROM role_permissions rp JOIN roles r ON r.id=rp.role_id JOIN permissions p ON p.id=rp.permission_id ORDER BY r.id,p.id',
        'memberships':'SELECT cu.id AS company_user_id,cu.company_id,cu.is_admin,r.code AS role_code,cur.is_active FROM company_users cu JOIN company_user_roles cur ON cur.company_user_id=cu.id JOIN roles r ON r.id=cur.role_id ORDER BY cu.id,cur.id',
        'transaction_count':'SELECT COUNT(*) AS total FROM transactions',
        'role_permission_count':'SELECT COUNT(*) AS total FROM role_permissions',
    }
    with engine.connect() as db:
        result={name:{'sql':query,'rows':[dict(row) for row in db.execute(text(query)).mappings()]} for name,query in queries.items()}
    engine.dispose()
    out=Path('docs/evidencias/unidad2')
    out.mkdir(parents=True,exist_ok=True)
    (out/(tag+'.json')).write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'version':result['version']['rows'],'transactions':result['transaction_count']['rows'],'roles':len(result['roles']['rows']),'permissions':len(result['permissions']['rows']),'relations':result['role_permission_count']['rows']},indent=2))
    return result


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('tag',nargs='?',default='mysql-comprobacion')
    args=parser.parse_args()
    if not args.tag.replace('-','').isalnum():
        raise SystemExit('Etiqueta inválida.')
    snapshot(args.tag)
