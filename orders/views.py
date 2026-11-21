from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from catalog.models import ColocationSettings, Coupon, DedicatedServer, OperatingSystem, VPSSettings
from customers.views import profile_of

from .forms import (
    CheckoutForm,
    ColocationForm,
    DedicatedOrderForm,
    MitigationForm,
    VPSConfigForm,
    read_colocation_items,
)
from .models import ColocationItem, ColocationRequest, DedicatedOrder, Invoice, VPSOrder

SESSION_VPS = 'vps_config'
SESSION_COLOCATION = 'colocation_items'


def _banner_coupon_code():
    coupon = Coupon.objects.current().filter(show_in_banner=True).first()
    return coupon.code if coupon else ''


# ----------------------------------------------------------------------------- VPS


@require_POST
def vps_checkout(request):
    """Receive the /vps builder, keep it in the session and move on to the review page."""
    form = VPSConfigForm(request.POST)
    if not VPSSettings.current().sales_enabled:
        messages.error(request, 'We are not accepting new VPS orders at the moment.')
        return redirect('home:vps')
    if not form.is_valid():
        for errors in form.errors.values():
            for e in errors:
                messages.error(request, e)
        return redirect('home:vps')
    d = form.cleaned_data
    request.session[SESSION_VPS] = {'cpu': d['cpu'], 'ram': d['ram'], 'disk': d['disk'], 'os': d['os'].pk}
    return redirect('orders:vps_review')


@login_required
def vps_review(request):
    config = request.session.get(SESSION_VPS)
    if not config:
        return redirect('home:vps')
    settings = VPSSettings.current()
    operating_system = get_object_or_404(OperatingSystem, pk=config['os'])
    try:
        settings.validate(config['cpu'], config['ram'], config['disk'])
    except ValidationError as e:
        for msg in e.messages:
            messages.error(request, msg)
        return redirect('home:vps')
    price = settings.calculate(config['cpu'], config['ram'], config['disk'], operating_system)

    form = CheckoutForm(request.POST or None, product='vps', initial={'coupon': _banner_coupon_code()})
    order = VPSOrder(
        customer=request.user,
        vcpu=config['cpu'],
        ram_gb=config['ram'],
        disk_gb=config['disk'],
        operating_system=operating_system,
        monthly_price=price,
    )
    if request.method == 'POST' and form.is_valid():
        order.apply_coupon(form.cleaned_data['coupon'], 'vps')
        if request.POST.get('action') == 'confirm':
            d = form.cleaned_data
            order.customer_notes = d['notes']
            order.hostname, order.ssh_key = d['hostname'], d['ssh_key']
            with transaction.atomic():
                order.save()
                invoice = Invoice.for_order(order)
            del request.session[SESSION_VPS]
            messages.success(request, f'Order {order.code} placed! Invoice {invoice.number} has been issued.')
            return redirect('orders:vps_detail', order.pk)
    elif request.method == 'GET' and form.initial.get('coupon'):
        order.apply_coupon(Coupon.objects.filter(code=form.initial['coupon']).first(), 'vps')

    context = {'order': order, 'form': form, 'profile': profile_of(request.user)}
    return render(request, 'orders/vps_review.html', context)


@login_required
def vps_detail(request, pk):
    order = get_object_or_404(VPSOrder, pk=pk, customer=request.user)
    return render(request, 'orders/order_detail.html', {'order': order, 'kind': 'VPS'})


# -------------------------------------------------------------- Dedicated servers


