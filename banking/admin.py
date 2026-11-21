from django.contrib import admin

from .models import Account, Card, Transaction


class ReadOnlyAdmin(admin.ModelAdmin):
    """Money is only changed through banking.services, never by editing rows in the admin."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Account)
class AccountAdmin(ReadOnlyAdmin):
    list_display = ('number', 'owner', 'account_type', 'balance', 'currency', 'is_active')
    list_filter = ('account_type', 'currency', 'is_active')
    search_fields = ('number', 'owner__username', 'owner__first_name', 'owner__last_name')


@admin.register(Transaction)
class TransactionAdmin(ReadOnlyAdmin):
    list_display = ('id', 'kind', 'from_account', 'to_account', 'amount', 'converted_amount', 'date')
    list_filter = ('kind', 'date')
    search_fields = ('from_account__number', 'to_account__number', 'description')


@admin.register(Card)
class CardAdmin(ReadOnlyAdmin):
    list_display = ('number', 'card_type', 'account', 'owner_name', 'expiry_date', 'is_active')
    list_filter = ('card_type', 'is_active')
    search_fields = ('number', 'account__number', 'owner_name')
