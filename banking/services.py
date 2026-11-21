"""All operations that change money live here.

Views, the REST API and management commands call these functions and never
touch balances directly. Every function is atomic and locks the rows it changes,
so two simultaneous requests cannot spend the same money twice.
"""
from datetime import date

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from . import money
from .models import Account, Card, Transaction


class BankError(Exception):
    """Base class for rule violations. The message is safe to show to the user."""


class InvalidAmount(BankError):
    pass


class InsufficientFunds(BankError):
    pass


class AccountClosed(BankError):
    pass


class NotYourAccount(BankError):
    pass


class SameAccount(BankError):
    pass


class DemoModeOff(BankError):
    pass


def _clean_amount(value):
    try:
        amount = money.to_money(value)
    except (TypeError, ValueError):
        raise InvalidAmount("Введите корректную сумму.") from None
    if amount <= 0:
        raise InvalidAmount("Сумма должна быть больше нуля.")
    if amount >= 10 ** 13:
        raise InvalidAmount("Слишком большая сумма.")
    return amount


def _lock_accounts(*pks):
    """Lock accounts in primary-key order so two opposite transfers never deadlock."""
    ordered = sorted(set(pks))
    locked = {a.pk: a for a in Account.objects.select_for_update().filter(pk__in=ordered).order_by('pk')}
    return locked


def open_account(user, account_type, currency):
    for _ in range(5):
        try:
            with transaction.atomic():
                return Account.objects.create(
                    owner=user,
                    account_type=account_type,
                    currency=currency,
                    number=money.generate_account_number(),
                )
        except IntegrityError:  # the random number was already taken, try another
            continue
    raise BankError("Не удалось создать номер счета, попробуйте еще раз.")


def close_account(account_id, user):
    with transaction.atomic():
        account = Account.objects.select_for_update().filter(pk=account_id, owner=user).first()
        if account is None:
            raise NotYourAccount("Счет не найден.")
        if not account.is_active:
            raise AccountClosed("Счет уже закрыт.")
        if account.balance != 0:
            raise BankError("Нельзя закрыть счет с ненулевым балансом.")
        account.is_active = False
        account.closed_date = timezone.now()
        account.save(update_fields=['is_active', 'closed_date'])
        Card.objects.filter(account=account).update(is_active=False)
        return account


def deposit(account_id, user, amount, description=''):
    """Top up an account. Only available in DEMO_MODE: a real bank has no such button."""
    if not settings.DEMO_MODE:
        raise DemoModeOff("Пополнение доступно только в демо-режиме.")
    amount = _clean_amount(amount)
    with transaction.atomic():
        accounts = _lock_accounts(account_id)
        account = accounts.get(account_id)
        if account is None or account.owner_id != user.pk:
            raise NotYourAccount("Счет не найден.")
        if not account.is_active:
            raise AccountClosed("Счет закрыт.")
        account.balance += amount
        account.save(update_fields=['balance'])
        return Transaction.objects.create(
            kind=Transaction.DEPOSIT,
            to_account=account,
            amount=amount,
            converted_amount=amount,
            description=description or 'Демо-пополнение',
        )


def transfer(from_account_id, to_account_id, user, amount, description=''):
    """Move money between two accounts, converting the currency if needed."""
    amount = _clean_amount(amount)
    if from_account_id == to_account_id:
        raise SameAccount("Нельзя переводить деньги на тот же счет.")
    with transaction.atomic():
        accounts = _lock_accounts(from_account_id, to_account_id)
        source = accounts.get(from_account_id)
        target = accounts.get(to_account_id)
        if source is None or source.owner_id != user.pk:
            raise NotYourAccount("Счет списания не найден.")
        if target is None:
            raise NotYourAccount("Счет получателя не найден.")
        if not source.is_active or not target.is_active:
            raise AccountClosed("Один из счетов закрыт.")
        if source.balance < amount:
            raise InsufficientFunds("Недостаточно средств на счете.")
        received = money.convert(amount, source.currency, target.currency)
        if received <= 0:
            raise InvalidAmount("Сумма слишком мала для перевода в эту валюту.")
        source.balance -= amount
        target.balance += received
        source.save(update_fields=['balance'])
        target.save(update_fields=['balance'])
        return Transaction.objects.create(
            kind=Transaction.TRANSFER,
            from_account=source,
            to_account=target,
            amount=amount,
            converted_amount=received,
            description=description,
        )


def find_account_by_number(text):
    number = money.normalize_account_number(text)
    return Account.objects.filter(number=number).first()


def issue_card(account_id, user, card_type):
    """Create a card. The CVV is returned once and is not stored anywhere."""
    with transaction.atomic():
        account = Account.objects.select_for_update().filter(pk=account_id, owner=user).first()
        if account is None:
            raise NotYourAccount("Счет не найден.")
        if not account.is_active:
            raise AccountClosed("Счет закрыт.")
        today = date.today()
        expiry = today.replace(year=today.year + 4, day=1)
        for _ in range(5):
            try:
                with transaction.atomic():
                    card = Card.objects.create(
                        account=account,
                        card_type=card_type,
                        number=money.generate_card_number(),
                        owner_name=(user.get_full_name() or user.username).upper(),
                        expiry_date=expiry,
                    )
                break
            except IntegrityError:
                continue
        else:
            raise BankError("Не удалось выпустить карту, попробуйте еще раз.")
        return card, money.generate_cvv()
