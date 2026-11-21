from django.urls import path

from .views import (
    AccountCloseView, AccountCreateView, AccountDetailView, AccountListView,
    CardCreateView, CardListView, DepositView, TransactionListView, TransferView,
)

urlpatterns = [
    path('accounts/', AccountListView.as_view(), name='account-list'),
    path('accounts/<int:pk>/', AccountDetailView.as_view(), name='account-detail'),
    path('accounts/open/', AccountCreateView.as_view(), name='account-create'),
    path('accounts/<int:pk>/close/', AccountCloseView.as_view(), name='account-delete'),
    path('accounts/<int:pk>/deposit/', DepositView.as_view(), name='account-deposit'),
    path('transactions/', TransactionListView.as_view(), name='transaction-list'),
    path('transfer/', TransferView.as_view(), name='transfer'),
    path('cards/', CardListView.as_view(), name='card-list'),
    path('cards/new/', CardCreateView.as_view(), name='card-create'),
]
