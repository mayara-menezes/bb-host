"""Products and price tables.

Everything here is editable in the admin (/admin/) and feeds the public pages.
"""

from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from .templatetags.bb import money

CENTS = Decimal('0.01')


def round_money(value):
    return Decimal(value).quantize(CENTS, rounding=ROUND_HALF_UP)


class Singleton(models.Model):
    """Settings table with a single row (pk=1)."""

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('This settings table cannot be deleted.')

    @classmethod
    def current(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


# --------------------------------------------------------------------------- VPS


class VPSSettings(Singleton):
    """Price per resource and limits of the VPS builder."""

    price_per_vcpu = models.DecimalField(
        'price per vCPU (R$/month)', max_digits=10, decimal_places=2, default=Decimal('15.00')
    )
    price_per_gb_ram = models.DecimalField(
        'price per GB of RAM (R$/month)', max_digits=10, decimal_places=2, default=Decimal('10.00')
    )
    price_per_gb_disk = models.DecimalField(
        'price per GB of NVMe disk (R$/month)', max_digits=10, decimal_places=2, default=Decimal('0.60')
    )

    vcpu_min = models.PositiveSmallIntegerField('minimum vCPU', default=1)
    vcpu_max = models.PositiveSmallIntegerField('maximum vCPU', default=16)
    ram_min = models.PositiveSmallIntegerField('minimum RAM (GB)', default=1)
    ram_max = models.PositiveSmallIntegerField('maximum RAM (GB)', default=32)
    disk_min = models.PositiveIntegerField('minimum disk (GB)', default=30)
    disk_max = models.PositiveIntegerField('maximum disk (GB)', default=500)
    disk_step = models.PositiveIntegerField('disk step (GB)', default=10)

    sales_enabled = models.BooleanField('accepting orders', default=True)

    class Meta:
        verbose_name = 'VPS settings'
        verbose_name_plural = 'VPS settings'

    def __str__(self):
        return 'VPS prices and limits'

    def clean(self):
        for resource in ('vcpu', 'ram', 'disk'):
            if getattr(self, f'{resource}_min') > getattr(self, f'{resource}_max'):
                raise ValidationError(f'The {resource} minimum cannot be greater than the maximum.')

    def validate(self, vcpu, ram, disk):
        """Make sure the chosen combination respects the limits."""
        errors = []
        if not self.vcpu_min <= vcpu <= self.vcpu_max:
            errors.append(f'vCPU must be between {self.vcpu_min} and {self.vcpu_max}.')
        if not self.ram_min <= ram <= self.ram_max:
            errors.append(f'RAM must be between {self.ram_min} and {self.ram_max} GB.')
        if not self.disk_min <= disk <= self.disk_max or (disk - self.disk_min) % self.disk_step:
            step = self.disk_step
            errors.append(f'Disk must be between {self.disk_min} and {self.disk_max} GB, in steps of {step} GB.')
        if errors:
            raise ValidationError(errors)

    def calculate(self, vcpu, ram, disk, operating_system=None):
        total = vcpu * self.price_per_vcpu + ram * self.price_per_gb_ram + disk * self.price_per_gb_disk
        if operating_system:
            total += operating_system.monthly_price
        return round_money(total)


class OperatingSystem(models.Model):
    FAMILIES = [('linux', 'Linux'), ('windows', 'Windows'), ('panel', 'Panel / hypervisor'), ('other', 'Other')]

    name = models.CharField(max_length=80, unique=True)
    family = models.CharField(max_length=10, choices=FAMILIES, default='linux')
    monthly_price = models.DecimalField(
        'monthly surcharge (R$)',
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='E.g. a Windows license. Leave 0 when there is no extra cost.',
    )
    available_for_vps = models.BooleanField('available for VPS', default=True)
    available_for_dedicated = models.BooleanField('available for dedicated servers', default=True)
    requires_panel_license = models.BooleanField(
        'asks for a panel license', default=False, help_text='cPanel, Virtualizor, etc.: the customer enters the key.'
    )
    requires_description = models.BooleanField(
        'asks which OS to install', default=False, help_text='"Other" option: installed manually by the team.'
    )
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = 'operating system'
        verbose_name_plural = 'operating systems'
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name


# --------------------------------------------------------------- Dedicated servers


class DedicatedServerQuerySet(models.QuerySet):
    def published(self):
        return self.filter(published=True)


class DedicatedServer(models.Model):
    name = models.CharField(
        'model name', max_length=80, unique=True, help_text='Name shown on the card, e.g. "Xeon Silver 4316".'
    )
    slug = models.SlugField(max_length=90, unique=True, blank=True)

    cpu = models.CharField('CPU', max_length=120, help_text='E.g. 2× Intel Xeon Silver 4316 (40c/80t)')
    ram = models.CharField('RAM', max_length=80, help_text='E.g. 512 GB DDR4 ECC')
    storage = models.CharField(max_length=120, help_text='E.g. 2× 4TB NVMe + 8TB HDD')
    bandwidth = models.CharField(max_length=80, default='1 Gbps')
    location = models.CharField(max_length=80, default='São Paulo - Brazil')
    description = models.TextField(blank=True)

    monthly_price = models.DecimalField('monthly price (R$)', max_digits=10, decimal_places=2)
    setup_fee = models.DecimalField('setup fee (R$)', max_digits=10, decimal_places=2, default=Decimal('0.00'))

    available = models.BooleanField(
        'available to order', default=True, help_text='Unchecked = shown as "On request" with a "Notify me" option.'
    )
    stock = models.PositiveSmallIntegerField(
        'machines in stock', default=0, help_text='Informational. Use "available" to control the storefront.'
    )
    featured = models.BooleanField('highlight card', default=False)
    published = models.BooleanField('show on site', default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = DedicatedServerQuerySet.as_manager()

    class Meta:
        verbose_name = 'dedicated server'
        verbose_name_plural = 'dedicated servers'
        ordering = ['-available', '-featured', 'monthly_price', 'name']

    def __str__(self):
        return f'{self.name} (R$ {money(self.monthly_price)}/month)'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def specs(self):
        """(label, icon, value) rows used by the cards."""
        return [
            ('CPU', 'fa-microchip', self.cpu),
            ('RAM', 'fa-th', self.ram),
            ('Storage', 'fa-hdd-o', self.storage),
            ('Bandwidth', 'fa-exchange', self.bandwidth),
            ('Location', 'fa-map-marker', self.location),
        ]

    def specs_summary(self):
        return (
            f'CPU: {self.cpu} | RAM: {self.ram} | Storage: {self.storage} | '
            f'Bandwidth: {self.bandwidth} | Location: {self.location}'
        )


class DedicatedOption(models.Model):
    """Extras chosen on the dedicated server "Configure" page (bandwidth, partitioning...)."""

    GROUPS = [('bandwidth', 'Bandwidth'), ('partitioning', 'Partitioning'), ('other', 'Other')]

    group = models.CharField(max_length=20, choices=GROUPS)
    name = models.CharField(max_length=120)
    monthly_price = models.DecimalField(
        'monthly surcharge (R$)', max_digits=10, decimal_places=2, default=Decimal('0.00')
    )
    servers = models.ManyToManyField(
        DedicatedServer, blank=True, related_name='options', help_text='Leave empty to offer it on every server.'
    )
    is_default = models.BooleanField('default option of the group', default=False)
    sort_order = models.PositiveSmallIntegerField(default=0)
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'dedicated server option'
        verbose_name_plural = 'dedicated server options'
        ordering = ['group', 'sort_order', 'monthly_price']

    def __str__(self):
        extra = f' (+ R$ {money(self.monthly_price)}/month)' if self.monthly_price else ''
        return f'{self.get_group_display()}: {self.name}{extra}'


class IPBlock(models.Model):
    """IP blocks sold standalone or together with dedicated servers."""

    KINDS = [('ipv4', 'IPv4 block'), ('byoip', 'BYO-IP (customer block)')]

    name = models.CharField(max_length=80)
    kind = models.CharField(max_length=10, choices=KINDS, default='ipv4')
    prefix = models.PositiveSmallIntegerField('prefix (/n)', help_text='29 for /29, 24 for /24...')
    usable_ips = models.PositiveIntegerField('usable IPs', default=0)
    monthly_price = models.DecimalField('monthly price (R$)', max_digits=10, decimal_places=2)
    available_standalone = models.BooleanField('orderable from the customer area', default=True)
    available_for_dedicated = models.BooleanField('offered with dedicated servers', default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = 'IP block'
        verbose_name_plural = 'IP blocks'
        ordering = ['sort_order', '-prefix']

    def __str__(self):
        return f'{self.name} (R$ {money(self.monthly_price)}/month)'


# --------------------------------------------------------------------- Colocation


class ColocationSettings(Singleton):
    price_per_u = models.DecimalField('price per U (R$/month)', max_digits=10, decimal_places=2, default=Decimal('150'))
    price_per_watt = models.DecimalField(
        'price per watt (R$/month)', max_digits=10, decimal_places=4, default=Decimal('0.6400')
    )
    default_watts = models.PositiveIntegerField('suggested power draw (W)', default=450)
    max_unit_size = models.PositiveSmallIntegerField('largest server size (U)', default=10)
    max_servers = models.PositiveSmallIntegerField('maximum servers per request', default=20)

    class Meta:
        verbose_name = 'colocation settings'
        verbose_name_plural = 'colocation settings'

    def __str__(self):
        return 'Colocation prices'

    def calculate(self, items):
        """items: iterable of (size_u, watts)."""
        return round_money(sum(u * self.price_per_u + w * self.price_per_watt for u, w in items))


# --------------------------------------------------------------------- Mitigation


class MitigationTier(models.Model):
    label = models.CharField(max_length=30, help_text='E.g. 500 Mbps, 1 Gbps, 10 Gbps+')
    mbps = models.PositiveIntegerField('traffic in Mbps', help_text='Used only for sorting and reports.')
    is_default = models.BooleanField('initial slider position', default=False)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = 'clean traffic tier (Mitigation)'
        verbose_name_plural = 'clean traffic tiers (Mitigation)'
        ordering = ['sort_order', 'mbps']

    def __str__(self):
        return self.label


class MitigationDeliveryMode(models.Model):
    name = models.CharField(max_length=80, unique=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = 'delivery mode (Mitigation)'
        verbose_name_plural = 'delivery modes (Mitigation)'
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name


# ------------------------------------------------------------------------ Coupons


class CouponQuerySet(models.QuerySet):
    def current(self):
        today = timezone.localdate()
        return self.filter(active=True).filter(
            models.Q(valid_from__isnull=True) | models.Q(valid_from__lte=today),
            models.Q(valid_until__isnull=True) | models.Q(valid_until__gte=today),
        )


class Coupon(models.Model):
    PRODUCTS = [('vps', 'VPS'), ('dedicated', 'Dedicated server'), ('all', 'All products')]

    code = models.CharField(max_length=30, unique=True)
    description = models.CharField(max_length=160, blank=True)
    product = models.CharField(max_length=10, choices=PRODUCTS, default='vps')
    discount_percent = models.DecimalField('discount (%)', max_digits=5, decimal_places=2)
    months = models.PositiveSmallIntegerField(
        'discounted months', default=1, help_text='How many monthly invoices get the discount.'
    )
    valid_from = models.DateField(null=True, blank=True)
    valid_until = models.DateField(null=True, blank=True)
    active = models.BooleanField(default=True)

    # Promo banner at the top of the site
    show_in_banner = models.BooleanField('show in the top banner', default=False)
    banner_tag = models.CharField(max_length=30, blank=True, help_text='E.g. BLACK FRIDAY')
    banner_text = models.CharField(max_length=120, blank=True, help_text='E.g. on VPS for 3 months')
    banner_fine_print = models.CharField(max_length=200, blank=True)

    objects = CouponQuerySet.as_manager()

    class Meta:
        verbose_name = 'coupon'
        verbose_name_plural = 'coupons'
        ordering = ['-active', 'code']

    def __str__(self):
        return self.code

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        super().save(*args, **kwargs)

    def applies_to(self, product):
        today = timezone.localdate()
        return (
            self.active
            and self.product in (product, 'all')
            and (self.valid_from is None or self.valid_from <= today)
            and (self.valid_until is None or self.valid_until >= today)
        )

    def discount_on(self, amount):
        return round_money(amount * self.discount_percent / 100)
