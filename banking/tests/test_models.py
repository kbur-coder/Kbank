from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import ProtectedError

from banking.models import Account, Card, Transaction

from .factories import BankTestCase, make_account, make_user


class LedgerRuleTests(BankTestCase):
    def setUp(self):
        super().setUp()
        self.alice = make_user('alice')
        self.a = make_account(self.alice, balance='100')
        self.b = make_account(self.alice, balance='50')

    def fails(self, **fields):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Transaction.objects.create(**fields)

    def test_balance_cannot_be_negative(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Account.objects.filter(pk=self.a.pk).update(balance=Decimal('-0.01'))

    def test_amount_must_be_positive(self):
        self.fails(from_account=self.a, to_account=self.b, amount=Decimal('0'))
        self.fails(from_account=self.a, to_account=self.b, amount=Decimal('-5'))

    def test_transfer_needs_a_source(self):
        self.fails(kind='transfer', from_account=None, to_account=self.b, amount=Decimal('5'))

    def test_deposit_has_no_source(self):
        tx = Transaction.objects.create(kind='deposit', to_account=self.b, amount=Decimal('5'))
        self.assertIsNone(tx.from_account)
        self.assertEqual(tx.received_amount, Decimal('5'))

    def test_cannot_transfer_to_the_same_account(self):
        self.fails(from_account=self.a, to_account=self.a, amount=Decimal('5'))

    def test_received_amount_prefers_converted(self):
        tx = Transaction.objects.create(
            from_account=self.a, to_account=self.b, amount=Decimal('10'), converted_amount=Decimal('9.25')
        )
        self.assertEqual(tx.received_amount, Decimal('9.25'))

    def test_account_with_history_cannot_be_deleted(self):
        Transaction.objects.create(from_account=self.a, to_account=self.b, amount=Decimal('5'))
        with self.assertRaises(ProtectedError):
            self.a.delete()

    def test_user_with_accounts_cannot_be_deleted(self):
        with self.assertRaises(ProtectedError):
            self.alice.delete()

    def test_numbers_are_unique(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Account.objects.create(owner=self.alice, number=self.a.number, account_type='savings', currency='USD')

    def test_account_number_is_validated(self):
        from django.core.exceptions import ValidationError
        account = Account(owner=self.alice, number='KB123', account_type='savings', currency='USD')
        with self.assertRaises(ValidationError) as caught:
            account.full_clean()
        self.assertIn('number', caught.exception.message_dict)

    def test_card_has_no_cvv_column(self):
        self.assertNotIn('cvv', [f.name for f in Card._meta.get_fields()])
