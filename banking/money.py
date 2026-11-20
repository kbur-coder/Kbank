"""Money helpers: exact decimal arithmetic, fixed exchange rates, Luhn numbers.

Nothing here touches the database, so everything is easy to test.
"""
import secrets
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.core.exceptions import ValidationError

CENT = Decimal("0.01")

# How many US dollars one unit of the currency is worth. The rates are fixed on
# purpose: a transfer must be reproducible, and the demo has no market data.
USD_PER_UNIT = {
    "USD": Decimal("1"),
    "EUR": Decimal("1.08"),
    "SUM": Decimal("0.0000787"),
}

ACCOUNT_PREFIX = "KB"
ACCOUNT_DIGITS = 13  # 12 random digits + 1 Luhn check digit
CARD_PREFIX = "4"
CARD_DIGITS = 16


def to_money(value):
    """Convert user input to a Decimal with exactly two decimal places."""
    if isinstance(value, float):
        raise TypeError("floats are not allowed for money, use str or Decimal")
    try:
        number = Decimal(str(value).strip().replace(",", "."))
    except (InvalidOperation, ValueError):
        raise ValueError(f"not a valid amount: {value!r}") from None
    if not number.is_finite():
        raise ValueError(f"not a valid amount: {value!r}")
    return number.quantize(CENT, rounding=ROUND_HALF_UP)


def convert(amount, from_currency, to_currency):
    """Convert an amount between currencies through USD, rounded to cents."""
    amount = to_money(amount)
    if from_currency == to_currency:
        return amount
    try:
        usd = amount * USD_PER_UNIT[from_currency]
        return (usd / USD_PER_UNIT[to_currency]).quantize(CENT, rounding=ROUND_HALF_UP)
    except KeyError as error:
        raise ValueError(f"unknown currency: {error.args[0]}") from None


def luhn_check_digit(payload):
    """Check digit that makes payload + digit pass the Luhn algorithm."""
    total = 0
    for position, char in enumerate(reversed(payload)):
        digit = int(char)
        if position % 2 == 0:  # these digits get doubled once the check digit is appended
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return str((10 - total % 10) % 10)


def luhn_valid(digits):
    return digits.isdigit() and len(digits) > 1 and luhn_check_digit(digits[:-1]) == digits[-1]


def _random_digits(count):
    return "".join(str(secrets.randbelow(10)) for _ in range(count))


def generate_account_number():
    payload = _random_digits(ACCOUNT_DIGITS - 1)
    return f"{ACCOUNT_PREFIX}{payload}{luhn_check_digit(payload)}"


def generate_card_number():
    payload = CARD_PREFIX + _random_digits(CARD_DIGITS - len(CARD_PREFIX) - 1)
    return payload + luhn_check_digit(payload)


def generate_cvv():
    return _random_digits(3)


def normalize_account_number(text):
    return "".join(str(text).split()).upper()


def is_account_number(text):
    text = normalize_account_number(text)
    digits = text[len(ACCOUNT_PREFIX):]
    return (
        text.startswith(ACCOUNT_PREFIX)
        and len(digits) == ACCOUNT_DIGITS
        and luhn_valid(digits)
    )


def validate_account_number(value):
    if not is_account_number(value):
        raise ValidationError("Некорректный номер счета.", code="invalid_account_number")


def validate_card_number(value):
    if len(value) != CARD_DIGITS or not luhn_valid(value):
        raise ValidationError("Некорректный номер карты.", code="invalid_card_number")
