from decimal import Decimal

from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from banking.models import Account, Card, Transaction

from .factories import PASSWORD, BankTestCase, make_account, make_user


class APITestCase(BankTestCase):
    def setUp(self):
        super().setUp()
        self.alice = make_user('alice')
        self.bob = make_user('bob')
        self.usd = make_account(self.alice, 'USD', '100.00')
        self.bob_usd = make_account(self.bob, 'USD', '5.00')
        self.api = APIClient()
        self.login(self.api, 'alice')

    def login(self, client, username):
        response = client.post(reverse('token_obtain_pair'), {'username': username, 'password': PASSWORD})
        self.assertEqual(response.status_code, 200, response.content)
        client.credentials(HTTP_AUTHORIZATION='Bearer ' + response.data['access'])


class AuthTests(APITestCase):
    def test_endpoints_need_a_token(self):
        anonymous = APIClient()
        for name in ('api-accounts', 'api-transactions', 'api-cards', 'api-me'):
            with self.subTest(endpoint=name):
                self.assertEqual(anonymous.get(reverse(name)).status_code, 401)
        self.assertEqual(anonymous.post(reverse('api-transfer'), {}).status_code, 401)

    def test_wrong_password(self):
        response = APIClient().post(reverse('token_obtain_pair'), {'username': 'alice', 'password': 'nope'})
        self.assertEqual(response.status_code, 401)

    def test_refresh_token(self):
        pair = APIClient().post(reverse('token_obtain_pair'), {'username': 'alice', 'password': PASSWORD}).data
        response = APIClient().post(reverse('token_refresh'), {'refresh': pair['refresh']})
        self.assertEqual(response.status_code, 200)
        self.assertIn('access', response.data)

    def test_swagger_schema_builds(self):
        response = APIClient().get('/swagger/?format=openapi')
        self.assertEqual(response.status_code, 200)
        self.assertIn('/transfer/', response.json()['paths'])


class AccountAPITests(APITestCase):
    def test_list_returns_only_my_accounts(self):
        response = self.api.get(reverse('api-accounts'))
        numbers = [row['number'] for row in response.data['results']] if 'results' in response.data else [
            row['number'] for row in response.data]
        self.assertEqual(numbers, [self.usd.number])

    def test_open_account(self):
        response = self.api.post(reverse('api-accounts'), {'account_type': 'savings', 'currency': 'EUR'})
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(Decimal(response.data['balance']), 0)
        self.assertTrue(response.data['number'].startswith('KB'))

    def test_balance_cannot_be_set_by_the_client(self):
        response = self.api.post(
            reverse('api-accounts'), {'account_type': 'savings', 'currency': 'EUR', 'balance': '1000000'}
        )
        self.assertEqual(Decimal(response.data['balance']), 0)

    def test_other_users_account_is_404(self):
        self.assertEqual(self.api.get(reverse('api-account', args=[self.bob_usd.pk])).status_code, 404)

    def test_close_account(self):
        empty = make_account(self.alice, 'USD', '0')
        response = self.api.post(reverse('api-account-close', args=[empty.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['is_active'])

    def test_close_account_with_money(self):
        response = self.api.post(reverse('api-account-close', args=[self.usd.pk]))
        self.assertEqual(response.status_code, 400)

    def test_account_cannot_be_deleted_over_the_api(self):
        self.assertEqual(self.api.delete(reverse('api-account', args=[self.usd.pk])).status_code, 405)


class TransferAPITests(APITestCase):
    def transfer(self, **fields):
        data = {'from_account_id': self.usd.pk, 'to_number': self.bob_usd.number, 'amount': '40.00'}
        data.update(fields)
        return self.api.post(reverse('api-transfer'), data)

    def test_transfer(self):
        response = self.transfer(description='rent')
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.data['to_number'], self.bob_usd.number)
        self.usd.refresh_from_db()
        self.bob_usd.refresh_from_db()
        self.assertEqual((self.usd.balance, self.bob_usd.balance), (Decimal('60.00'), Decimal('45.00')))

    def test_insufficient_funds(self):
        response = self.transfer(amount='500')
        self.assertEqual(response.status_code, 400)
        self.assertIn('Недостаточно', response.data['detail'])
        self.assertEqual(Transaction.objects.count(), 0)

    def test_bad_amounts(self):
        for amount in ('0', '-5', 'ten'):
            with self.subTest(amount=amount):
                self.assertEqual(self.transfer(amount=amount).status_code, 400)

    def test_cannot_spend_someone_elses_account(self):
        response = self.transfer(from_account_id=self.bob_usd.pk, to_number=self.usd.number)
        self.assertEqual(response.status_code, 404)
        self.bob_usd.refresh_from_db()
        self.assertEqual(self.bob_usd.balance, Decimal('5.00'))

    def test_bad_and_unknown_numbers(self):
        self.assertEqual(self.transfer(to_number='KB123').status_code, 400)
        self.assertEqual(self.transfer(to_number='KB0000000000000').status_code, 400)

    def test_history_lists_my_transactions(self):
        self.transfer()
        Transaction.objects.create(from_account=self.bob_usd, to_account=make_account(self.bob), amount=Decimal('1'))
        response = self.api.get(reverse('api-transactions'))
        rows = response.data['results'] if 'results' in response.data else response.data
        self.assertEqual(len(rows), 1)

    @override_settings(DEMO_MODE=True)
    def test_demo_deposit(self):
        response = self.api.post(reverse('api-account-deposit', args=[self.usd.pk]), {'amount': '10.00'})
        self.assertEqual(response.status_code, 201)
        self.usd.refresh_from_db()
        self.assertEqual(self.usd.balance, Decimal('110.00'))

    @override_settings(DEMO_MODE=False)
    def test_no_deposit_outside_demo_mode(self):
        response = self.api.post(reverse('api-account-deposit', args=[self.usd.pk]), {'amount': '10.00'})
        self.assertEqual(response.status_code, 400)
        self.usd.refresh_from_db()
        self.assertEqual(self.usd.balance, Decimal('100.00'))


class CardAPITests(APITestCase):
    def test_issue_and_list(self):
        response = self.api.post(reverse('api-card-issue'), {'account_id': self.usd.pk, 'card_type': 'debit'})
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(len(response.data['cvv']), 3)
        self.assertEqual(len(response.data['number']), 16)
        listing = self.api.get(reverse('api-cards'))
        rows = listing.data['results'] if 'results' in listing.data else listing.data
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]['number'].startswith('****'))
        self.assertNotIn('cvv', rows[0])
        self.assertEqual(Card.objects.count(), 1)

    def test_other_users_account(self):
        response = self.api.post(reverse('api-card-issue'), {'account_id': self.bob_usd.pk, 'card_type': 'debit'})
        self.assertEqual(response.status_code, 404)


class ThrottleTests(APITestCase):
    def test_login_attempts_are_limited(self):
        # DRF reads the rates when the class is imported, so patch the class for this test
        from rest_framework.throttling import AnonRateThrottle
        AnonRateThrottle.THROTTLE_RATES = {'anon': '3/minute'}
        try:
            codes = [
                APIClient().post(reverse('token_obtain_pair'), {'username': 'alice', 'password': 'x'}).status_code
                for _ in range(5)
            ]
        finally:
            AnonRateThrottle.THROTTLE_RATES = {'anon': '30/minute', 'user': '120/minute'}
        self.assertIn(429, codes)
