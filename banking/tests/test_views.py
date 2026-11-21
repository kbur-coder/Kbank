from decimal import Decimal

from django.test import override_settings
from django.urls import reverse

from banking.models import Account, Card, Transaction

from .factories import PASSWORD, BankTestCase, make_account, make_user


class WebTestCase(BankTestCase):
    def setUp(self):
        super().setUp()
        self.alice = make_user('alice', first_name='Alice', last_name='K')
        self.bob = make_user('bob')
        self.client.login(username='alice', password=PASSWORD)
        self.usd = make_account(self.alice, 'USD', '100.00')
        self.bob_usd = make_account(self.bob, 'USD', '5.00')


class PageTests(WebTestCase):
    def test_every_page_renders(self):
        Transaction.objects.create(from_account=self.usd, to_account=self.bob_usd, amount=Decimal('1'))
        Transaction.objects.create(kind='deposit', to_account=self.usd, amount=Decimal('9'))
        urls = [
            reverse('home'), reverse('account-list'), reverse('account-detail', args=[self.usd.pk]),
            reverse('account-create'), reverse('account-delete', args=[self.usd.pk]),
            reverse('account-deposit', args=[self.usd.pk]), reverse('transaction-list'),
            reverse('transfer'), reverse('card-list'), reverse('card-create'),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_other_users_accounts_are_hidden(self):
        for name in ('account-detail', 'account-delete', 'account-deposit'):
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(name, args=[self.bob_usd.pk])).status_code, 404)

    def test_account_list_shows_only_my_accounts(self):
        response = self.client.get(reverse('account-list'))
        self.assertContains(response, self.usd.number)
        self.assertNotContains(response, self.bob_usd.number)

    def test_deposit_shows_up_in_history(self):
        Transaction.objects.create(kind='deposit', to_account=self.usd, amount=Decimal('9'))
        self.assertContains(self.client.get(reverse('transaction-list')), 'Пополнение')

    def test_history_can_be_filtered_by_account(self):
        other = make_account(self.alice, 'USD', '1')
        Transaction.objects.create(kind='deposit', to_account=other, amount=Decimal('3'), description='only-other')
        Transaction.objects.create(kind='deposit', to_account=self.usd, amount=Decimal('4'), description='only-usd')
        response = self.client.get(reverse('transaction-list') + f'?account={other.pk}')
        self.assertContains(response, 'only-other')
        self.assertNotContains(response, 'only-usd')


