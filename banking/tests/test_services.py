from decimal import Decimal

from django.test import override_settings

from banking import services
from banking.models import Account, Card, Transaction

from .factories import BankTestCase, make_account, make_user


class OpenAndCloseTests(BankTestCase):
    def setUp(self):
        super().setUp()
        self.alice = make_user('alice')

    def test_open_account(self):
        account = services.open_account(self.alice, 'savings', 'EUR')
        self.assertEqual(account.balance, 0)
        self.assertTrue(account.number.startswith('KB'))
        self.assertTrue(account.is_active)

    def test_close_empty_account(self):
        account = make_account(self.alice)
        services.close_account(account.pk, self.alice)
        account.refresh_from_db()
        self.assertFalse(account.is_active)
        self.assertIsNotNone(account.closed_date)
        self.assertTrue(Account.objects.filter(pk=account.pk).exists())

    def test_close_deactivates_cards(self):
        account = make_account(self.alice)
        card, _ = services.issue_card(account.pk, self.alice, 'debit')
        services.close_account(account.pk, self.alice)
        card.refresh_from_db()
        self.assertFalse(card.is_active)

    def test_cannot_close_with_money(self):
        account = make_account(self.alice, balance='1')
        with self.assertRaises(services.BankError):
            services.close_account(account.pk, self.alice)

    def test_cannot_close_twice(self):
        account = make_account(self.alice)
        services.close_account(account.pk, self.alice)
        with self.assertRaises(services.AccountClosed):
            services.close_account(account.pk, self.alice)

    def test_cannot_close_someone_elses_account(self):
        bob = make_user('bob')
        account = make_account(bob)
        with self.assertRaises(services.NotYourAccount):
            services.close_account(account.pk, self.alice)


class TransferTests(BankTestCase):
    def setUp(self):
        super().setUp()
        self.alice = make_user('alice')
        self.bob = make_user('bob')
        self.usd = make_account(self.alice, 'USD', '100.00')
        self.bob_usd = make_account(self.bob, 'USD', '10.00')
        self.bob_eur = make_account(self.bob, 'EUR', '0')

    def balance(self, account):
        account.refresh_from_db()
        return account.balance

    def test_transfer_moves_money_and_writes_a_row(self):
        tx = services.transfer(self.usd.pk, self.bob_usd.pk, self.alice, '25.50', 'lunch')
        self.assertEqual(self.balance(self.usd), Decimal('74.50'))
        self.assertEqual(self.balance(self.bob_usd), Decimal('35.50'))
        self.assertEqual(tx.amount, Decimal('25.50'))
        self.assertEqual(tx.converted_amount, Decimal('25.50'))
        self.assertEqual(tx.description, 'lunch')

    def test_transfer_converts_currency(self):
        tx = services.transfer(self.usd.pk, self.bob_eur.pk, self.alice, '54.00')
        self.assertEqual(tx.converted_amount, Decimal('50.00'))
        self.assertEqual(self.balance(self.bob_eur), Decimal('50.00'))
        self.assertEqual(self.balance(self.usd), Decimal('46.00'))

    def test_money_is_conserved(self):
        before = self.usd.balance + self.bob_usd.balance
        services.transfer(self.usd.pk, self.bob_usd.pk, self.alice, '33.33')
        self.assertEqual(self.balance(self.usd) + self.balance(self.bob_usd), before)

    def test_all_the_money_can_be_sent(self):
        services.transfer(self.usd.pk, self.bob_usd.pk, self.alice, '100.00')
        self.assertEqual(self.balance(self.usd), 0)

    def test_insufficient_funds(self):
        with self.assertRaises(services.InsufficientFunds):
            services.transfer(self.usd.pk, self.bob_usd.pk, self.alice, '100.01')
        self.assertEqual(self.balance(self.usd), Decimal('100.00'))
        self.assertEqual(Transaction.objects.count(), 0)

    def test_bad_amounts(self):
        for amount in ('0', '-5', 'abc', '', '0.001', None):
            with self.subTest(amount=amount), self.assertRaises(services.InvalidAmount):
                services.transfer(self.usd.pk, self.bob_usd.pk, self.alice, amount)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_float_is_refused(self):
        with self.assertRaises(services.InvalidAmount):
            services.transfer(self.usd.pk, self.bob_usd.pk, self.alice, 0.1)

    def test_cannot_send_from_someone_elses_account(self):
        with self.assertRaises(services.NotYourAccount):
            services.transfer(self.bob_usd.pk, self.usd.pk, self.alice, '1')
        self.assertEqual(self.balance(self.bob_usd), Decimal('10.00'))

    def test_unknown_accounts(self):
        with self.assertRaises(services.NotYourAccount):
            services.transfer(self.usd.pk, 999999, self.alice, '1')
        with self.assertRaises(services.NotYourAccount):
            services.transfer(999999, self.usd.pk, self.alice, '1')

    def test_same_account(self):
        with self.assertRaises(services.SameAccount):
            services.transfer(self.usd.pk, self.usd.pk, self.alice, '1')

    def test_closed_accounts_do_not_take_part(self):
        services.close_account(self.bob_eur.pk, self.bob)
        with self.assertRaises(services.AccountClosed):
            services.transfer(self.usd.pk, self.bob_eur.pk, self.alice, '1')

    def test_amount_too_small_to_convert(self):
        eur = make_account(self.alice, 'EUR', '10')
        # 0.01 SUM is worth far less than one cent of EUR
        sum_source = make_account(self.alice, 'SUM', '1')
        with self.assertRaises(services.InvalidAmount):
            services.transfer(sum_source.pk, eur.pk, self.alice, '0.01')
        self.assertEqual(self.balance(sum_source), Decimal('1'))

    def test_between_own_accounts(self):
        mine = make_account(self.alice, 'USD', '0')
        services.transfer(self.usd.pk, mine.pk, self.alice, '40')
        self.assertEqual(self.balance(mine), Decimal('40.00'))


