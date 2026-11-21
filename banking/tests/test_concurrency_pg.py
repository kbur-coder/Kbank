"""Race conditions need a real database with row locks, so these run on PostgreSQL only.

    DATABASE_URL=postgres://user:pass@localhost/bank python manage.py test banking.tests.test_concurrency_pg
"""
import threading
from decimal import Decimal
from unittest import skipUnless

from django.db import connection, connections
from django.test import TransactionTestCase

from banking import services
from banking.models import Account, Transaction

from .factories import make_account, make_user


def run_in_threads(jobs):
    errors, results = [], []

    def wrap(job):
        try:
            results.append(job())
        except services.BankError as error:
            errors.append(error)
        finally:
            connections.close_all()

    barrier = threading.Barrier(len(jobs))

    def start(job):
        barrier.wait()
        wrap(job)

    threads = [threading.Thread(target=start, args=(job,)) for job in jobs]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
        assert not thread.is_alive(), 'a transfer is stuck: possible deadlock'
    return results, errors


@skipUnless(connection.vendor == 'postgresql', 'needs PostgreSQL (row locks)')
class ConcurrentTransferTests(TransactionTestCase):
    def setUp(self):
        self.alice = make_user('alice')
        self.bob = make_user('bob')
        self.a = make_account(self.alice, 'USD', '100.00')
        self.b = make_account(self.bob, 'USD', '0.00')

    def test_the_same_money_cannot_be_spent_twice(self):
        jobs = [lambda: services.transfer(self.a.pk, self.b.pk, self.alice, '80.00') for _ in range(8)]
        results, errors = run_in_threads(jobs)
        self.assertEqual(len(results), 1)
        self.assertEqual(len(errors), 7)
        self.a.refresh_from_db()
        self.b.refresh_from_db()
        self.assertEqual((self.a.balance, self.b.balance), (Decimal('20.00'), Decimal('80.00')))
        self.assertEqual(Transaction.objects.count(), 1)

    def test_opposite_transfers_do_not_deadlock_and_conserve_money(self):
        to_bob = lambda: services.transfer(self.a.pk, self.b.pk, self.alice, '1.00')
        to_alice = lambda: services.transfer(self.b.pk, self.a.pk, self.bob, '1.00')
        self.b.balance = Decimal('100.00')
        self.b.save()
        jobs = [to_bob, to_alice] * 10
        results, errors = run_in_threads(jobs)
        self.assertEqual(len(results) + len(errors), 20)
        total = sum(Account.objects.values_list('balance', flat=True))
        self.assertEqual(total, Decimal('200.00'))
        self.assertEqual(Transaction.objects.count(), len(results))
