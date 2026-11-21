"""Customer data, support tickets and messages received through the site."""

from django.conf import settings
from django.db import models

BRAZILIAN_STATES = [
    (uf, uf) for uf in 'AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO'.split()
]


class CustomerProfile(models.Model):
    """Customer registration data. The login is the e-mail (User.username = User.email)."""

    DOCUMENT_TYPES = [
        ('CPF', 'CPF (Brazilian individual taxpayer ID)'),
        ('CNPJ', 'CNPJ (Brazilian company ID)'),
        ('PASSPORT', 'Passport'),
        ('FOREIGN_ID', 'Foreign ID'),
    ]
    SUPPORT_PLANS = [('standard', 'Standard'), ('premium', 'Premium')]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    document_type = models.CharField(max_length=12, choices=DOCUMENT_TYPES, default='CPF')
    document_number = models.CharField('tax ID / document number', max_length=30, blank=True)
    company_name = models.CharField(max_length=150, blank=True)
    phone = models.CharField('phone / WhatsApp', max_length=20, blank=True)

    country = models.CharField(max_length=60, default='Brazil')
    postal_code = models.CharField(max_length=12, blank=True)
    street = models.CharField('street address', max_length=150, blank=True)
    number = models.CharField(max_length=10, blank=True)
    complement = models.CharField('apartment, suite, etc.', max_length=60, blank=True)
    district = models.CharField('neighborhood', max_length=80, blank=True)
    city = models.CharField(max_length=80, blank=True)
    state = models.CharField(max_length=2, choices=BRAZILIAN_STATES, blank=True)

    support_plan = models.CharField(max_length=10, choices=SUPPORT_PLANS, default='standard')
    verified = models.BooleanField(
        'verified account',
        default=False,
        help_text='Signed contract + ID document + selfie checked. Unlocks colocation requests.',
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    terms_accepted_at = models.DateTimeField(null=True, blank=True)
    internal_notes = models.TextField(blank=True)

    created_at = models.DateTimeField('signed up at', auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'customer'
        verbose_name_plural = 'customers'
        ordering = ['-created_at']

    def __str__(self):
        return self.display_name

    @property
    def display_name(self):
        return self.user.get_full_name() or self.user.email or self.user.username

    @property
    def is_complete(self):
        return all([self.document_number, self.phone, self.postal_code, self.street, self.city])

    @property
    def credit_balance(self):
        total = self.user.credit_transactions.aggregate(s=models.Sum('amount'))['s']
        return total or 0


class TicketCategory(models.Model):
    name = models.CharField(max_length=80, unique=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'ticket category'
        verbose_name_plural = 'ticket categories'
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name


class Ticket(models.Model):
    class Status(models.TextChoices):
        OPEN = 'open', 'Open'
        WAITING_CUSTOMER = 'waiting_customer', 'Waiting for customer'
        IN_PROGRESS = 'in_progress', 'In progress'
        RESOLVED = 'resolved', 'Resolved'
        CLOSED = 'closed', 'Closed'

    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tickets')
    category = models.ForeignKey(TicketCategory, on_delete=models.PROTECT)
    subject = models.CharField(max_length=150)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    service = models.ForeignKey(
        'orders.Service', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='related service'
    )
    created_at = models.DateTimeField('opened at', auto_now_add=True)
    updated_at = models.DateTimeField('last update', auto_now=True)

    class Meta:
        verbose_name = 'support ticket'
        verbose_name_plural = 'support tickets'
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.code} · {self.subject}'

    @property
    def code(self):
        return f'#{self.pk:05d}' if self.pk else '—'

    @property
    def is_closed(self):
        return self.status in (self.Status.RESOLVED, self.Status.CLOSED)


class TicketMessage(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='messages')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    from_staff = models.BooleanField('staff reply', default=False)
    body = models.TextField('message')
    created_at = models.DateTimeField('sent at', auto_now_add=True)

    class Meta:
        verbose_name = 'message'
        verbose_name_plural = 'messages'
        ordering = ['created_at']

    def __str__(self):
        return f'{"Staff" if self.from_staff else "Customer"} · {self.created_at:%Y-%m-%d %H:%M}'


class ContactMessage(models.Model):
    name = models.CharField(max_length=120)
    phone = models.CharField('phone number', max_length=20, blank=True)
    email = models.EmailField('e-mail')
    company = models.CharField(max_length=120, blank=True)
    subject = models.CharField(max_length=150)
    message = models.TextField('your question')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='logged-in user'
    )
    answered = models.BooleanField(default=False)
    created_at = models.DateTimeField('received at', auto_now_add=True)

    class Meta:
        verbose_name = 'contact message'
        verbose_name_plural = 'contact messages'
        ordering = ['answered', '-created_at']

    def __str__(self):
        return f'{self.name} — {self.subject}'


class StockAlert(models.Model):
    """ "Notify me when it's back" requests for sold-out dedicated servers."""

    server = models.ForeignKey('catalog.DedicatedServer', on_delete=models.CASCADE, related_name='stock_alerts')
    email = models.EmailField('e-mail')
    notified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField('requested at', auto_now_add=True)

    class Meta:
        verbose_name = 'stock alert'
        verbose_name_plural = 'stock alerts'
        ordering = ['notified_at', '-created_at']
        constraints = [models.UniqueConstraint(fields=['server', 'email'], name='one_alert_per_server_and_email')]

    def __str__(self):
        return f'{self.email} → {self.server.name}'
