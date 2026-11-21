"""Orders, requests, services and billing.

Prices and descriptions are copied into the order when it is placed
(a snapshot), so changing the catalog later never alters past orders.
"""

import calendar
import datetime
from decimal import Decimal

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone


class OrderStatus(models.TextChoices):
    AWAITING_PAYMENT = 'awaiting_payment', 'Awaiting payment'
    PAID = 'paid', 'Paid'
    PROVISIONING = 'provisioning', 'Provisioning'
    ACTIVE = 'active', 'Active'
    SUSPENDED = 'suspended', 'Suspended'
    CANCELLED = 'cancelled', 'Cancelled'


class RequestStatus(models.TextChoices):
    NEW = 'new', 'New'
    IN_REVIEW = 'in_review', 'In review'
    PROPOSAL_SENT = 'proposal_sent', 'Proposal sent'
    APPROVED = 'approved', 'Approved'
    DECLINED = 'declined', 'Declined'
    COMPLETED = 'completed', 'Completed'


class BaseOrder(models.Model):
    PREFIX = 'ORD'

    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    status = models.CharField(max_length=24, choices=OrderStatus.choices, default=OrderStatus.AWAITING_PAYMENT)

    monthly_price = models.DecimalField('full monthly price (R$)', max_digits=10, decimal_places=2)
    coupon = models.ForeignKey('catalog.Coupon', on_delete=models.SET_NULL, null=True, blank=True)
    monthly_discount = models.DecimalField(
        'discount per month (R$)', max_digits=10, decimal_places=2, default=Decimal('0.00')
    )
    discount_months = models.PositiveSmallIntegerField('discounted months', default=0)

    customer_notes = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)

    created_at = models.DateTimeField('ordered at', auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ['-created_at']

    @property
    def code(self):
        return f'{self.PREFIX}-{self.pk:05d}' if self.pk else '—'

    @property
    def discounted_price(self):
        return self.monthly_price - self.monthly_discount

    def apply_coupon(self, coupon, product):
        """Apply the coupon if it is valid for the product. Returns True when applied."""
        if not coupon or not coupon.applies_to(product):
            return False
        self.coupon = coupon
        self.monthly_discount = coupon.discount_on(self.monthly_price)
        self.discount_months = coupon.months
        return True


class VPSOrder(BaseOrder):
    PREFIX = 'VPS'

    vcpu = models.PositiveSmallIntegerField('vCPU')
    ram_gb = models.PositiveSmallIntegerField('RAM (GB)')
    disk_gb = models.PositiveIntegerField('NVMe disk (GB)')
    operating_system = models.ForeignKey('catalog.OperatingSystem', on_delete=models.PROTECT)
    hostname = models.CharField(max_length=63, blank=True)
    ssh_key = models.TextField('public SSH key', blank=True)

    class Meta(BaseOrder.Meta):
        verbose_name = 'VPS order'
        verbose_name_plural = 'VPS orders'

    def __str__(self):
        return f'{self.code} · {self.vcpu} vCPU / {self.ram_gb} GB / {self.disk_gb} GB'

    @property
    def description(self):
        return f'{self.vcpu} vCPU · {self.ram_gb} GB RAM · {self.disk_gb} GB NVMe · {self.operating_system}'


class DedicatedOrder(BaseOrder):
    PREFIX = 'DED'

    server = models.ForeignKey('catalog.DedicatedServer', on_delete=models.PROTECT, related_name='orders')
    server_name = models.CharField('ordered model', max_length=80)
    specs = models.TextField('ordered specs')
    setup_fee = models.DecimalField('setup fee (R$)', max_digits=10, decimal_places=2, default=Decimal('0.00'))
    operating_system = models.ForeignKey('catalog.OperatingSystem', on_delete=models.PROTECT)
    custom_os = models.CharField('requested OS ("Other" option)', max_length=120, blank=True)
    panel_license = models.CharField(max_length=120, blank=True)

    bandwidth = models.ForeignKey(
        'catalog.DedicatedOption',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='+',
        limit_choices_to={'group': 'bandwidth'},
    )
    partitioning = models.ForeignKey(
        'catalog.DedicatedOption',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='+',
        limit_choices_to={'group': 'partitioning'},
    )
    ip_block = models.ForeignKey(
        'catalog.IPBlock', on_delete=models.PROTECT, null=True, blank=True, verbose_name='additional IP block'
    )
    options_price = models.DecimalField(
        'extra options (R$/month)', max_digits=10, decimal_places=2, default=Decimal('0.00')
    )
    options_summary = models.TextField('chosen options', blank=True)

    hostname = models.CharField(max_length=63, blank=True)
    ssh_key = models.TextField('public SSH key', blank=True)

    class Meta(BaseOrder.Meta):
        verbose_name = 'dedicated server order'
        verbose_name_plural = 'dedicated server orders'

    def __str__(self):
        return f'{self.code} · {self.server_name}'

    @property
    def description(self):
        os_name = self.custom_os or self.operating_system
        return f'{self.server_name} · {os_name}'


class ColocationRequest(models.Model):
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=RequestStatus.choices, default=RequestStatus.NEW)
    estimated_price = models.DecimalField('monthly estimate (R$)', max_digits=10, decimal_places=2)
    desired_move_in_date = models.DateField(null=True, blank=True)
    customer_notes = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)
    created_at = models.DateTimeField('requested at', auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'colocation request'
        verbose_name_plural = 'colocation requests'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.code} · {self.customer}'

    @property
    def code(self):
        return f'COL-{self.pk:05d}' if self.pk else '—'

    @property
    def total_units(self):
        return sum(i.size_u for i in self.items.all())


