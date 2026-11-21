from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from orders.models import ColocationRequest, DedicatedOrder, Invoice, MitigationRequest, Service, VPSOrder

from .forms import LoginForm, ProfileForm, SignupForm, TicketForm, TicketReplyForm, UserForm
from .models import CustomerProfile, Ticket, TicketMessage


def profile_of(user):
    profile, _ = CustomerProfile.objects.get_or_create(user=user)
    return profile


def _next_url(request, default='customers:dashboard'):
    nxt = request.POST.get('next') or request.GET.get('next')
    if nxt and url_has_allowed_host_and_scheme(nxt, {request.get_host()}, request.is_secure()):
        return nxt
    return default


class LoginView(auth_views.LoginView):
    template_name = 'customers/login.html'
    authentication_form = LoginForm
    redirect_authenticated_user = True


class LogoutView(auth_views.LogoutView):
    pass


def signup(request):
    if request.user.is_authenticated:
        return redirect(_next_url(request))
    form = SignupForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        messages.success(request, f'Welcome, {user.first_name}! Your account has been created.')
        return redirect(_next_url(request))
    return render(request, 'customers/signup.html', {'form': form, 'next': request.GET.get('next', '')})


@login_required
def dashboard(request):
    u = request.user
    return render(
        request,
        'customers/dashboard.html',
        {
            'profile': profile_of(u),
            'service_count': u.services.exclude(status=Service.Status.CANCELLED).count(),
            'open_invoice_count': u.invoices.filter(status=Invoice.Status.OPEN).count(),
            'open_ticket_count': u.tickets.exclude(status__in=['resolved', 'closed']).count(),
            'vps_orders': VPSOrder.objects.filter(customer=u).select_related('operating_system')[:10],
            'dedicated_orders': DedicatedOrder.objects.filter(customer=u).select_related('operating_system')[:10],
            'colocation_requests': ColocationRequest.objects.filter(customer=u).prefetch_related('items')[:10],
            'mitigation_requests': MitigationRequest.objects.filter(customer=u)[:10],
        },
    )


@login_required
def services(request):
    return render(request, 'customers/services.html', {'services': request.user.services.all()})


@login_required
def invoices(request):
    status_filter = request.GET.get('filter', 'all')
    qs = request.user.invoices.all()
    if status_filter == 'open':
        qs = qs.filter(status=Invoice.Status.OPEN)
    elif status_filter == 'paid':
        qs = qs.filter(status=Invoice.Status.PAID)
    return render(request, 'customers/invoices.html', {'invoices': qs, 'filter': status_filter})


@login_required
def invoice_detail(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk, customer=request.user)
    return render(request, 'customers/invoice_detail.html', {'invoice': invoice})


@login_required
def credit(request):
    profile = profile_of(request.user)
    if request.method == 'POST':
        try:
            amount = Decimal(request.POST.get('amount', '0').replace(',', ''))
        except InvalidOperation:
            amount = Decimal(0)
        if not Decimal('10') <= amount <= Decimal('50000'):
            messages.error(request, 'Enter an amount between R$ 10.00 and R$ 50,000.00.')
        else:
            invoice = Invoice.objects.create(
                customer=request.user,
                kind=Invoice.Kind.CREDIT,
                amount=amount.quantize(Decimal('0.01')),
                description='Account credit top-up',
                due_date=timezone.localdate() + timedelta(days=3),
            )
            messages.success(request, f'Invoice {invoice.number} created. The amount becomes credit once paid.')
            return redirect('customers:invoice', invoice.pk)
    return render(
        request,
        'customers/credit.html',
        {'profile': profile, 'transactions': request.user.credit_transactions.all()},
    )


@login_required
def tickets(request):
    return render(request, 'customers/tickets.html', {'tickets': request.user.tickets.select_related('category')})


@login_required
def ticket_new(request):
    form = TicketForm(
        request.POST or None,
        user=request.user,
        initial={'category': request.GET.get('category'), 'subject': request.GET.get('subject', '')},
    )
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            ticket = form.save(commit=False)
            ticket.customer = request.user
            ticket.save()
            TicketMessage.objects.create(ticket=ticket, author=request.user, body=form.cleaned_data['message'])
        messages.success(request, f'Ticket {ticket.code} opened. We will reply right here.')
        return redirect('customers:ticket', ticket.pk)
    return render(request, 'customers/ticket_new.html', {'form': form})


@login_required
def ticket_detail(request, pk):
    ticket = get_object_or_404(Ticket.objects.select_related('category', 'service'), pk=pk, customer=request.user)
    form = TicketReplyForm(request.POST or None)
    if request.method == 'POST':
        if request.POST.get('action') == 'close':
            ticket.status = Ticket.Status.CLOSED
            ticket.save(update_fields=['status', 'updated_at'])
            messages.success(request, 'Ticket closed.')
            return redirect('customers:ticket', ticket.pk)
        if form.is_valid():
            TicketMessage.objects.create(ticket=ticket, author=request.user, body=form.cleaned_data['body'])
            ticket.status = Ticket.Status.OPEN  # back to the staff queue
            ticket.save(update_fields=['status', 'updated_at'])
            return redirect('customers:ticket', ticket.pk)
    return render(
        request,
        'customers/ticket_detail.html',
        {'ticket': ticket, 'messages_list': ticket.messages.select_related('author'), 'form': form},
    )


@login_required
def profile(request):
    profile = profile_of(request.user)
    user_form = UserForm(request.POST or None, instance=request.user, prefix='u')
    profile_form = ProfileForm(request.POST or None, instance=profile, prefix='p')
    if request.method == 'POST' and user_form.is_valid() and profile_form.is_valid():
        user_form.save()
        profile_form.save()
        messages.success(request, 'Your details have been updated.')
        return redirect(_next_url(request, 'customers:profile'))
    return render(
        request,
        'customers/profile.html',
        {'user_form': user_form, 'profile_form': profile_form, 'next': request.GET.get('next', '')},
    )


class PasswordChangeView(auth_views.PasswordChangeView):
    template_name = 'customers/password.html'
    success_url = reverse_lazy('customers:dashboard')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        for field in form.fields.values():
            field.widget.attrs['class'] = 'form-input'
        return form

    def form_valid(self, form):
        messages.success(self.request, 'Password changed.')
        return super().form_valid(form)