def dedicated_configure(request, slug):
    server = get_object_or_404(DedicatedServer.objects.published(), slug=slug)
    form = DedicatedOrderForm(request.POST or None, server=server)

    if request.method == 'POST':
        if not request.user.is_authenticated:
            return redirect(f'{reverse("customers:login")}?{urlencode({"next": request.path})}')
        if not server.available:
            messages.error(request, 'This server is not available at the moment.')
            return redirect('orders:dedicated_configure', server.slug)
        if form.is_valid():
            d = form.cleaned_data
            extras = form.options_price()
            with transaction.atomic():
                order = DedicatedOrder(
                    customer=request.user,
                    server=server,
                    server_name=server.name,
                    specs=server.specs_summary(),
                    monthly_price=server.monthly_price + extras,
                    options_price=extras,
                    options_summary=form.summary(),
                    setup_fee=server.setup_fee,
                    operating_system=d['operating_system'],
                    custom_os=d.get('custom_os', ''),
                    panel_license=d.get('panel_license', ''),
                    bandwidth=d.get('bandwidth'),
                    partitioning=d.get('partitioning'),
                    ip_block=d.get('ip_block'),
                    hostname=d['hostname'],
                    ssh_key=d['ssh_key'],
                    customer_notes=d['notes'],
                )
                order.apply_coupon(d['coupon'], 'dedicated')
                order.save()
                invoice = Invoice.for_order(order)
            messages.success(request, f'Order {order.code} placed! Invoice {invoice.number} has been issued.')
            return redirect('orders:dedicated_detail', order.pk)

    return render(request, 'orders/dedicated_configure.html', {'server': server, 'form': form})


@login_required
def dedicated_detail(request, pk):
    order = get_object_or_404(DedicatedOrder, pk=pk, customer=request.user)
    return render(request, 'orders/order_detail.html', {'order': order, 'kind': 'Dedicated server'})


# --------------------------------------------------------------------- Colocation


@require_POST
def colocation_start(request):
    """Receive the public estimate, keep it and send the visitor to sign up / log in / review."""
    items, _ = read_colocation_items(request.POST)
    request.session[SESSION_COLOCATION] = items
    target = reverse('orders:colocation_new')
    if request.user.is_authenticated:
        return redirect(target)
    route = 'customers:signup' if request.POST.get('destination') == 'signup' else 'customers:login'
    return redirect(f'{reverse(route)}?{urlencode({"next": target})}')


@login_required
def colocation_new(request):
    settings = ColocationSettings.current()
    profile = profile_of(request.user)
    if not profile.verified:
        # Same as the original site: only verified accounts can request colocation.
        return render(request, 'orders/colocation_verification.html', {'profile': profile})
    form = ColocationForm(request.POST or None)
    items = request.session.get(SESSION_COLOCATION) or [{'model': '', 'size_u': 1, 'watts': settings.default_watts}]
    errors = []
    if request.method == 'POST':
        items, errors = read_colocation_items(request.POST)
        if form.is_valid() and not errors:
            with transaction.atomic():
                req = ColocationRequest.objects.create(
                    customer=request.user,
                    estimated_price=settings.calculate((i['size_u'], i['watts']) for i in items),
                    desired_move_in_date=form.cleaned_data['desired_move_in_date'],
                    customer_notes=form.cleaned_data['notes'],
                )
                ColocationItem.objects.bulk_create(ColocationItem(request=req, **i) for i in items)
            request.session.pop(SESSION_COLOCATION, None)
            messages.success(request, f'Request {req.code} sent! Our team will get in touch.')
            return redirect('orders:colocation_detail', req.pk)
    return render(
        request,
        'orders/colocation_form.html',
        {
            'settings': settings,
            'form': form,
            'items': items,
            'errors': errors,
            'sizes': range(1, settings.max_unit_size + 1),
        },
    )


@login_required
def colocation_detail(request, pk):
    req = get_object_or_404(ColocationRequest.objects.prefetch_related('items'), pk=pk, customer=request.user)
    return render(request, 'orders/colocation_detail.html', {'req': req})


# --------------------------------------------------------------------- Mitigation


def mitigation_quote(request):
    initial = {'bandwidth': request.GET.get('bandwidth'), 'delivery_mode': request.GET.get('mode')}
    if request.user.is_authenticated:
        p = profile_of(request.user)
        initial.update(
            name=request.user.get_full_name(), email=request.user.email, phone=p.phone, company=p.company_name
        )
    form = MitigationForm(request.POST or None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        req = form.save(commit=False)
        if request.user.is_authenticated:
            req.customer = request.user
        req.save()
        messages.success(request, f'Quote request {req.code} received! A specialist will contact you shortly.')
        return redirect('customers:dashboard' if request.user.is_authenticated else 'home:mitigation')
    return render(request, 'orders/mitigation_form.html', {'form': form})