class AccountViewTests(WebTestCase):
    def test_open_account(self):
        response = self.client.post(reverse('account-create'), {'account_type': 'savings', 'currency': 'EUR'})
        self.assertRedirects(response, reverse('account-list'))
        account = Account.objects.filter(owner=self.alice, currency='EUR').get()
        self.assertEqual(account.balance, 0)
        self.assertTrue(account.number.startswith('KB'))

    def test_open_account_rejects_a_bad_currency(self):
        response = self.client.post(reverse('account-create'), {'account_type': 'savings', 'currency': 'XXX'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Account.objects.filter(owner=self.alice).count(), 1)

    def test_close_account(self):
        empty = make_account(self.alice, 'USD', '0')
        response = self.client.post(reverse('account-delete', args=[empty.pk]))
        self.assertRedirects(response, reverse('account-list'))
        empty.refresh_from_db()
        self.assertFalse(empty.is_active)

    def test_account_with_money_stays_open(self):
        response = self.client.post(reverse('account-delete', args=[self.usd.pk]))
        self.assertRedirects(response, reverse('account-detail', args=[self.usd.pk]))
        self.usd.refresh_from_db()
        self.assertTrue(self.usd.is_active)


class TransferViewTests(WebTestCase):
    def post(self, **fields):
        data = {'from_account': self.usd.pk, 'to_number': self.bob_usd.number, 'amount': '30.00'}
        data.update(fields)
        return self.client.post(reverse('transfer'), data)

    def test_transfer_by_account_number(self):
        response = self.post(description='thanks')
        self.assertRedirects(response, reverse('transaction-list'))
        self.usd.refresh_from_db()
        self.bob_usd.refresh_from_db()
        self.assertEqual(self.usd.balance, Decimal('70.00'))
        self.assertEqual(self.bob_usd.balance, Decimal('35.00'))
        self.assertEqual(Transaction.objects.get().description, 'thanks')

    def test_number_with_spaces_works(self):
        number = self.bob_usd.number
        self.post(to_number=f'{number[:4]} {number[4:9]} {number[9:]}')
        self.assertEqual(Transaction.objects.count(), 1)

    def test_typo_in_number(self):
        number = self.bob_usd.number
        wrong = number[:-1] + str((int(number[-1]) + 1) % 10)
        response = self.post(to_number=wrong)
        self.assertContains(response, 'Некорректный номер счета')
        self.assertEqual(Transaction.objects.count(), 0)

    def test_unknown_number(self):
        response = self.post(to_number='KB0000000000000')
        self.assertContains(response, 'не найден')

    def test_not_enough_money(self):
        response = self.post(amount='100.01')
        self.assertContains(response, 'Недостаточно средств')
        self.assertEqual(Transaction.objects.count(), 0)

    def test_bad_amounts(self):
        for amount in ('0', '-1', 'abc', '1.234'):
            with self.subTest(amount=amount):
                self.assertEqual(self.post(amount=amount).status_code, 200)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_cannot_use_someone_elses_source_account(self):
        response = self.post(from_account=self.bob_usd.pk, to_number=self.usd.number)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_same_account(self):
        self.assertContains(self.post(to_number=self.usd.number), 'тот же счет')

    def test_source_account_is_preselected(self):
        response = self.client.get(reverse('transfer') + f'?from_account={self.usd.pk}')
        self.assertEqual(response.context['form'].initial['from_account'], str(self.usd.pk))

    def test_transfer_with_currency_conversion(self):
        eur = make_account(self.bob, 'EUR', '0')
        self.post(to_number=eur.number, amount='54.00')
        eur.refresh_from_db()
        self.assertEqual(eur.balance, Decimal('50.00'))


class DepositViewTests(WebTestCase):
    @override_settings(DEMO_MODE=True)
    def test_deposit_in_demo_mode(self):
        response = self.client.post(reverse('account-deposit', args=[self.usd.pk]), {'amount': '25.00'})
        self.assertRedirects(response, reverse('account-detail', args=[self.usd.pk]))
        self.usd.refresh_from_db()
        self.assertEqual(self.usd.balance, Decimal('125.00'))

    @override_settings(DEMO_MODE=True)
    def test_deposit_button_is_shown_in_demo_mode(self):
        self.assertContains(self.client.get(reverse('account-detail', args=[self.usd.pk])), 'Пополнить')

    @override_settings(DEMO_MODE=False)
    def test_no_deposit_outside_demo_mode(self):
        url = reverse('account-deposit', args=[self.usd.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, {'amount': '25'}).status_code, 404)
        self.assertNotContains(self.client.get(reverse('account-detail', args=[self.usd.pk])), 'Пополнить')
        self.usd.refresh_from_db()
        self.assertEqual(self.usd.balance, Decimal('100.00'))


class CardViewTests(WebTestCase):
    def test_issue_card_shows_cvv_once(self):
        response = self.client.post(
            reverse('card-create'), {'account': self.usd.pk, 'card_type': 'debit'}, follow=True
        )
        card = Card.objects.get()
        self.assertContains(response, 'CVV:')
        self.assertContains(response, card.number[-4:])
        self.assertNotContains(response, card.number)  # only the last four digits are displayed
        again = self.client.get(reverse('card-list'))
        self.assertNotContains(again, 'CVV:')

    def test_cannot_issue_a_card_for_someone_elses_account(self):
        response = self.client.post(reverse('card-create'), {'account': self.bob_usd.pk, 'card_type': 'debit'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Card.objects.count(), 0)
