from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings

from banking import money
from banking.models import Account

# Password hashing is deliberately slow; the tests do not need that.
FAST_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
PASSWORD = 'correct-horse-battery'


def make_user(username='alice', **extra):
    return get_user_model().objects.create_user(username, f'{username}@example.com', PASSWORD, **extra)


def make_account(owner, currency='USD', balance='0', account_type='checking', **extra):
    return Account.objects.create(
        owner=owner,
        number=money.generate_account_number(),
        account_type=account_type,
        currency=currency,
        balance=Decimal(balance),
        **extra,
    )


@override_settings(PASSWORD_HASHERS=FAST_HASHERS)
class BankTestCase(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()  # the API throttle counters live in the cache
