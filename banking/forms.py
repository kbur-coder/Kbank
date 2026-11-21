from django import forms

from . import money
from .models import Account, Card


class AccountForm(forms.Form):
    account_type = forms.ChoiceField(choices=Account.ACCOUNT_TYPES)
    currency = forms.ChoiceField(choices=Account.CURRENCIES)


class TransferForm(forms.Form):
    from_account = forms.ModelChoiceField(queryset=Account.objects.none(), label='Со счета')
    to_number = forms.CharField(max_length=30, label='Номер счета получателя')
    amount = forms.DecimalField(min_value=money.CENT, max_digits=15, decimal_places=2, label='Сумма')
    description = forms.CharField(required=False, max_length=255, widget=forms.Textarea(attrs={'rows': 2}))

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user')
        super().__init__(*args, **kwargs)
        self.fields['from_account'].queryset = Account.objects.filter(owner=user, is_active=True)
        for name in ('from_account', 'to_number', 'amount', 'description'):
            self.fields[name].widget.attrs.setdefault('class', 'form-control')
        self.fields['from_account'].widget.attrs['class'] = 'form-select'

    def clean(self):
        cleaned = super().clean()
        number = cleaned.get('to_number')
        if number:
            if not money.is_account_number(number):
                self.add_error('to_number', 'Некорректный номер счета.')
            else:
                target = Account.objects.filter(number=money.normalize_account_number(number)).first()
                if target is None:
                    self.add_error('to_number', 'Счет с таким номером не найден.')
                else:
                    cleaned['to_account'] = target
                    if cleaned.get('from_account') == target:
                        self.add_error('to_number', 'Нельзя переводить деньги на тот же счет.')
        return cleaned


class DepositForm(forms.Form):
    amount = forms.DecimalField(
        min_value=money.CENT, max_digits=15, decimal_places=2, label='Сумма',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
    )


class CardForm(forms.Form):
    account = forms.ModelChoiceField(queryset=Account.objects.none(), label='Счет')
    card_type = forms.ChoiceField(choices=Card.CARD_TYPES, label='Тип карты')

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user')
        super().__init__(*args, **kwargs)
        self.fields['account'].queryset = Account.objects.filter(owner=user, is_active=True)
        self.fields['account'].widget.attrs['class'] = 'form-select'
        self.fields['card_type'].widget.attrs['class'] = 'form-select'