class ColocationItem(models.Model):
    request = models.ForeignKey(ColocationRequest, on_delete=models.CASCADE, related_name='items')
    model = models.CharField('equipment model', max_length=80, blank=True)
    size_u = models.PositiveSmallIntegerField('size (U)')
    watts = models.PositiveIntegerField('power draw (W)')

    class Meta:
        verbose_name = 'equipment'
        verbose_name_plural = 'equipment'

    def __str__(self):
        return f'{self.model or "Server"} · {self.size_u}U · {self.watts} W'


class MitigationRequest(models.Model):
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='customer (if logged in)',
    )
    name = models.CharField(max_length=120)
    email = models.EmailField('e-mail')
    phone = models.CharField(max_length=20)
    company = models.CharField(max_length=120, blank=True)
    bandwidth = models.CharField('clean traffic', max_length=30)
    delivery_mode = models.CharField(max_length=80)
    message = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=RequestStatus.choices, default=RequestStatus.NEW)
    internal_notes = models.TextField(blank=True)
    created_at = models.DateTimeField('requested at', auto_now_add=True)

    class Meta:
        verbose_name = 'Mitigation quote request'
        verbose_name_plural = 'Mitigation quote requests'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.code} · {self.company or self.name}'

    @property
    def code(self):
        return f'MIT-{self.pk:05d}' if self.pk else '—'


# ============================================================ Services and billing


def add_months(date, months=1):
    """Same day N months later (or the last day of that month)."""
    m = date.month - 1 + months
    year, month = date.year + m // 12, m % 12 + 1
    return date.replace(year=year, month=month, day=min(date.day, calendar.monthrange(year, month)[1]))


class Service(models.Model):
    """A service the customer is using (created when the first invoice is paid)."""

    class Kind(models.TextChoices):
        VPS = 'vps', 'VPS'
        DEDICATED = 'dedicated', 'Dedicated server'
        COLOCATION = 'colocation', 'Colocation'
        IP_BLOCK = 'ip_block', 'IP block'
        MITIGATION = 'mitigation', 'Anti-DDoS (Mitigation)'
        SUPPORT = 'support', 'Premium support'

    class Status(models.TextChoices):
        PROVISIONING = 'provisioning', 'Provisioning'
        ACTIVE = 'active', 'Active'
        SUSPENDED = 'suspended', 'Suspended'
        CANCELLED = 'cancelled', 'Cancelled'

    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='services')
    kind = models.CharField(max_length=12, choices=Kind.choices)
    description = models.CharField(max_length=200)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PROVISIONING)
    monthly_price = models.DecimalField('monthly price (R$)', max_digits=10, decimal_places=2)
    cycle_months = models.PositiveSmallIntegerField('billing cycle (months)', default=1)
    next_renewal = models.DateField(null=True, blank=True)
    auto_renew = models.BooleanField(default=False)

    hostname = models.CharField(max_length=63, blank=True)
    primary_ip = models.GenericIPAddressField('primary IP', null=True, blank=True)
    extra_ips = models.TextField('additional IPs / blocks', blank=True, help_text='One per line.')
    access_details = models.TextField('access details (visible to the customer)', blank=True)

    vps_order = models.OneToOneField(VPSOrder, on_delete=models.SET_NULL, null=True, blank=True, related_name='service')
    dedicated_order = models.OneToOneField(
        DedicatedOrder, on_delete=models.SET_NULL, null=True, blank=True, related_name='service'
    )
    activated_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'service'
        verbose_name_plural = 'services'
        ordering = ['status', '-created_at']

    def __str__(self):
        return f'{self.code} · {self.description}'

    @property
    def code(self):
        return f'SRV-{self.pk:05d}' if self.pk else '—'


