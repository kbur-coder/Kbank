from rest_framework import serializers

from .models import Account, Card, Transaction


class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = ['id', 'number', 'account_type', 'balance', 'currency', 'opened_date', 'is_active']
        read_only_fields = ['id', 'number', 'balance', 'opened_date', 'is_active']


class TransactionSerializer(serializers.ModelSerializer):
    from_number = serializers.CharField(source='from_account.number', default=None, read_only=True)
    to_number = serializers.CharField(source='to_account.number', read_only=True)

    class Meta:
        model = Transaction
        fields = ['id', 'kind', 'from_number', 'to_number', 'amount', 'converted_amount', 'date', 'description']
        read_only_fields = fields


class CardSerializer(serializers.ModelSerializer):
    number = serializers.SerializerMethodField()

    class Meta:
        model = Card
        fields = ['id', 'number', 'card_type', 'account', 'owner_name', 'expiry_date', 'is_active']
        read_only_fields = fields

    def get_number(self, card):
        return '**** **** **** ' + card.number[-4:]


class TransferSerializer(serializers.Serializer):
    from_account_id = serializers.IntegerField()
    to_number = serializers.CharField(max_length=30)
    amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    description = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')


class DepositSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=15, decimal_places=2)


class CardIssueSerializer(serializers.Serializer):
    account_id = serializers.IntegerField()
    card_type = serializers.ChoiceField(choices=Card.CARD_TYPES)
