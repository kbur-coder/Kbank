from io import StringIO

from django.core.management import CommandError, call_command
from django.test import override_settings

from banking.models import Account, Card, Transaction

from .factories import BankTestCase


@override_settings(DEMO_MODE=True)
class SeedDemoTests(BankTestCase):
    def run_seed(self):
        out = StringIO()
        call_command('seed_demo', stdout=out)
        return out.getvalue()

    def test_creates_users_accounts_card_and_history(self):
        self.run_seed()
        self.assertEqual(Account.objects.count(), 3)
        self.assertEqual(Card.objects.count(), 2)
        self.assertEqual(Transaction.objects.filter(kind='deposit').count(), 3)
        self.assertEqual(Transaction.objects.filter(kind='transfer').count(), 3)

    def test_balances_add_up(self):
        self.run_seed()
        for account in Account.objects.all():
            incoming = sum(t.received_amount for t in account.incoming_transactions.all())
            outgoing = sum(t.amount for t in account.outgoing_transactions.all())
            self.assertEqual(account.balance, incoming - outgoing, account.number)

    def test_running_twice_changes_nothing(self):
        self.run_seed()
        self.assertIn('already exist', self.run_seed())
        self.assertEqual(Account.objects.count(), 3)

    @override_settings(DEMO_MODE=False)
    def test_refuses_to_run_outside_demo_mode(self):
        with self.assertRaises(CommandError):
            self.run_seed()
        self.assertEqual(Account.objects.count(), 0)
