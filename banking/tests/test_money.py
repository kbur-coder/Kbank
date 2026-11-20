from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from banking import money


class ToMoneyTests(SimpleTestCase):
    def test_rounds_to_cents_half_up(self):
        self.assertEqual(money.to_money('10.005'), Decimal('10.01'))
        self.assertEqual(money.to_money('10.004'), Decimal('10.00'))

    def test_accepts_decimal_comma(self):
        self.assertEqual(money.to_money('25,50'), Decimal('25.50'))

    def test_rejects_float(self):
        with self.assertRaises(TypeError):
            money.to_money(0.1)

    def test_rejects_garbage(self):
        for bad in ('abc', '', 'NaN', 'Infinity'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                money.to_money(bad)

    def test_no_binary_float_error(self):
        total = sum((money.to_money('0.10') for _ in range(3)), Decimal('0'))
        self.assertEqual(total, Decimal('0.30'))


class ConvertTests(SimpleTestCase):
    def test_same_currency_is_unchanged(self):
        self.assertEqual(money.convert('12.34', 'USD', 'USD'), Decimal('12.34'))

    def test_usd_to_eur(self):
        self.assertEqual(money.convert('108.00', 'EUR', 'USD'), Decimal('116.64'))
        self.assertEqual(money.convert('116.64', 'USD', 'EUR'), Decimal('108.00'))

    def test_usd_to_sum(self):
        self.assertEqual(money.convert('1', 'USD', 'SUM'), Decimal('12706.48'))

    def test_unknown_currency(self):
        with self.assertRaises(ValueError):
            money.convert('1', 'USD', 'GBP')


class LuhnTests(SimpleTestCase):
    def test_known_valid_numbers(self):
        self.assertTrue(money.luhn_valid('4539578763621486'))
        self.assertTrue(money.luhn_valid('79927398713'))

    def test_changed_digit_is_detected(self):
        self.assertFalse(money.luhn_valid('4539578763621487'))
        self.assertFalse(money.luhn_valid('79927398710'))

    def test_check_digit(self):
        self.assertEqual(money.luhn_check_digit('7992739871'), '3')

    def test_not_digits(self):
        self.assertFalse(money.luhn_valid('12ab'))
        self.assertFalse(money.luhn_valid(''))


class GeneratedNumberTests(SimpleTestCase):
    def test_account_numbers_are_valid(self):
        for _ in range(200):
            number = money.generate_account_number()
            self.assertEqual(len(number), 15)
            self.assertTrue(money.is_account_number(number), number)

    def test_card_numbers_are_valid(self):
        for _ in range(200):
            number = money.generate_card_number()
            self.assertEqual(len(number), 16)
            self.assertTrue(number.startswith('4'))
            self.assertTrue(money.luhn_valid(number), number)

    def test_cvv_has_three_digits(self):
        for _ in range(50):
            cvv = money.generate_cvv()
            self.assertTrue(cvv.isdigit() and len(cvv) == 3)

    def test_typo_in_account_number_is_caught(self):
        number = money.generate_account_number()
        last = int(number[-1])
        typo = number[:-1] + str((last + 1) % 10)
        self.assertFalse(money.is_account_number(typo))

    def test_spaces_and_case_are_ignored(self):
        number = money.generate_account_number()
        spaced = ' '.join([number[:2].lower(), number[2:6], number[6:]])
        self.assertTrue(money.is_account_number(spaced))
        self.assertEqual(money.normalize_account_number(spaced), number)

    def test_validators_raise(self):
        with self.assertRaises(ValidationError):
            money.validate_account_number('KB123')
        with self.assertRaises(ValidationError):
            money.validate_card_number('4111111111111112')
        money.validate_card_number('4111111111111111')
