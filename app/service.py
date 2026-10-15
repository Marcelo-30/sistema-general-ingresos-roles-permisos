import hmac
from datetime import timedelta
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from email_validator import validate_email, EmailNotValidError
from graphql import GraphQLError
from sqlalchemy import select
from . import models as m

hasher = PasswordHasher()


def fail(message, code='BAD_INPUT'):
    raise GraphQLError(message, extensions={'code': code})


def identifier(value):
    try:
        result = int(value)
        if result < 1:
            raise ValueError
        return result
    except (ValueError, TypeError):
        fail('Identificador inválido.')


def name(value):
    if value is None or not value.strip() or len(value.strip()) > 200:
        fail('El nombre debe tener entre 1 y 200 caracteres.')
    return value.strip()


def email(value):
    try:
        return validate_email(value.strip(), check_deliverability=False).normalized.casefold()
    except (EmailNotValidError, AttributeError):
        fail('Correo inválido.')


class Service:
    def __init__(self, session, settings, headers, actor_company_user_id=None):
        self.db, self.settings, self.headers = session, settings, headers
        self.actor_company_user_id = actor_company_user_id
        self.required_permissions = set()

    def require(self, code):
        from .access import exigir_permiso
        if self.actor_company_user_id is None:
            fail('Se requiere actorCompanyUserId.', 'FORBIDDEN')
        exigir_permiso(self.db, self.actor_company_user_id, code)
        self.required_permissions.add(code)

    def check_before_commit(self):
        from .access import exigir_permiso
        for code in sorted(self.required_permissions):
            exigir_permiso(self.db, self.actor_company_user_id, code)

    def bootstrap(self):
        supplied = self.headers.get('x-bootstrap-key', '')
        if not hmac.compare_digest(supplied.encode(), self.settings.bootstrap_key.encode()):
            fail('Se requiere la clave de inicialización.', 'FORBIDDEN')

    def actor(self):
        if self.actor_company_user_id is not None:
            from .access import membership
            return membership(self.db, self.actor_company_user_id).user
        auth = self.headers.get('authorization', '')
        try:
            scheme, token = auth.split(' ', 1)
            if scheme.lower() != 'bearer':
                raise ValueError
            data = jwt.decode(token, self.settings.jwt_secret, algorithms=['HS256'],
                              issuer='empresa-api', audience='empresa-api',
                              options={'require': ['exp', 'iat', 'sub', 'iss', 'aud']})
            user = self.db.get(m.User, int(data['sub']))
        except (jwt.PyJWTError, ValueError, KeyError, TypeError):
            fail('Token ausente, inválido o expirado.', 'UNAUTHENTICATED')
        if not user or not user.is_active:
            fail('Usuario inactivo o inexistente.', 'UNAUTHENTICATED')
        return user

    def admin(self, company_id):
        from .access import membership
        self.require('company.users.write')
        member = membership(self.db, self.actor_company_user_id)
        if member.company_id != company_id:
            fail('No tienes autorización en esta empresa.', 'FORBIDDEN')
        return member

    def company(self, value):
        company = self.db.get(m.Company, identifier(value))
        if not company:
            fail('Empresa inexistente.', 'NOT_FOUND')
        return company

    def companies(self, active_only):
        self.bootstrap()
        stmt = select(m.Company).order_by(m.Company.id)
        if active_only:
            stmt = stmt.where(m.Company.is_active.is_(True))
        return list(self.db.scalars(stmt))

    def get_company(self, value):
        self.bootstrap()
        return self.db.get(m.Company, identifier(value))

    def company_fields(self, fields):
        if 'name' in fields:
            fields['name'] = name(fields['name'])
        if fields.get('email') is not None:
            fields['email'] = email(fields['email'])
        for key, limit in [('legal_name', 250), ('tax_id', 50), ('phone', 50)]:
            if fields.get(key) is not None:
                fields[key] = fields[key].strip()
                if not fields[key] or len(fields[key]) > limit:
                    fail(f'{key}: longitud inválida.')
        if 'is_active' in fields and fields['is_active'] is None:
            fail('isActive no admite null.')
        return fields

    def create_company(self, fields):
        self.bootstrap()
        company = m.Company(**self.company_fields(fields))
        self.db.add(company)
        self.db.flush()
        return company

    def update_company(self, value, fields):
        self.bootstrap()
        company = self.company(value)
        for key, val in self.company_fields(fields).items():
            setattr(company, key, val)
        company.updated_at = m.now()
        self.db.flush()
        return company

    def create_member(self, fields, admin):
        cid = identifier(fields['company_id'])
        if admin:
            self.bootstrap()
        else:
            self.admin(cid)
        company = self.company(cid)
        if not company.is_active:
            fail('La empresa está inactiva.', 'FORBIDDEN')
        if admin and self.db.scalar(select(m.CompanyUser.id).where(
                m.CompanyUser.company_id == cid, m.CompanyUser.is_admin.is_(True))):
            fail('La empresa ya tiene administrador.', 'CONFLICT')
        normalized = email(fields['email'])
        if self.db.scalar(select(m.User.id).where(m.User.email == normalized)):
            fail('El correo ya está registrado.', 'CONFLICT')
        password = fields['password']
        if not 10 <= len(password) <= 128:
            fail('La contraseña debe tener entre 10 y 128 caracteres.')
        user = m.User(name=name(fields['name']), email=normalized,
                      password_hash=hasher.hash(password))
        member = m.CompanyUser(company=company, user=user, is_admin=admin)
        self.db.add(member)
        self.db.flush()
        from .access import assign, role_by_code
        assign(self.db, member, role_by_code(self.db, 'ADMINISTRADOR' if admin else 'CONSULTA'))
        return member

    def members(self, value):
        cid = identifier(value)
        from .access import membership
        self.require('company.users.read')
        if membership(self.db, self.actor_company_user_id).company_id != cid:
            fail('No tienes autorización en esta empresa.', 'FORBIDDEN')
        return list(self.db.scalars(select(m.CompanyUser).where(
            m.CompanyUser.company_id == cid).order_by(m.CompanyUser.id)))

    def deactivate_member(self, value):
        self.actor()
        member = self.db.get(m.CompanyUser, identifier(value))
        if not member:
            fail('Membresía no disponible.', 'FORBIDDEN')
        self.admin(member.company_id)
        if member.is_admin:
            fail('No se puede desactivar al administrador principal.', 'CONFLICT')
        member.is_active = False
        self.db.flush()
        return member

    def login(self, fields):
        user = self.db.scalar(select(m.User).where(m.User.email == email(fields['email'])))
        try:
            if not user or not user.is_active:
                fail('Credenciales incorrectas.', 'UNAUTHENTICATED')
            hasher.verify(user.password_hash, fields['password'])
        except (VerificationError, InvalidHashError):
            fail('Credenciales incorrectas.', 'UNAUTHENTICATED')
        active = self.db.scalar(select(m.CompanyUser.id).join(m.Company).where(
            m.CompanyUser.user_id == user.id, m.CompanyUser.is_active.is_(True),
            m.Company.is_active.is_(True)))
        if active is None:
            fail('No tienes membresías activas en empresas activas.', 'FORBIDDEN')
        instant = m.now()
        token = jwt.encode({'sub': str(user.id), 'iat': instant,
                            'exp': instant + timedelta(minutes=self.settings.jwt_expire_minutes),
                            'iss': 'empresa-api', 'aud': 'empresa-api'},
                           self.settings.jwt_secret, algorithm='HS256')
        return token, user
