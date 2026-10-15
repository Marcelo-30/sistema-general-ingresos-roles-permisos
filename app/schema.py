from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
import strawberry
from strawberry.types import Info
from graphql import GraphQLError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from .service import fail
from .finance_service import FinanceService as Service


def serialize_time(value):
    return value.replace(tzinfo=value.tzinfo or timezone.utc).isoformat().replace('+00:00', 'Z')


def parse_time(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Time requiere zona horaria.')
    return result.astimezone(timezone.utc)


Time = strawberry.scalar(datetime, name='Time', serialize=serialize_time, parse_value=parse_time)


@strawberry.type
class Company:
    id: strawberry.ID
    name: str
    legal_name: Optional[str]
    tax_id: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    is_active: bool
    created_at: Time
    updated_at: Time


@strawberry.type
class User:
    id: strawberry.ID
    name: str
    email: str
    email_verified: bool
    is_active: bool
    created_at: Time
    updated_at: Time


@strawberry.type
class CompanyUser:
    id: strawberry.ID
    company_id: strawberry.ID
    user_id: strawberry.ID
    is_admin: bool
    is_active: bool
    joined_at: Time
    company: Company
    user: User


@strawberry.type
class AuthUser:
    id: strawberry.ID
    name: str
    email: str


@strawberry.type
class AuthPayload:
    token: str
    token_type: str
    user: AuthUser


@strawberry.input
class CreateCompanyInput:
    name: str
    legal_name: Optional[str] = strawberry.UNSET
    tax_id: Optional[str] = strawberry.UNSET
    email: Optional[str] = strawberry.UNSET
    phone: Optional[str] = strawberry.UNSET


@strawberry.input
class UpdateCompanyInput:
    id: strawberry.ID
    name: Optional[str] = strawberry.UNSET
    legal_name: Optional[str] = strawberry.UNSET
    tax_id: Optional[str] = strawberry.UNSET
    email: Optional[str] = strawberry.UNSET
    phone: Optional[str] = strawberry.UNSET
    is_active: Optional[bool] = strawberry.UNSET


@strawberry.input
class CreateCompanyAdminInput:
    company_id: strawberry.ID
    name: str
    email: str
    password: str


@strawberry.input
class CreateCompanyUserInput:
    company_id: strawberry.ID
    name: str
    email: str
    password: str


@strawberry.input
class LoginInput:
    email: str
    password: str


def convert(kind, obj):
    if obj is None:
        return None
    fields = kind.__dataclass_fields__
    values = {key: getattr(obj, key) for key in fields if key not in ('company', 'user')}
    for key in ('id', 'company_id', 'user_id'):
        if key in values:
            values[key] = strawberry.ID(str(values[key]))
    if kind is CompanyUser:
        values.update(company=convert(Company, obj.company), user=convert(User, obj.user))
    return kind(**values)


def execute(info, work, actor_company_user_id=None, permission=None):
    app = info.context['request'].app
    try:
        with app.state.sessions.begin() as session:
            from .db import lock_operation
            lock_operation(session)
            service = Service(session, app.state.settings, info.context['request'].headers, actor_company_user_id)
            if permission:
                service.require(permission)
            result = work(service)
            service.check_before_commit()
            return result
    except GraphQLError:
        raise
    except IntegrityError:
        fail('Conflicto: registro o relación duplicada, o referencia inválida.', 'CONFLICT')
    except SQLAlchemyError:
        fail('No se pudo completar la operación de base de datos.', 'INTERNAL_ERROR')


from .finance_schema import FinanceQuery, FinanceMutation, Money
from .access_schema import AccessQuery, AccessMutation


@strawberry.type
class Query(FinanceQuery, AccessQuery):
    @strawberry.field
    def companies(self, info: Info, active_only: Optional[bool] = strawberry.UNSET) -> list[Company]:
        return execute(info, lambda svc: [convert(Company, x) for x in svc.companies(active_only)])

    @strawberry.field
    def company(self, info: Info, id: strawberry.ID) -> Optional[Company]:
        return execute(info, lambda svc: convert(Company, svc.get_company(id)))

    @strawberry.field
    def company_users(self, info: Info, actor_company_user_id: strawberry.ID, company_id: strawberry.ID) -> list[CompanyUser]:
        return execute(info, lambda svc: [convert(CompanyUser, x) for x in svc.members(company_id)], actor_company_user_id, 'company.users.read')


@strawberry.type
class Mutation(FinanceMutation, AccessMutation):
    @strawberry.mutation
    def create_company(self, info: Info, input: CreateCompanyInput) -> Company:
        fields = {key: getattr(input, key) for key in input.__dataclass_fields__
                  if getattr(input, key) is not strawberry.UNSET}
        return execute(info, lambda svc: convert(Company, svc.create_company(fields)))

    @strawberry.mutation
    def update_company(self, info: Info, input: UpdateCompanyInput) -> Company:
        fields = {key: getattr(input, key) for key in input.__dataclass_fields__
                  if key != 'id' and getattr(input, key) is not strawberry.UNSET}
        return execute(info, lambda svc: convert(Company, svc.update_company(input.id, fields)))

    @strawberry.mutation
    def deactivate_company(self, info: Info, id: strawberry.ID) -> Company:
        return execute(info, lambda svc: convert(Company, svc.update_company(id, {'is_active': False})))

    @strawberry.mutation
    def create_company_admin(self, info: Info, input: CreateCompanyAdminInput) -> CompanyUser:
        return execute(info, lambda svc: convert(CompanyUser, svc.create_member(asdict(input), True)))

    @strawberry.mutation
    def create_company_user(self, info: Info, actor_company_user_id: strawberry.ID, input: CreateCompanyUserInput) -> CompanyUser:
        return execute(info, lambda svc: convert(CompanyUser, svc.create_member(asdict(input), False)), actor_company_user_id, 'company.users.write')

    @strawberry.mutation
    def deactivate_company_user(self, info: Info, actor_company_user_id: strawberry.ID, id: strawberry.ID) -> CompanyUser:
        return execute(info, lambda svc: convert(CompanyUser, svc.deactivate_member(id)), actor_company_user_id, 'company.users.write')

    @strawberry.mutation
    def login(self, info: Info, input: LoginInput) -> AuthPayload:
        def run(svc):
            token, user = svc.login(asdict(input))
            return AuthPayload(token=token, token_type='Bearer', user=convert(AuthUser, user))
        return execute(info, run)


schema = strawberry.Schema(query=Query, mutation=Mutation, types=[Decimal], scalar_overrides={Decimal: Money})
