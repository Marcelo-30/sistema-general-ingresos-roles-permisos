"""RBAC plano: decisión central, asignación atómica y catálogos iniciales."""
from sqlalchemy import select, func, inspect, text
from . import models as m
from .access_models import RoleModel as Role, PermissionModel as Permission
from .access_models import RolePermissionModel as RolePermission, CompanyUserRoleModel as CompanyUserRole
from .db import Base, lock_operation
from .service import fail, identifier

PERMISSIONS = (
    'company.users.read', 'company.users.write', 'accounts.read', 'accounts.write',
    'concepts.read', 'concepts.write', 'transactions.read', 'transactions.write', 'roles.read', 'roles.write',
)
MATRIX = {
    'ADMINISTRADOR': PERMISSIONS,
    'CONTADOR': ('company.users.read', 'accounts.read', 'accounts.write', 'concepts.read',
                 'concepts.write', 'transactions.read', 'transactions.write', 'roles.read'),
    'CAPTURISTA': ('accounts.read', 'concepts.read', 'transactions.read', 'transactions.write'),
    'CONSULTA': ('company.users.read', 'accounts.read', 'concepts.read', 'transactions.read'),
}


def membership(db, value):
    member = db.get(m.CompanyUser, identifier(value))
    if not member or not member.is_active or not member.company.is_active or not member.user.is_active:
        fail('La membresía, su usuario o su empresa no están activos.', 'FORBIDDEN')
    return member


def exigir_permiso(db, company_user_id: int, codigo: str) -> None:
    """No interpreta isAdmin ni permisos enviados por el cliente."""
    member = membership(db, company_user_id)
    assignments = list(db.scalars(select(CompanyUserRole).where(
        CompanyUserRole.company_user_id == member.id, CompanyUserRole.is_active.is_(True))))
    if len(assignments) != 1 or not assignments[0].role.is_active:
        fail('La membresía no tiene exactamente un rol activo.', 'FORBIDDEN')
    allowed = db.scalar(select(RolePermission.id).join(Permission).where(
        RolePermission.role_id == assignments[0].role_id,
        RolePermission.is_active.is_(True), Permission.is_active.is_(True), Permission.code == codigo))
    if allowed is None:
        fail(f'El rol no tiene el permiso {codigo}.', 'FORBIDDEN')


def assign(db, member, role):
    """El llamador valida autorización. Reutiliza filas y no hace commit parcial."""
    if not member.is_active or not member.company.is_active or not role.is_active:
        fail('La membresía, empresa y rol deben estar activos.')
    rows = list(db.scalars(select(CompanyUserRole).where(CompanyUserRole.company_user_id == member.id)))
    target = next((row for row in rows if row.role_id == role.id), None)
    for row in rows:
        row.is_active = False
    db.flush()  # Libera el índice único antes de activar la nueva asignación.
    if target is None:
        target = CompanyUserRole(company_user_id=member.id, role_id=role.id)
        db.add(target)
    target.is_active = True
    db.flush()
    return target


def role_by_code(db, code):
    role = db.scalar(select(Role).where(Role.code == code, Role.is_active.is_(True)))
    if role is None:
        fail(f'Falta el rol activo {code}; configura el catálogo antes de continuar.', 'CONFLICT')
    return role


def seed_catalogs(db):
    if db.scalar(select(func.count()).select_from(Role)) == 0:
        db.add_all(Role(code=code, name=code.capitalize()) for code in MATRIX)
    if db.scalar(select(func.count()).select_from(Permission)) == 0:
        db.add_all(Permission(code=code, name=code) for code in PERMISSIONS)
    db.flush()
    permissions = {x.code: x for x in db.scalars(select(Permission))}
    for role in db.scalars(select(Role)):
        # Contamos TAMBIÉN las relaciones inactivas: una revocación no se restaura.
        configured = db.scalar(select(RolePermission.id).where(RolePermission.role_id == role.id).limit(1))
        if role.code in MATRIX and configured is None:
            missing = set(MATRIX[role.code]) - permissions.keys()
            if missing:
                fail('Catálogo parcial: faltan permisos para inicializar la matriz.', 'CONFLICT')
            db.add_all(RolePermission(role_id=role.id, permission_id=permissions[code].id)
                       for code in MATRIX[role.code])
    db.flush()
    for member in db.scalars(select(m.CompanyUser).where(m.CompanyUser.is_active.is_(True))):
        historical = db.scalar(select(CompanyUserRole.id).where(CompanyUserRole.company_user_id == member.id).limit(1))
        if historical is None:
            # Transición explícita de mínimo privilegio, incluso para isAdmin antiguo.
            db.add(CompanyUserRole(company_user_id=member.id, role_id=role_by_code(db, 'CONSULTA').id))
    db.flush()


def initialize(engine, sessions):
    Base.metadata.create_all(engine)
    if engine.dialect.name == 'mysql':
        # MySQL no tiene índices parciales: una expresión NULL permite múltiples
        # filas inactivas y aplica UNIQUE únicamente a las activas.
        indexes = [('company_users', 'uq_company_admin', 'is_admin', 'company_id'),
                   ('company_user_roles', 'uq_member_active_role', 'is_active', 'company_user_id')]
        with engine.begin() as connection:
            # Conserva microsegundos al migrar datos de SQLite o de una versión
            # anterior de este proyecto. Solo amplía precisión; no borra filas.
            for table in ('companies', 'users', 'company_users', 'accounts', 'concepts', 'account_concepts', 'transactions'):
                for column in inspect(connection).get_columns(table):
                    if column['type'].__class__.__name__ == 'DATETIME' and column['type'].fsp != 6:
                        nullable = 'NULL' if column['nullable'] else 'NOT NULL'
                        connection.execute(text(f"ALTER TABLE {table} MODIFY {column['name']} DATETIME(6) {nullable}"))
            for table, index, flag, column in indexes:
                if index not in {i['name'] for i in inspect(connection).get_indexes(table)}:
                    connection.execute(text(f'CREATE UNIQUE INDEX {index} ON {table} '
                                            f'((CASE WHEN {flag} = 1 THEN {column} ELSE NULL END))'))
    with sessions.begin() as db:
        lock_operation(db)
        seed_catalogs(db)
