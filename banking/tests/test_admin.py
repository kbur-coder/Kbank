from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse

from banking.models import Transaction

from .factories import PASSWORD, BankTestCase, make_account, make_user


class ReadOnlyAdminTests(BankTestCase):
    def setUp(self):
        super().setUp()
        get_user_model().objects.create_superuser('root', 'root@example.com', PASSWORD)
        self.client.login(username='root', password=PASSWORD)
        self.alice = make_user('alice')
        self.account = make_account(self.alice, balance='10')
        self.tx = Transaction.objects.create(kind='deposit', to_account=self.account, amount=Decimal('10'))

    def test_lists_are_visible(self):
        for model in ('account', 'transaction', 'card'):
            with self.subTest(model=model):
                self.assertEqual(self.client.get(reverse(f'admin:banking_{model}_changelist')).status_code, 200)

    def test_rows_can_be_viewed_but_not_edited(self):
        url = reverse('admin:banking_account_change', args=[self.account.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.post(url, {'number': 'x', 'balance': '999999', 'currency': 'USD', 'account_type': 'checking'})
        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, Decimal('10'))

    def test_nothing_can_be_added(self):
        for model in ('account', 'transaction', 'card'):
            with self.subTest(model=model):
                self.assertEqual(self.client.get(reverse(f'admin:banking_{model}_add')).status_code, 403)

    def test_nothing_can_be_deleted(self):
        url = reverse('admin:banking_transaction_delete', args=[self.tx.pk])
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url, {'post': 'yes'}).status_code, 403)
        self.assertTrue(Transaction.objects.filter(pk=self.tx.pk).exists())
