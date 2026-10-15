"""Guarda el SELECT final real de MySQL y verifica la matriz de la actividad 4."""
import argparse
import json
from pathlib import Path

from sqlalchemy import text

from app.access import MATRIX
from app.config import Settings
from app.db import database


RELATIONS_SQL = """SELECT rp.id, r.code AS rol, p.code AS permiso, rp.is_active
FROM role_permissions rp
JOIN roles r ON r.id = rp.role_id
JOIN permissions p ON p.id = rp.permission_id
ORDER BY r.id, p.id"""
PEDRO_SQL = """SELECT cur.id, r.code AS rol, cur.is_active
FROM company_user_roles cur
JOIN roles r ON r.id = cur.role_id
JOIN company_users cu ON cu.id = cur.company_user_id
JOIN users u ON u.id = cu.user_id
JOIN companies c ON c.id = cu.company_id
WHERE c.tax_id = 'DEMO-PERMISOS-U2-A4'
AND u.email = 'pedro.permisos@example.com'
ORDER BY cur.id"""


def snapshot(after_restart=False):
    settings = Settings.from_env()
    engine, _ = database(settings.database_url)
    try:
        if engine.dialect.name != 'mysql':
            raise RuntimeError('Este SELECT de entrega debe ejecutarse en MySQL.')
        with engine.connect() as db:
            roles = [dict(row) for row in db.execute(text(
                'SELECT id, code, is_active FROM roles ORDER BY id'
            )).mappings()]
            permissions = [dict(row) for row in db.execute(text(
                'SELECT id, code, is_active FROM permissions ORDER BY id'
            )).mappings()]
            relations = [dict(row) for row in db.execute(text(RELATIONS_SQL)).mappings()]
            pedro = [dict(row) for row in db.execute(text(PEDRO_SQL)).mappings()]
            counts = dict(db.execute(text("""SELECT
                (SELECT COUNT(*) FROM accounts a JOIN companies c ON c.id=a.company_id
                 WHERE c.tax_id='DEMO-PERMISOS-U2-A4') AS cuentas,
                (SELECT COUNT(*) FROM transactions t JOIN accounts a ON a.id=t.account_id
                 JOIN companies c ON c.id=a.company_id
                 WHERE c.tax_id='DEMO-PERMISOS-U2-A4') AS movimientos""")).mappings().one())

        active = {(row['rol'], row['permiso']) for row in relations if row['is_active']}
        expected = {(role, code) for role, codes in MATRIX.items() for code in codes}
        inactive = {(row['rol'], row['permiso']) for row in relations if not row['is_active']}
        checks = {
            'cuatro_roles': len(roles) == 4,
            'diez_permisos': len(permissions) == 10,
            'matriz_activa_inicial_26': active == expected and len(active) == 26,
            'dos_parejas_historicas_inactivas': inactive == {
                ('CAPTURISTA', 'accounts.write'), ('CONSULTA', 'concepts.write'),
            },
            'pedro_un_rol_activo_capturista': sum(bool(row['is_active']) for row in pedro) == 1
            and any(row['rol'] == 'CAPTURISTA' and row['is_active'] for row in pedro)
            and any(row['rol'] == 'CONSULTA' and not row['is_active'] for row in pedro),
            'cuentas_aceptadas': counts['cuentas'] == 4,
            'solo_movimiento_aceptado': counts['movimientos'] == 1,
        }
        result = {
            'backend': 'MySQL', 'sql_role_permissions': RELATIONS_SQL,
            'sql_roles_pedro': PEDRO_SQL, 'roles': roles, 'permissions': permissions,
            'role_permissions': relations, 'company_user_roles_pedro': pedro,
            'conteos_empresa_demo': counts, 'comprobaciones': checks,
        }
        folder = Path('docs/evidencias/actividad4')
        folder.mkdir(parents=True, exist_ok=True)
        output = folder / ('tras-reinicio.json' if after_restart else 'select-final.json')
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        table = folder / ('tras-reinicio.txt' if after_restart else 'select-final.txt')
        table.write_text(
            RELATIONS_SQL + '\n\n' + 'id\trol\tpermiso\tis_active\n' +
            ''.join(f"{row['id']}\t{row['rol']}\t{row['permiso']}\t{row['is_active']}\n"
                    for row in relations),
            encoding='utf-8',
        )
        if not all(checks.values()):
            raise AssertionError(f'La matriz final no coincide: {checks}')
        print(json.dumps({'archivo': str(output), 'select': str(table),
                          'comprobaciones': checks}, ensure_ascii=False))
    finally:
        engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--after-restart', action='store_true')
    snapshot(parser.parse_args().after_restart)
