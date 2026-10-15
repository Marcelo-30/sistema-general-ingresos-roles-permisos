"""Contrato GraphQL financiero de las páginas 3–7 del PDF."""
from decimal import Decimal, InvalidOperation
from enum import Enum
import re
import strawberry
from strawberry.types import Info
from . import models as m
from .schema import Time, Company, User, convert, execute


def parse_decimal(value):
    # Exigir texto evita recibir un número JSON ya redondeado por float.
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise ValueError('Decimal requiere una cadena decimal (o un entero), nunca float.')
    text = str(value)
    if len(text) > 210 or not re.fullmatch(r'[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?', text):
        raise ValueError('Decimal inválido.')
    try:
        result = Decimal(text)
        if not result.is_finite() or len(result.as_tuple().digits) > 100 or abs(result.as_tuple().exponent) > 100:
            raise ValueError('Decimal fuera del rango admitido (100 dígitos y exponente ±100).')
        return result
    except InvalidOperation:
        raise ValueError('Decimal inválido.') from None


Money = strawberry.scalar(Decimal, name='Decimal', serialize=lambda x: format(x, 'f'), parse_value=parse_decimal)


@strawberry.enum
class AccountType(Enum):
    DEBIT = 'DEBIT'
    CREDIT = 'CREDIT'
    CASH = 'CASH'
    SAVINGS = 'SAVINGS'
    INVESTMENT = 'INVESTMENT'
    WALLET = 'WALLET'
    OTHER = 'OTHER'


@strawberry.enum
class ConceptType(Enum):
    INCOME = 'INCOME'
    EXPENSE = 'EXPENSE'


@strawberry.enum
class TransactionType(Enum):
    INCOME = 'INCOME'
    EXPENSE = 'EXPENSE'


@strawberry.type
class Account:
    id: strawberry.ID
    company_id: strawberry.ID
    account_type: AccountType
    name: str
    bank_name: str | None
    account_number: str | None
    clabe: str | None
    card_last_digits: str | None
    short_description: str | None
    long_description: str | None
    is_active: bool
    created_at: Time
    updated_at: Time
    company: Company


@strawberry.type
class Concept:
    id: strawberry.ID
    company_id: strawberry.ID
    concept_type: ConceptType
    name: str
    short_description: str | None
    long_description: str | None
    is_active: bool
    created_at: Time
    updated_at: Time


@strawberry.type
class AccountConcept:
    id: strawberry.ID
    account_id: strawberry.ID
    concept_id: strawberry.ID
    is_active: bool
    created_at: Time
    account: Account
    concept: Concept


@strawberry.type
class Transaction:
    id: strawberry.ID
    account_id: strawberry.ID
    concept_id: strawberry.ID
    transaction_type: TransactionType
    amount: Decimal
    transaction_date: Time
    captured_at: Time
    captured_by: strawberry.ID
    short_description: str | None
    long_description: str | None
    is_active: bool
    created_at: Time
    updated_at: Time
    account: Account
    concept: Concept
    captured_by_user: User


@strawberry.input
class CreateAccountInput:
    company_id: strawberry.ID
    account_type: AccountType
    name: str
    bank_name: str | None = strawberry.UNSET
    account_number: str | None = strawberry.UNSET
    clabe: str | None = strawberry.UNSET
    card_last_digits: str | None = strawberry.UNSET
    short_description: str | None = strawberry.UNSET
    long_description: str | None = strawberry.UNSET


@strawberry.input
class CreateConceptInput:
    company_id: strawberry.ID
    concept_type: ConceptType
    name: str
    short_description: str | None = strawberry.UNSET
    long_description: str | None = strawberry.UNSET


@strawberry.input
class AssignConceptToAccountInput:
    account_id: strawberry.ID
    concept_id: strawberry.ID


@strawberry.input
class CreateTransactionInput:
    account_id: strawberry.ID
    concept_id: strawberry.ID
    transaction_type: TransactionType
    amount: Decimal
    transaction_date: Time | None = strawberry.UNSET
    short_description: str | None = strawberry.UNSET
    long_description: str | None = strawberry.UNSET


def plain(value):
    return value.value if isinstance(value, Enum) else None if value is strawberry.UNSET else value


def fields(input):
    return {key: plain(getattr(input, key)) for key in input.__dataclass_fields__
            if getattr(input, key) is not strawberry.UNSET}