@override_settings(DEMO_MODE=True)
class DepositTests(BankTestCase):
    def setUp(self):
        super().setUp()
        self.alice = make_user('alice')
        self.account = make_account(self.alice)

    def test_deposit(self):
        tx = services.deposit(self.account.pk, self.alice, '75.25')
        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, Decimal('75.25'))
        self.assertEqual(tx.kind, Transaction.DEPOSIT)
        self.assertIsNone(tx.from_account)

    @override_settings(DEMO_MODE=False)
    def test_deposit_is_off_outside_demo_mode(self):
        with self.assertRaises(services.DemoModeOff):
            services.deposit(self.account.pk, self.alice, '10')
        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, 0)

    def test_deposit_checks_owner_and_amount(self):
        bob = make_user('bob')
        with self.assertRaises(services.NotYourAccount):
            services.deposit(self.account.pk, bob, '10')
        with self.assertRaises(services.InvalidAmount):
            services.deposit(self.account.pk, self.alice, '-10')
        with self.assertRaises(services.InvalidAmount):
            services.deposit(self.account.pk, self.alice, '99999999999999')

    def test_deposit_into_closed_account(self):
        services.close_account(self.account.pk, self.alice)
        with self.assertRaises(services.AccountClosed):
            services.deposit(self.account.pk, self.alice, '1')


class CardTests(BankTestCase):
    def setUp(self):
        super().setUp()
        self.alice = make_user('alice', first_name='Alice', last_name='Karimova')
        self.account = make_account(self.alice)

    def test_issue_card(self):
        card, cvv = services.issue_card(self.account.pk, self.alice, 'debit')
        self.assertEqual(len(card.number), 16)
        self.assertEqual(len(cvv), 3)
        self.assertEqual(card.owner_name, 'ALICE KARIMOVA')
        self.assertGreater(card.expiry_date.year, 2025)
        self.assertEqual(card.expiry_date.day, 1)

    def test_cvv_is_not_stored(self):
        card, cvv = services.issue_card(self.account.pk, self.alice, 'debit')
        row = Card.objects.filter(pk=card.pk).values().get()
        self.assertNotIn(cvv, [str(v) for k, v in row.items() if k != 'number'])
        self.assertNotIn('cvv', row)

    def test_card_for_someone_elses_or_closed_account(self):
        bob = make_user('bob')
        with self.assertRaises(services.NotYourAccount):
            services.issue_card(self.account.pk, bob, 'debit')
        services.close_account(self.account.pk, self.alice)
        with self.assertRaises(services.AccountClosed):
            services.issue_card(self.account.pk, self.alice, 'debit')


class FindAccountTests(BankTestCase):
    def test_find_by_number_ignores_spaces_and_case(self):
        account = make_account(make_user('alice'))
        text = f'{account.number[:2].lower()} {account.number[2:]}'
        self.assertEqual(services.find_account_by_number(text), account)
        self.assertIsNone(services.find_account_by_number('KB0000000000000'))
