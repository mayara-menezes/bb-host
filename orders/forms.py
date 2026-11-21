from decimal import Decimal

from django import forms
from django.db import models

from catalog.models import (
    ColocationSettings,
    Coupon,
    DedicatedOption,
    IPBlock,
    MitigationDeliveryMode,
    MitigationTier,
    OperatingSystem,
    VPSSettings,
)
from catalog.templatetags.bb import money
from customers.forms import StyledFormMixin

from .models import MitigationRequest


class VPSConfigForm(forms.Form):
    """Validates what comes from the VPS builder (sliders)."""

    cpu = forms.IntegerField()
    ram = forms.IntegerField()
    disk = forms.IntegerField()
    os = forms.ModelChoiceField(queryset=OperatingSystem.objects.filter(available_for_vps=True))

    def clean(self):
        data = super().clean()
        if self.errors:
            return data
        VPSSettings.current().validate(data['cpu'], data['ram'], data['disk'])
        return data


class CheckoutForm(StyledFormMixin, forms.Form):
    coupon = forms.CharField(label='Discount coupon', max_length=30, required=False)
    hostname = forms.CharField(
        label='Hostname (optional)',
        max_length=63,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'vps01.yourcompany.com'}),
    )
    ssh_key = forms.CharField(
        label='Public SSH key (optional)',
        required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'ssh-ed25519 AAAA...'}),
    )
    notes = forms.CharField(label='Notes (optional)', required=False, widget=forms.Textarea(attrs={'rows': 3}))

    def __init__(self, *args, product, **kwargs):
        self.product = product
        super().__init__(*args, **kwargs)

    def clean_coupon(self):
        code = self.cleaned_data['coupon'].strip().upper()
        if not code:
            return None
        coupon = Coupon.objects.filter(code=code).first()
        if not coupon or not coupon.applies_to(self.product):
            raise forms.ValidationError('Invalid or expired coupon, or not valid for this product.')
        return coupon


class PricedSelect(forms.Select):
    """Select whose <option>s carry data-price (and OS flags) so the JS can add up the total."""

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        opt = super().create_option(name, value, label, selected, index, subindex, attrs)
        obj = getattr(value, 'instance', None)
        if obj is not None:
            opt['attrs']['data-price'] = str(getattr(obj, 'monthly_price', 0))
            if getattr(obj, 'requires_description', False):
                opt['attrs']['data-needs'] = 'description'
            elif getattr(obj, 'requires_panel_license', False):
                opt['attrs']['data-needs'] = 'license'
        else:
            opt['attrs']['data-price'] = '0'
        return opt


class PricedChoiceField(forms.ModelChoiceField):
    widget = PricedSelect

    def label_from_instance(self, obj):
        price = getattr(obj, 'monthly_price', 0)
        return f'{obj.name} (+ R$ {money(price)}/month)' if price else obj.name


