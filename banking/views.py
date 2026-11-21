from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import FormView, ListView, TemplateView

from . import services
from .forms import AccountForm, CardForm, DepositForm, TransferForm
from .models import Account, Card, Transaction


class HomeView(LoginRequiredMixin, TemplateView):
    template_name = 'banking/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        accounts = Account.objects.filter(owner=self.request.user, is_active=True)
        context['accounts'] = accounts
        context['transactions'] = (
            Transaction.objects.filter(Q(from_account__owner=self.request.user) | Q(to_account__owner=self.request.user))
            .select_related('from_account__owner', 'to_account__owner')
            .order_by('-date', '-id')[:5]
        )
        return context


class AccountListView(LoginRequiredMixin, ListView):
    template_name = 'banking/account_list.html'
    context_object_name = 'accounts'

    def get_queryset(self):
        return Account.objects.filter(owner=self.request.user).order_by('-is_active', 'id')


class AccountDetailView(LoginRequiredMixin, TemplateView):
    template_name = 'banking/account_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        account = get_object_or_404(Account, pk=self.kwargs['pk'], owner=self.request.user)
        context['account'] = account
        context['demo_mode'] = settings.DEMO_MODE
        return context


class AccountCreateView(LoginRequiredMixin, FormView):
    form_class = AccountForm
    template_name = 'banking/account_create.html'
    success_url = reverse_lazy('account-list')

    def form_valid(self, form):
        services.open_account(self.request.user, form.cleaned_data['account_type'], form.cleaned_data['currency'])
        messages.success(self.request, "Счет открыт.")
        return super().form_valid(form)


class AccountCloseView(LoginRequiredMixin, TemplateView):
    template_name = 'banking/account_confirm_delete.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['account'] = get_object_or_404(
            Account, pk=self.kwargs['pk'], owner=self.request.user, is_active=True
        )
        return context

    def post(self, request, *args, **kwargs):
        try:
            services.close_account(self.kwargs['pk'], request.user)
        except services.BankError as error:
            messages.error(request, str(error))
            return redirect('account-detail', pk=self.kwargs['pk'])
        messages.success(request, "Счет закрыт.")
        return redirect('account-list')


class TransactionListView(LoginRequiredMixin, ListView):
    template_name = 'banking/transaction_list.html'
    context_object_name = 'transactions'
    paginate_by = 10

    def get_queryset(self):
        mine = Account.objects.filter(owner=self.request.user)
        queryset = Transaction.objects.filter(Q(from_account__in=mine) | Q(to_account__in=mine))
        account = self.request.GET.get('account')
        if account and account.isdigit():
            queryset = queryset.filter(Q(from_account_id=account) | Q(to_account_id=account))
        return queryset.select_related('from_account__owner', 'to_account__owner').order_by('-date', '-id')


class TransferView(LoginRequiredMixin, FormView):
    form_class = TransferForm
    template_name = 'banking/transfer.html'
    success_url = reverse_lazy('transaction-list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        source = self.request.GET.get('from_account')
        if source and source.isdigit():
            initial['from_account'] = source
        return initial

    def form_valid(self, form):
        try:
            services.transfer(
                form.cleaned_data['from_account'].pk,
                form.cleaned_data['to_account'].pk,
                self.request.user,
                form.cleaned_data['amount'],
                form.cleaned_data['description'],
            )
        except services.BankError as error:
            form.add_error(None, str(error))
            return self.form_invalid(form)
        messages.success(self.request, "Перевод выполнен.")
        return super().form_valid(form)


class DepositView(LoginRequiredMixin, FormView):
    form_class = DepositForm
    template_name = 'banking/deposit.html'

    def dispatch(self, request, *args, **kwargs):
        if not settings.DEMO_MODE:
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['account'] = get_object_or_404(
            Account, pk=self.kwargs['pk'], owner=self.request.user, is_active=True
        )
        return context

    def get_success_url(self):
        return reverse('account-detail', kwargs={'pk': self.kwargs['pk']})

    def form_valid(self, form):
        try:
            services.deposit(self.kwargs['pk'], self.request.user, form.cleaned_data['amount'])
        except services.BankError as error:
            form.add_error(None, str(error))
            return self.form_invalid(form)
        messages.success(self.request, "Счет пополнен (демо).")
        return super().form_valid(form)


class CardListView(LoginRequiredMixin, ListView):
    template_name = 'banking/card_list.html'
    context_object_name = 'cards'

    def get_queryset(self):
        return Card.objects.filter(account__owner=self.request.user).select_related('account').order_by('-id')


class CardCreateView(LoginRequiredMixin, FormView):
    form_class = CardForm
    template_name = 'banking/card_create.html'
    success_url = reverse_lazy('card-list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        try:
            card, cvv = services.issue_card(
                form.cleaned_data['account'].pk, self.request.user, form.cleaned_data['card_type']
            )
        except services.BankError as error:
            form.add_error(None, str(error))
            return self.form_invalid(form)
        # The CVV is not stored, so this message is the only time it can be seen.
        messages.success(
            self.request,
            f"Карта выпущена. CVV: {cvv}. Запомните его: повторно он не показывается.",
        )
        return super().form_valid(form)
