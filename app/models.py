from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base, Timestamp


def now():
    return datetime.now(timezone.utc)


class Company(Base):
    __tablename__ = 'companies'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    legal_name: Mapped[str | None] = mapped_column(String(250))
    tax_id: Mapped[str | None] = mapped_column(String(50))
    email: Mapped[str | None] = mapped_column(String(254))
    phone: Mapped[str | None] = mapped_column(String(50))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(Timestamp, default=now)
    updated_at: Mapped[datetime] = mapped_column(Timestamp, default=now, onupdate=now)
    memberships: Mapped[list['CompanyUser']] = relationship(back_populates='company')


class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(Timestamp, default=now)
    updated_at: Mapped[datetime] = mapped_column(Timestamp, default=now, onupdate=now)
    memberships: Mapped[list['CompanyUser']] = relationship(back_populates='user')


class CompanyUser(Base):
    __tablename__ = 'company_users'
    __table_args__ = (
        UniqueConstraint('company_id', 'user_id', name='uq_company_user'),
        Index('uq_company_admin', 'company_id', unique=True, sqlite_where=text('is_admin = 1')).ddl_if(dialect='sqlite'),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey('companies.id'))
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    joined_at: Mapped[datetime] = mapped_column(Timestamp, default=now)
    company: Mapped[Company] = relationship(back_populates='memberships')
    user: Mapped[User] = relationship(back_populates='memberships')

# Registro de las tablas financieras de la actividad 4.
from .finance_models import Account, Concept, AccountConcept, Transaction
