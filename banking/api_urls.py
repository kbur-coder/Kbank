from django.urls import path

from .api_views import (
    AccountCloseAPIView, AccountDepositAPIView, AccountDetailAPIView, AccountListCreateAPIView,
    CardIssueAPIView, CardListAPIView, TransactionListAPIView, TransferAPIView,
)

urlpatterns = [
    path('accounts/', AccountListCreateAPIView.as_view(), name='api-accounts'),
    path('accounts/<int:pk>/', AccountDetailAPIView.as_view(), name='api-account'),
    path('accounts/<int:pk>/close/', AccountCloseAPIView.as_view(), name='api-account-close'),
    path('accounts/<int:pk>/deposit/', AccountDepositAPIView.as_view(), name='api-account-deposit'),
    path('transactions/', TransactionListAPIView.as_view(), name='api-transactions'),
    path('transfer/', TransferAPIView.as_view(), name='api-transfer'),
    path('cards/', CardListAPIView.as_view(), name='api-cards'),
    path('cards/issue/', CardIssueAPIView.as_view(), name='api-card-issue'),
]
