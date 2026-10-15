from sqlalchemy import select
from .service import fail, identifier, name
from . import models as m
from .access import Role, Permission, RolePermission, CompanyUserRole, assign, membership


def get(db, model, value):
    obj = db.get(model, identifier(value))
    if obj is None:
        fail('Rol, permiso o membresía inexistente.', 'NOT_FOUND')
    return obj


def catalog(svc, model, active_only):
    stmt = select(model).order_by(model.id)
    if active_only:
        stmt = stmt.where(model.is_active.is_(True))
    return list(svc.db.scalars(stmt))


def create(svc, model, values):
    values = dict(values)
    code = values['code'].strip()
    code = code.upper() if model is Role else code.lower()
    if not code or len(code) > 50 or any(char.isspace() for char in code):
        fail('El código debe tener 1–50 caracteres sin espacios.')
    values['code'] = code
    values['name'] = name(values['name'])
    if len(values['name']) > 100 or len(values.get('description') or '') > 255:
        fail('Nombre de hasta 100 caracteres y descripción de hasta 255.')
    if svc.db.scalar(select(model.id).where(model.code == code)):
        fail('El código ya existe.', 'CONFLICT')
    obj = model(**values)
    svc.db.add(obj)
    svc.db.flush()
    return obj


def deactivate(svc, value):
    role = get(svc.db, Role, value)
    in_use = svc.db.scalar(select(CompanyUserRole.id).join(m.CompanyUser).where(
        CompanyUserRole.role_id == role.id, CompanyUserRole.is_active.is_(True), m.CompanyUser.is_active.is_(True)))
    if in_use:
        fail('Reasigna las membresías activas antes de desactivar este rol.', 'CONFLICT')
    role.is_active = False
    svc.db.flush()
    return role


def role_permissions(svc, value):
    role = get(svc.db, Role, value)
    return list(svc.db.scalars(select(RolePermission).where(
        RolePermission.role_id == role.id, RolePermission.is_active.is_(True)).order_by(RolePermission.id)))


def permission_pair(svc, role_id, permission_id, remove=False):
    role, permission = get(svc.db, Role, role_id), get(svc.db, Permission, permission_id)
    row = svc.db.scalar(select(RolePermission).where(
        RolePermission.role_id == role.id, RolePermission.permission_id == permission.id))
    if remove:
        if row is None or not row.is_active:
            return False
        row.is_active = False
        svc.db.flush()
        return True
    if not role.is_active or not permission.is_active:
        fail('El rol y el permiso deben estar activos.')
    if row and row.is_active:
        fail('La pareja rol-permiso ya está activa.', 'CONFLICT')
    if row is None:
        row = RolePermission(role_id=role.id, permission_id=permission.id)
        svc.db.add(row)
    row.is_active = True
    svc.db.flush()
    return row


def assign_role(svc, company_user_id, role_id):
    actor = membership(svc.db, svc.actor_company_user_id)
    member = get(svc.db, m.CompanyUser, company_user_id)
    if member.company_id != actor.company_id:
        fail('La membresía pertenece a otra empresa.', 'FORBIDDEN')
    return assign(svc.db, member, get(svc.db, Role, role_id))
