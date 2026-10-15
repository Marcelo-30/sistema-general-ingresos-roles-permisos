"""Tipos públicos de roles separados de los modelos SQLAlchemy."""
import strawberry
from strawberry.types import Info
from .schema import CompanyUser, convert, execute
from .finance_schema import fields
from . import access_service as actions
from .access import Role as RoleModel, Permission as PermissionModel


@strawberry.type
class Role:
    id: strawberry.ID
    code: str
    name: str
    description: str | None
    is_active: bool


@strawberry.type
class Permission:
    id: strawberry.ID
    code: str
    name: str
    description: str | None
    is_active: bool


@strawberry.type
class RolePermission:
    id: strawberry.ID
    role: Role
    permission: Permission
    is_active: bool


@strawberry.type
class CompanyUserRole:
    id: strawberry.ID
    company_user: CompanyUser
    role: Role
    is_active: bool


@strawberry.input
class CreateRoleInput:
    code: str
    name: str
    description: str | None = strawberry.UNSET


@strawberry.input
class CreatePermissionInput:
    code: str
    name: str
    description: str | None = strawberry.UNSET


@strawberry.input
class AssignPermissionToRoleInput:
    role_id: strawberry.ID
    permission_id: strawberry.ID


@strawberry.input
class AssignRoleInput:
    company_user_id: strawberry.ID
    role_id: strawberry.ID


def public(kind, obj):
    if obj is None:
        return None
    if kind is RolePermission:
        return kind(id=str(obj.id), role=convert(Role,obj.role),
                    permission=convert(Permission,obj.permission), is_active=obj.is_active)
    if kind is CompanyUserRole:
        return kind(id=str(obj.id), company_user=convert(CompanyUser,obj.company_user),
                    role=convert(Role,obj.role),is_active=obj.is_active)
    return convert(kind,obj)


@strawberry.type
class AccessQuery:
    @strawberry.field
    def roles(self, info: Info, actor_company_user_id: strawberry.ID,
              active_only: bool | None = strawberry.UNSET) -> list[Role]:
        return execute(info, lambda s: [public(Role,x) for x in actions.catalog(s,RoleModel,active_only)],
                       actor_company_user_id,'roles.read')

    @strawberry.field
    def role(self, info: Info, actor_company_user_id: strawberry.ID, id: strawberry.ID) -> Role | None:
        from .service import identifier
        return execute(info, lambda s: public(Role,s.db.get(RoleModel,identifier(id))), actor_company_user_id,'roles.read')

    @strawberry.field
    def permissions(self, info: Info, actor_company_user_id: strawberry.ID,
                    active_only: bool | None = strawberry.UNSET) -> list[Permission]:
        return execute(info, lambda s: [public(Permission,x) for x in actions.catalog(s,PermissionModel,active_only)],
                       actor_company_user_id,'roles.read')

    @strawberry.field
    def role_permissions(self, info: Info, actor_company_user_id: strawberry.ID,
                         role_id: strawberry.ID) -> list[RolePermission]:
        return execute(info, lambda s: [public(RolePermission,x) for x in actions.role_permissions(s,role_id)],
                       actor_company_user_id,'roles.read')


@strawberry.type
class AccessMutation:
    @strawberry.mutation
    def create_role(self, info: Info, actor_company_user_id: strawberry.ID, input: CreateRoleInput) -> Role:
        return execute(info, lambda s: public(Role,actions.create(s,RoleModel,fields(input))),actor_company_user_id,'roles.write')

    @strawberry.mutation
    def deactivate_role(self, info: Info, actor_company_user_id: strawberry.ID, id: strawberry.ID) -> Role:
        return execute(info, lambda s: public(Role,actions.deactivate(s,id)),actor_company_user_id,'roles.write')

    @strawberry.mutation
    def create_permission(self, info: Info, actor_company_user_id: strawberry.ID, input: CreatePermissionInput) -> Permission:
        return execute(info, lambda s: public(Permission,actions.create(s,PermissionModel,fields(input))),actor_company_user_id,'roles.write')

    @strawberry.mutation
    def assign_permission_to_role(self, info: Info, actor_company_user_id: strawberry.ID,
                                  input: AssignPermissionToRoleInput) -> RolePermission:
        return execute(info, lambda s: public(RolePermission,actions.permission_pair(s,input.role_id,input.permission_id)),actor_company_user_id,'roles.write')

    @strawberry.mutation
    def remove_permission_from_role(self, info: Info, actor_company_user_id: strawberry.ID,
                                    role_id: strawberry.ID, permission_id: strawberry.ID) -> bool:
        return execute(info, lambda s: actions.permission_pair(s,role_id,permission_id,remove=True),actor_company_user_id,'roles.write')

    @strawberry.mutation
    def assign_role(self, info: Info, actor_company_user_id: strawberry.ID, input: AssignRoleInput) -> CompanyUserRole:
        return execute(info, lambda s: public(CompanyUserRole,actions.assign_role(s,input.company_user_id,input.role_id)),actor_company_user_id,'roles.write')