class DedicatedOrderForm(CheckoutForm):
    bandwidth = PricedChoiceField(
        label='Bandwidth', queryset=DedicatedOption.objects.none(), empty_label=None, required=False
    )
    operating_system = PricedChoiceField(
        label='Operating system',
        queryset=OperatingSystem.objects.filter(available_for_dedicated=True),
        empty_label=None,
    )
    custom_os = forms.CharField(
        label='Which operating system?',
        max_length=120,
        required=False,
        help_text='We have no ready-made image for this option. Please give the exact version.',
    )
    panel_license = forms.CharField(
        label='Panel license (cPanel/Virtualizor)',
        max_length=120,
        required=False,
        help_text='Enter the key; the installer runs on first boot.',
    )
    partitioning = PricedChoiceField(
        label='Partitioning', queryset=DedicatedOption.objects.none(), empty_label=None, required=False
    )
    ip_block = PricedChoiceField(
        label='IP addressing',
        required=False,
        empty_label='1× IPv4 (included)',
        queryset=IPBlock.objects.filter(available_for_dedicated=True),
    )
    hostname = forms.CharField(
        label='Hostname (optional)',
        max_length=63,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'srv01.yourcompany.com'}),
    )

    field_order = [
        'bandwidth',
        'operating_system',
        'custom_os',
        'panel_license',
        'partitioning',
        'ip_block',
        'hostname',
        'ssh_key',
        'coupon',
        'notes',
    ]

    def __init__(self, *args, server, **kwargs):
        super().__init__(*args, product='dedicated', **kwargs)
        self.server = server
        for group in ('bandwidth', 'partitioning'):
            qs = (
                DedicatedOption.objects.filter(active=True, group=group)
                .filter(models.Q(servers=server) | models.Q(servers__isnull=True))
                .distinct()
            )
            if qs.exists():
                self.fields[group].queryset = qs
                self.fields[group].initial = qs.filter(is_default=True).first()
            else:
                del self.fields[group]
        # marker for the JS that recalculates the total on screen
        for name in ('bandwidth', 'partitioning', 'ip_block', 'operating_system'):
            if name in self.fields:
                self.fields[name].widget.attrs['data-priced'] = '1'

    def clean(self):
        data = super().clean()
        os_choice = data.get('operating_system')
        if os_choice and os_choice.requires_description and not data.get('custom_os'):
            self.add_error('custom_os', 'Tell us which operating system to install.')
        if os_choice and os_choice.requires_panel_license and not data.get('panel_license'):
            self.add_error('panel_license', 'This system requires a panel license.')
        return data

    def chosen_options(self):
        d = self.cleaned_data
        choices = (d.get('bandwidth'), d.get('partitioning'), d.get('ip_block'), d.get('operating_system'))
        return [o for o in choices if o]

    def options_price(self):
        return sum((o.monthly_price for o in self.chosen_options()), Decimal('0.00'))

    def summary(self):
        d = self.cleaned_data

        def label(o):
            return f'{o.name} (+ R$ {money(o.monthly_price)}/month)' if o.monthly_price else o.name

        lines = []
        if d.get('bandwidth'):
            lines.append(f'Bandwidth: {label(d["bandwidth"])}')
        if d.get('partitioning'):
            lines.append(f'Partitioning: {label(d["partitioning"])}')
        lines.append(f'IP: {label(d["ip_block"]) if d.get("ip_block") else "1× IPv4 (included)"}')
        return '\n'.join(lines)


class ColocationForm(StyledFormMixin, forms.Form):
    desired_move_in_date = forms.DateField(
        label='Preferred move-in date', required=False, widget=forms.DateInput(attrs={'type': 'date'})
    )
    notes = forms.CharField(
        label='Notes',
        required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Network ports, full rack, IPs, etc.'}),
    )


def read_colocation_items(data):
    """Read the model[]/size[]/watts[] rows from the form. Returns (items, errors)."""
    cfg = ColocationSettings.current()
    models_, sizes, watts = data.getlist('model'), data.getlist('size'), data.getlist('watts')
    items, errors = [], []
    for i, (m, u, w) in enumerate(zip(models_, sizes, watts, strict=False), start=1):
        try:
            u, w = int(u), int(w or 0)
        except ValueError:
            errors.append(f'Server {i}: invalid size or power draw.')
            continue
        if not 1 <= u <= cfg.max_unit_size:
            errors.append(f'Server {i}: size must be between 1U and {cfg.max_unit_size}U.')
        if not 0 <= w <= 10000:
            errors.append(f'Server {i}: power draw must be between 0 and 10,000 W.')
        items.append({'model': m.strip()[:80], 'size_u': u, 'watts': w})
    if not items:
        errors.append('Add at least one server.')
    if len(items) > cfg.max_servers:
        errors.append(f'Up to {cfg.max_servers} servers per request.')
    return items, errors


class MitigationForm(StyledFormMixin, forms.ModelForm):
    bandwidth = forms.ModelChoiceField(
        label='Clean traffic delivered', queryset=MitigationTier.objects.all(), to_field_name='label', empty_label=None
    )
    delivery_mode = forms.ModelChoiceField(
        queryset=MitigationDeliveryMode.objects.all(), to_field_name='name', empty_label=None
    )

    class Meta:
        model = MitigationRequest
        fields = ['bandwidth', 'delivery_mode', 'name', 'email', 'phone', 'company', 'message']
        labels = {'message': 'Tell us a bit about your operation (optional)'}
        widgets = {'message': forms.Textarea(attrs={'rows': 4})}

    def clean_bandwidth(self):
        return self.cleaned_data['bandwidth'].label

    def clean_delivery_mode(self):
        return self.cleaned_data['delivery_mode'].name
