from django.db.models import Q
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from . import money, services
from .models import Account, Card, Transaction
from .serializers import (
    AccountSerializer, CardIssueSerializer, CardSerializer, DepositSerializer,
    TransactionSerializer, TransferSerializer,
)


def bank_error_response(error):
    code = status.HTTP_404_NOT_FOUND if isinstance(error, services.NotYourAccount) else status.HTTP_400_BAD_REQUEST
    return Response({'detail': str(error)}, status=code)


class AccountListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = AccountSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Account.objects.none()
        return Account.objects.filter(owner=self.request.user).order_by('id')

    def perform_create(self, serializer):
        serializer.instance = services.open_account(
            self.request.user, serializer.validated_data['account_type'], serializer.validated_data['currency']
        )


class AccountDetailAPIView(generics.RetrieveAPIView):
    serializer_class = AccountSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Account.objects.none()
        return Account.objects.filter(owner=self.request.user)


class AccountCloseAPIView(APIView):
    def post(self, request, pk):
        try:
            account = services.close_account(pk, request.user)
        except services.BankError as error:
            return bank_error_response(error)
        return Response(AccountSerializer(account).data)


class AccountDepositAPIView(APIView):
    def post(self, request, pk):
        serializer = DepositSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            tx = services.deposit(pk, request.user, serializer.validated_data['amount'])
        except services.BankError as error:
            return bank_error_response(error)
        return Response(TransactionSerializer(tx).data, status=status.HTTP_201_CREATED)


class TransactionListAPIView(generics.ListAPIView):
    serializer_class = TransactionSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Transaction.objects.none()
        mine = Account.objects.filter(owner=self.request.user)
        return (
            Transaction.objects.filter(Q(from_account__in=mine) | Q(to_account__in=mine))
            .select_related('from_account', 'to_account')
            .order_by('-date', '-id')
        )


class TransferAPIView(APIView):
    def post(self, request):
        serializer = TransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if not money.is_account_number(data['to_number']):
            raise ValidationError({'to_number': 'Некорректный номер счета.'})
        target = services.find_account_by_number(data['to_number'])
        if target is None:
            raise ValidationError({'to_number': 'Счет с таким номером не найден.'})
        try:
            tx = services.transfer(
                data['from_account_id'], target.pk, request.user, data['amount'], data['description']
            )
        except services.BankError as error:
            return bank_error_response(error)
        return Response(TransactionSerializer(tx).data, status=status.HTTP_201_CREATED)


class CardListAPIView(generics.ListAPIView):
    serializer_class = CardSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Card.objects.none()
        return Card.objects.filter(account__owner=self.request.user).order_by('id')


class CardIssueAPIView(APIView):
    def post(self, request):
        serializer = CardIssueSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            card, cvv = services.issue_card(
                serializer.validated_data['account_id'], request.user, serializer.validated_data['card_type']
            )
        except services.BankError as error:
            return bank_error_response(error)
        data = CardSerializer(card).data
        data['number'] = card.number  # the full number is shown once, together with the CVV
        data['cvv'] = cvv
        return Response(data, status=status.HTTP_201_CREATED)