def financial(kind, obj):
    relations = {'company': Company, 'account': Account, 'concept': Concept, 'captured_by_user': User}
    enums = {'account_type': AccountType, 'concept_type': ConceptType, 'transaction_type': TransactionType}
    values = {}
    for key in kind.__dataclass_fields__:
        value = getattr(obj, key)
        if key in relations:
            target = relations[key]
            value = convert(target, value) if target in (Company, User) else financial(target, value)
        elif key in enums:
            value = enums[key](value)
        elif key == 'id' or key.endswith('_id') or key == 'captured_by':
            value = strawberry.ID(str(value))
        values[key] = value
    return kind(**values)


@strawberry.type
class FinanceQuery:
    @strawberry.field
    def accounts(self, info: Info, actor_company_user_id: strawberry.ID, company_id: strawberry.ID,
                 account_type: AccountType | None = strawberry.UNSET,
                 active_only: bool | None = strawberry.UNSET) -> list[Account]:
        return execute(info, lambda s: [financial(Account, x) for x in s.catalog(
            m.Account, company_id, plain(account_type), plain(active_only))], actor_company_user_id, 'accounts.read')

    @strawberry.field
    def concepts(self, info: Info, actor_company_user_id: strawberry.ID, company_id: strawberry.ID,
                 concept_type: ConceptType | None = strawberry.UNSET,
                 active_only: bool | None = strawberry.UNSET) -> list[Concept]:
        return execute(info, lambda s: [financial(Concept, x) for x in s.catalog(
            m.Concept, company_id, plain(concept_type), plain(active_only))], actor_company_user_id, 'concepts.read')

    @strawberry.field
    def account_concepts(self, info: Info, actor_company_user_id: strawberry.ID, account_id: strawberry.ID) -> list[AccountConcept]:
        return execute(info, lambda s: [financial(AccountConcept, x) for x in s.links(account_id)], actor_company_user_id, 'concepts.read')

    @strawberry.field
    def transactions(self, info: Info, actor_company_user_id: strawberry.ID, account_id: strawberry.ID | None = strawberry.UNSET,
                     transaction_type: TransactionType | None = strawberry.UNSET,
                     limit: int | None = strawberry.UNSET, offset: int | None = strawberry.UNSET) -> list[Transaction]:
        return execute(info, lambda s: [financial(Transaction, x) for x in s.transactions(
            plain(account_id), plain(transaction_type), plain(limit), plain(offset))], actor_company_user_id, 'transactions.read')

    @strawberry.field(description='Extensión: ingresos activos menos egresos activos, sin paginación.')
    def account_balance(self, info: Info, actor_company_user_id: strawberry.ID, account_id: strawberry.ID) -> Decimal:
        return execute(info, lambda s: s.balance(account_id), actor_company_user_id, 'transactions.read')


@strawberry.type
class FinanceMutation:
    @strawberry.mutation
    def create_account(self, info: Info, actor_company_user_id: strawberry.ID, input: CreateAccountInput) -> Account:
        return execute(info, lambda s: financial(Account, s.create_catalog(m.Account, fields(input))), actor_company_user_id, 'accounts.write')

    @strawberry.mutation
    def create_concept(self, info: Info, actor_company_user_id: strawberry.ID, input: CreateConceptInput) -> Concept:
        return execute(info, lambda s: financial(Concept, s.create_catalog(m.Concept, fields(input))), actor_company_user_id, 'concepts.write')

    @strawberry.mutation
    def assign_concept_to_account(self, info: Info, actor_company_user_id: strawberry.ID, input: AssignConceptToAccountInput) -> AccountConcept:
        return execute(info, lambda s: financial(AccountConcept, s.assign(input.account_id, input.concept_id)), actor_company_user_id, 'concepts.write')

    @strawberry.mutation
    def remove_concept_from_account(self, info: Info, actor_company_user_id: strawberry.ID, account_id: strawberry.ID, concept_id: strawberry.ID) -> bool:
        return execute(info, lambda s: s.remove_link(account_id, concept_id), actor_company_user_id, 'concepts.write')

    @strawberry.mutation
    def create_transaction(self, info: Info, actor_company_user_id: strawberry.ID, input: CreateTransactionInput) -> Transaction:
        return execute(info, lambda s: financial(Transaction, s.create_transaction(fields(input))), actor_company_user_id, 'transactions.write')

    @strawberry.mutation
    def delete_transaction(self, info: Info, actor_company_user_id: strawberry.ID, id: strawberry.ID) -> Transaction:
        return execute(info, lambda s: financial(Transaction, s.delete_transaction(id)), actor_company_user_id, 'transactions.write')
