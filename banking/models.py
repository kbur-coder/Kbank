from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q

from .money import validate_account_number, validate_card_number


class Account(models.Model):
    ACCOUNT_TYPES = (
        ('checking', 'Checking'),
        ('savings', 'Savings'),
        ('credit', 'Credit'),
        ('deposit', 'Deposit'),
    )

    CURRENCIES = (
        ('USD', 'US Dollar'),
        ('EUR', 'Euro'),
        ('SUM', 'Uzbek Sum'),
    )

    number = models.CharField(max_length=20, unique=True, validators=[validate_account_number])
    account_type = models.CharField(max_length=10, choices=ACCOUNT_TYPES)
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    currency = models.CharField(max_length=3, choices=CURRENCIES)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='accounts')
    opened_date = models.DateTimeField(auto_now_add=True)
    # Accounts are closed, never deleted: the ledger must keep pointing at them.
    is_active = models.BooleanField(default=True)
    closed_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(balance__gte=0), name='account_balance_not_negative'),
        ]

    def __str__(self):
        return f"{self.number} ({self.get_account_type_display()})"


class Transaction(models.Model):
    TRANSFER = 'transfer'
    DEPOSIT = 'deposit'
    KINDS = (
        (TRANSFER, 'Transfer'),
        (DEPOSIT, 'Deposit'),
    )

    kind = models.CharField(max_length=10, choices=KINDS, default=TRANSFER)
    # A deposit comes from outside the bank, so it has no source account.
    from_account = models.ForeignKey(
        Account, on_delete=models.PROTECT, related_name='outgoing_transactions', null=True, blank=True
    )
    to_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='incoming_transactions')
    # amount is in the source currency; converted_amount is what the receiver got.
    amount = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(0.01)])
    converted_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name='transaction_amount_positive'),
            models.CheckConstraint(
                condition=Q(kind='deposit') | Q(from_account__isnull=False),
                name='transfer_needs_source_account',
            ),
            models.CheckConstraint(
                condition=Q(from_account__isnull=True) | ~Q(from_account=F('to_account')),
                name='transfer_to_a_different_account',
            ),
        ]

    def __str__(self):
        return f"Transaction #{self.id}"

    @property
    def received_amount(self):
        return self.converted_amount if self.converted_amount is not None else self.amount


class Card(models.Model):
    CARD_TYPES = (
        ('debit', 'Debit'),
        ('credit', 'Credit'),
    )

    number = models.CharField(max_length=16, unique=True, validators=[validate_card_number])
    card_type = models.CharField(max_length=6, choices=CARD_TYPES)
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='cards')
    owner_name = models.CharField(max_length=100)
    expiry_date = models.DateField()
    issued_date = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Card {self.number}"
