from datetime import timezone
from decimal import Decimal, localcontext
from sqlalchemy import select
from . import models as m
from .service import Service, fail, identifier, name


class FinanceService(Service):
    def company_ids(self):
        if self.actor_company_user_id is not None:
            from .access import membership
            return [membership(self.db, self.actor_company_user_id).company_id]
        user = self.actor()
        return list(self.db.scalars(select(m.CompanyUser.company_id).join(m.Company).where(
            m.CompanyUser.user_id == user.id, m.CompanyUser.is_active.is_(True),
            m.Company.is_active.is_(True))))

    def authorize(self, company_id):
        if company_id not in self.company_ids():
            fail('No tienes autorización en esta empresa.', 'FORBIDDEN')

    def owned(self, model, value):
        self.actor()
        obj = self.db.get(model, identifier(value))
        if obj is None:
            fail('Cuenta, concepto o movimiento inexistente.', 'NOT_FOUND')
        cid = obj.account.company_id if model is m.Transaction else obj.company_id
        self.authorize(cid)
        return obj

    def catalog(self, model, company_id, kind=None, active_only=None):
        cid = identifier(company_id)
        self.authorize(cid)
        query = select(model).where(model.company_id == cid).order_by(model.id)
        if kind is not None:
            field = model.account_type if model is m.Account else model.concept_type
            query = query.where(field == kind)
        if active_only:
            query = query.where(model.is_active.is_(True))
        return list(self.db.scalars(query))

    def create_catalog(self, model, fields):
        fields = dict(fields)
        cid = fields['company_id'] = identifier(fields['company_id'])
        self.authorize(cid)
        fields['name'] = ' '.join(name(fields['name']).split())
        fields['name_key'] = fields['name'].casefold()
        query = select(model.id).where(model.company_id == cid, model.name_key == fields['name_key'])
        if model is m.Concept:
            query = query.where(model.concept_type == fields['concept_type'])
        if self.db.scalar(query):
            fail('Ya existe una cuenta o concepto con ese nombre.', 'CONFLICT')
        for key in ('bank_name', 'account_number', 'clabe', 'card_last_digits'):
            if fields.get(key) is not None:
                fields[key] = ' '.join(fields[key].split()) or None
        obj = model(**fields)
        self.db.add(obj)
        self.db.flush()
        return obj

    def pair(self, account_id, concept_id):
        account = self.owned(m.Account, account_id)
        concept = self.owned(m.Concept, concept_id)
        if account.company_id != concept.company_id:
            fail('La cuenta y el concepto deben pertenecer a la misma empresa.', 'FORBIDDEN')
        return account, concept

    def relation(self, account_id, concept_id):
        return self.db.scalar(select(m.AccountConcept).where(
            m.AccountConcept.account_id == account_id, m.AccountConcept.concept_id == concept_id))

    def assign(self, account_id, concept_id):
        account, concept = self.pair(account_id, concept_id)
        if not account.is_active or not concept.is_active:
            fail('La cuenta y el concepto deben estar activos.')
        link = self.relation(account.id, concept.id)
        if link and link.is_active:
            fail('El concepto ya está asignado a la cuenta.', 'CONFLICT')
        if link:
            link.is_active = True
        else:
            link = m.AccountConcept(account_id=account.id, concept_id=concept.id)
            self.db.add(link)
        self.db.flush()
        return link

    def links(self, account_id):
        account = self.owned(m.Account, account_id)
        return list(self.db.scalars(select(m.AccountConcept).where(
            m.AccountConcept.account_id == account.id, m.AccountConcept.is_active.is_(True))
            .order_by(m.AccountConcept.id)))

    def remove_link(self, account_id, concept_id):
        account, concept = self.pair(account_id, concept_id)
        link = self.relation(account.id, concept.id)
        if not link or not link.is_active:
            return False
        link.is_active = False
        self.db.flush()
        return True

    def create_transaction(self, fields):
        fields = dict(fields)
        actor = self.actor()
        account, concept = self.pair(fields['account_id'], fields['concept_id'])
        amount = fields['amount']
        if not isinstance(amount, Decimal) or not amount.is_finite() or amount <= 0:
            fail('El monto debe ser un decimal finito estrictamente mayor que cero.')
        if len(amount.as_tuple().digits) > 100 or abs(amount.as_tuple().exponent) > 100:
            fail('El monto excede 100 dígitos o 100 posiciones decimales.')
        if not account.is_active or not concept.is_active:
            fail('La cuenta y el concepto deben estar activos.')
        link = self.relation(account.id, concept.id)
        if not link or not link.is_active:
            fail('El concepto no está permitido para esta cuenta.')
        if fields['transaction_type'] != concept.concept_type:
            fail('El tipo de movimiento no coincide con el concepto.')
        instant = m.now()
        date = fields.pop('transaction_date', None) or instant
        if date.tzinfo is None:
            fail('transactionDate requiere zona horaria.')
        obj = m.Transaction(**{**fields, 'account_id': account.id, 'concept_id': concept.id},
                            transaction_date=date.astimezone(timezone.utc), captured_at=instant,
                            captured_by=actor.id)
        self.db.add(obj)
        self.db.flush()
        return obj

    def transaction_query(self, account_id=None, transaction_type=None):
        ids = self.company_ids()
        query = select(m.Transaction).join(m.Account).where(
            m.Account.company_id.in_(ids), m.Transaction.is_active.is_(True))
        if account_id is not None:
            account = self.owned(m.Account, account_id)
            query = query.where(m.Transaction.account_id == account.id)
        if transaction_type is not None:
            query = query.where(m.Transaction.transaction_type == transaction_type)
        return query.order_by(m.Transaction.id)

    def transactions(self, account_id=None, transaction_type=None, limit=None, offset=None):
        query = self.transaction_query(account_id, transaction_type)
        if limit is not None and limit < 0 or offset is not None and offset < 0:
            fail('limit y offset deben ser no negativos.')
        return list(self.db.scalars(query.limit(100 if limit is None else limit).offset(offset or 0)))

    def delete_transaction(self, value):
        obj = self.owned(m.Transaction, value)
        obj.is_active = False
        self.db.flush()
        return obj

    def balance(self, account_id):
        rows = list(self.db.scalars(self.transaction_query(account_id)))
        # Hasta 200 posiciones enteras y 100 fraccionarias; margen para N sumandos.
        with localcontext() as context:
            context.prec = 302 + len(str(len(rows)))
            return sum((x.amount if x.transaction_type == 'INCOME' else -x.amount
                        for x in rows), Decimal('0'))
