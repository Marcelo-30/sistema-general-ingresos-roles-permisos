"""Tablas de la actividad 4; las anteriores se conservan sin migraciones destructivas."""
from datetime import datetime
from decimal import Decimal
from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator
from .db import Base, Timestamp
from .models import now, Company, User


class ExactDecimal(TypeDecorator):
    """SQLite NUMERIC convierte a float: TEXT conserva todos los dígitos."""
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if not isinstance(value, Decimal) or not value.is_finite() or value <= 0:
            raise ValueError('El monto debe ser un Decimal finito positivo.')
        return format(value, 'f')

    def process_result_value(self, value, dialect):
        return Decimal(value) if value is not None else None


class Account(Base):
    __tablename__ = 'accounts'
    __table_args__ = (UniqueConstraint('company_id', 'name_key', name='uq_account_name'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey('companies.id'))
    account_type: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(200))
    name_key: Mapped[str] = mapped_column(String(200))
    bank_name: Mapped[str | None]
    account_number: Mapped[str | None]
    clabe: Mapped[str | None]
    card_last_digits: Mapped[str | None]
    short_description: Mapped[str | None]
    long_description: Mapped[str | None]
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(Timestamp, default=now)
    updated_at: Mapped[datetime] = mapped_column(Timestamp, default=now, onupdate=now)
    company: Mapped[Company] = relationship()


class Concept(Base):
    __tablename__ = 'concepts'
    __table_args__ = (UniqueConstraint('company_id', 'concept_type', 'name_key', name='uq_concept_name'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey('companies.id'))
    concept_type: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(200))
    name_key: Mapped[str] = mapped_column(String(200))
    short_description: Mapped[str | None]
    long_description: Mapped[str | None]
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(Timestamp, default=now)
    updated_at: Mapped[datetime] = mapped_column(Timestamp, default=now, onupdate=now)


class AccountConcept(Base):
    __tablename__ = 'account_concepts'
    __table_args__ = (UniqueConstraint('account_id', 'concept_id', name='uq_account_concept'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey('accounts.id'))
    concept_id: Mapped[int] = mapped_column(ForeignKey('concepts.id'))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(Timestamp, default=now)
    account: Mapped[Account] = relationship()
    concept: Mapped[Concept] = relationship()


class Transaction(Base):
    __tablename__ = 'transactions'
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey('accounts.id'))
    concept_id: Mapped[int] = mapped_column(ForeignKey('concepts.id'))
    transaction_type: Mapped[str] = mapped_column(String(20))
    amount: Mapped[Decimal] = mapped_column(ExactDecimal())
    transaction_date: Mapped[datetime] = mapped_column(Timestamp)
    captured_at: Mapped[datetime] = mapped_column(Timestamp, default=now)
    captured_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    short_description: Mapped[str | None]
    long_description: Mapped[str | None]
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(Timestamp, default=now)
    updated_at: Mapped[datetime] = mapped_column(Timestamp, default=now, onupdate=now)
    account: Mapped[Account] = relationship()
    concept: Mapped[Concept] = relationship()
    captured_by_user: Mapped[User] = relationship()
