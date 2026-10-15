"""Catálogos globales y asignaciones; independientes de los tipos GraphQL."""
from sqlalchemy import Boolean, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base
from .models import CompanyUser


class RoleModel(Base):
    __tablename__ = 'roles'
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class PermissionModel(Base):
    __tablename__ = 'permissions'
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class RolePermissionModel(Base):
    __tablename__ = 'role_permissions'
    __table_args__ = (UniqueConstraint('role_id', 'permission_id', name='uq_role_permission'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey('roles.id'))
    permission_id: Mapped[int] = mapped_column(ForeignKey('permissions.id'))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    role: Mapped[RoleModel] = relationship()
    permission: Mapped[PermissionModel] = relationship()


class CompanyUserRoleModel(Base):
    __tablename__ = 'company_user_roles'
    __table_args__ = (
        UniqueConstraint('company_user_id', 'role_id', name='uq_member_role'),
        Index('uq_member_active_role', 'company_user_id', unique=True,
              sqlite_where=text('is_active = 1')).ddl_if(dialect='sqlite'),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    company_user_id: Mapped[int] = mapped_column(ForeignKey('company_users.id'))
    role_id: Mapped[int] = mapped_column(ForeignKey('roles.id'))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    company_user: Mapped[CompanyUser] = relationship()
    role: Mapped[RoleModel] = relationship()
