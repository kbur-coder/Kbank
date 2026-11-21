from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from banking import services
from banking.models import Account

DEMO_PASSWORD = 'demo-pass-2025'

DEMO_USERS = [
    # username, first name, last name, [(account type, currency, opening balance)]
    ('alice', 'Alice', 'Karimova', [('checking', 'USD', '1500.00'), ('savings', 'SUM', '25000000.00')]),
    ('bob', 'Bob', 'Yusupov', [('checking', 'EUR', '800.00')]),
]


class Command(BaseCommand):
    help = 'Create two demo users with accounts, a card and a few transfers (DEMO_MODE only).'

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEMO_MODE:
            raise CommandError('seed_demo needs DEMO_MODE=True, it uses the demo top-up.')
        User = get_user_model()
        if User.objects.filter(username__in=[u[0] for u in DEMO_USERS]).exists():
            self.stdout.write('Demo users already exist, nothing to do.')
            return

        accounts = {}
        for username, first, last, wallet in DEMO_USERS:
            user = User.objects.create_user(username, f'{username}@example.com', DEMO_PASSWORD,
                                            first_name=first, last_name=last)
            for account_type, currency, balance in wallet:
                account = services.open_account(user, account_type, currency)
                services.deposit(account.pk, user, balance, 'Начальный остаток')
                accounts.setdefault(username, []).append(account)
            services.issue_card(accounts[username][0].pk, user, 'debit')

        alice, bob = User.objects.get(username='alice'), User.objects.get(username='bob')
        usd, eur = accounts['alice'][0], accounts['bob'][0]
        services.transfer(usd.pk, eur.pk, alice, '100.00', 'Подарок на день рождения')
        services.transfer(eur.pk, usd.pk, bob, '20.00', 'Сдача')
        services.transfer(accounts['alice'][1].pk, usd.pk, alice, '1000000.00', 'Конвертация сумов')

        self.stdout.write(self.style.SUCCESS(
            f'Created users alice and bob (password: {DEMO_PASSWORD}), '
            f'{Account.objects.count()} accounts.'
        ))