class Invoice(models.Model):
    class Kind(models.TextChoices):
        ORDER = 'order', 'New order'
        RENEWAL = 'renewal', 'Renewal'
        CREDIT = 'credit', 'Credit top-up'
        MANUAL = 'manual', 'Manual'

    class Status(models.TextChoices):
        OPEN = 'open', 'Open'
        PAID = 'paid', 'Paid'
        CANCELLED = 'cancelled', 'Cancelled'

    PAYMENT_METHODS = [
        ('pix', 'PIX'),
        ('boleto', 'Boleto'),
        ('card', 'Card'),
        ('credit', 'Account credit'),
        ('other', 'Other'),
    ]

    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='invoices')
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.ORDER)
    description = models.CharField(max_length=200)
    amount = models.DecimalField('amount (R$)', max_digits=10, decimal_places=2)
    due_date = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHODS, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    vps_order = models.ForeignKey(VPSOrder, on_delete=models.SET_NULL, null=True, blank=True, related_name='invoices')
    dedicated_order = models.ForeignKey(
        DedicatedOrder, on_delete=models.SET_NULL, null=True, blank=True, related_name='invoices'
    )
    service = models.ForeignKey(Service, on_delete=models.SET_NULL, null=True, blank=True, related_name='invoices')
    created_at = models.DateTimeField('issued at', auto_now_add=True)

    class Meta:
        verbose_name = 'invoice'
        verbose_name_plural = 'invoices'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.number} · R$ {self.amount}'

    @property
    def number(self):
        return f'INV-{self.pk:06d}' if self.pk else '—'

    @property
    def is_overdue(self):
        return self.status == self.Status.OPEN and self.due_date < timezone.localdate()

    @classmethod
    def for_order(cls, order, days_until_due=3):
        """Issue the first invoice of a new order (discounted month + setup fee)."""
        amount = order.discounted_price + getattr(order, 'setup_fee', 0)
        field = 'vps_order' if isinstance(order, VPSOrder) else 'dedicated_order'
        return cls.objects.create(
            customer=order.customer,
            kind=cls.Kind.ORDER,
            amount=amount,
            description=f'{order.code} · {order.description} (first month)',
            due_date=timezone.localdate() + datetime.timedelta(days=days_until_due),
            **{field: order},
        )

    def mark_paid(self, method='pix'):
        """Settle the invoice and release what it was charging for (new service, renewal or credit)."""
        if self.status == self.Status.PAID:
            return
        with transaction.atomic():
            self.status, self.paid_at, self.payment_method = self.Status.PAID, timezone.now(), method
            self.save()
            order = self.vps_order or self.dedicated_order
            if order and order.status == OrderStatus.AWAITING_PAYMENT:
                order.status = OrderStatus.PROVISIONING
                order.save(update_fields=['status', 'updated_at'])
                already_has_service = Service.objects.filter(
                    models.Q(vps_order=self.vps_order, vps_order__isnull=False)
                    | models.Q(dedicated_order=self.dedicated_order, dedicated_order__isnull=False)
                ).exists()
                if not already_has_service:
                    self.service = Service.objects.create(
                        customer=self.customer,
                        kind=Service.Kind.VPS if self.vps_order else Service.Kind.DEDICATED,
                        description=order.description,
                        monthly_price=order.monthly_price,
                        hostname=order.hostname,
                        next_renewal=add_months(timezone.localdate()),
                        vps_order=self.vps_order,
                        dedicated_order=self.dedicated_order,
                    )
                    self.save(update_fields=['service'])
            elif self.service and self.kind == self.Kind.RENEWAL:
                base = self.service.next_renewal or timezone.localdate()
                self.service.next_renewal = add_months(base, self.service.cycle_months)
                self.service.save(update_fields=['next_renewal'])
            elif self.kind == self.Kind.CREDIT:
                CreditTransaction.objects.create(
                    customer=self.customer,
                    amount=self.amount,
                    description=f'Credit from invoice {self.number}',
                    invoice=self,
                )


class CreditTransaction(models.Model):
    """Account credit ledger. Positive amount = top-up, negative = usage."""

    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='credit_transactions')
    amount = models.DecimalField('amount (R$)', max_digits=10, decimal_places=2)
    description = models.CharField(max_length=200)
    invoice = models.ForeignKey(Invoice, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField('date', auto_now_add=True)

    class Meta:
        verbose_name = 'credit transaction'
        verbose_name_plural = 'credit ledger'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.amount:+} · {self.description}'
