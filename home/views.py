from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from catalog.models import (
    ColocationSettings,
    DedicatedServer,
    MitigationDeliveryMode,
    MitigationTier,
    OperatingSystem,
    VPSSettings,
)
from customers.forms import ContactForm
from customers.models import StockAlert

SORT_OPTIONS = {
    'available': ('Available first', ['-available', '-featured', 'monthly_price', 'name']),
    'price': ('Lowest price', ['monthly_price', 'name']),
    'price-desc': ('Highest price', ['-monthly_price', 'name']),
    'name': ('Name (A–Z)', ['name']),
}


def index(request):
    return render(request, 'home/index.html')


def vps(request):
    return render(
        request,
        'home/vps.html',
        {
            'settings': VPSSettings.current(),
            'operating_systems': OperatingSystem.objects.filter(available_for_vps=True),
        },
    )


def dedicated(request):
    sort = request.GET.get('sort', 'available')
    if sort not in SORT_OPTIONS:
        sort = 'available'
    servers = DedicatedServer.objects.published().order_by(*SORT_OPTIONS[sort][1])
    return render(
        request,
        'home/dedicated.html',
        {
            'servers': servers,
            'sort_options': [(k, v[0]) for k, v in SORT_OPTIONS.items()],
            'sort': sort,
            'available_count': sum(s.available for s in servers),
        },
    )


@require_POST
def notify_me(request, server_id):
    server = get_object_or_404(DedicatedServer, pk=server_id)
    email = (request.POST.get('email') or '').strip().lower()
    back = request.POST.get('next')
    if not (back and url_has_allowed_host_and_scheme(back, {request.get_host()}, request.is_secure())):
        back = 'home:dedicated'
    # The "website" field is a honeypot for bots, just like on the original site.
    if request.POST.get('website'):
        return redirect(back)
    if '@' not in email:
        messages.error(request, 'Please enter a valid e-mail address.')
    else:
        StockAlert.objects.get_or_create(server=server, email=email)
        messages.success(request, f'Done! We will e-mail {email} when the {server.name} is back.')
    return redirect(back)


def colocation(request):
    settings = ColocationSettings.current()
    return render(
        request, 'home/colocation.html', {'settings': settings, 'sizes': range(1, settings.max_unit_size + 1)}
    )


def mitigation(request):
    tiers = list(MitigationTier.objects.all())
    default = next((i for i, t in enumerate(tiers) if t.is_default), len(tiers) // 2)
    return render(
        request,
        'home/mitigation.html',
        {'tiers': tiers, 'default_tier': default, 'modes': MitigationDeliveryMode.objects.all()},
    )


def about(request):
    return render(request, 'home/about.html')


def contact(request):
    initial = {}
    if request.user.is_authenticated:
        initial = {'name': request.user.get_full_name(), 'email': request.user.email}
    form = ContactForm(request.POST or None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        msg = form.save(commit=False)
        if request.user.is_authenticated:
            msg.user = request.user
        msg.save()
        messages.success(request, 'Thank you! We received your message and will get back to you soon.')
        return redirect('home:contact')
    return render(request, 'home/contact.html', {'form': form})
