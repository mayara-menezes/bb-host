"""Creates a demo account with services, invoices and support tickets.

Usage:
    python manage.py seed_demo              # customer demo@bbhost.local
    python manage.py seed_demo --admin      # also creates admin@bbhost.local (superuser)
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from catalog.models import ColocationSettings, Coupon, DedicatedServer, OperatingSystem, VPSSettings
from customers.models import CustomerProfile, Ticket, TicketCategory, TicketMessage
from orders.models import (
    ColocationItem,
    ColocationRequest,
    DedicatedOrder,
    Invoice,
    MitigationRequest,
    Service,
    VPSOrder,
)

User = get_user_model()
CUSTOMER_EMAIL = 'demo@bbhost.local'
ADMIN_EMAIL = 'admin@bbhost.local'


class Command(BaseCommand):
    help = 'Creates demo data (a customer with orders, invoices, a service and a support ticket).'

    def add_arguments(self, parser):
        parser.add_argument('--password', default='demo-bbhost-2026', help='Password for the created accounts.')
        parser.add_argument('--admin', action='store_true', help=f'Also create the {ADMIN_EMAIL} superuser.')

    @transaction.atomic
    def handle(self, *args, password, admin, **options):
        if User.objects.filter(username=CUSTOMER_EMAIL).exists():
            self.stdout.write(self.style.WARNING(f'{CUSTOMER_EMAIL} already exists; nothing changed.'))
        else:
            self._create_customer(password)
            self.stdout.write(self.style.SUCCESS(f'Customer created: {CUSTOMER_EMAIL} / {password}'))

        if admin and not User.objects.filter(username=ADMIN_EMAIL).exists():
            User.objects.create_superuser(
                username=ADMIN_EMAIL, email=ADMIN_EMAIL, password=password, first_name='Staff'
            )
            self.stdout.write(self.style.SUCCESS(f'Admin created: {ADMIN_EMAIL} / {password}  ->  /admin/'))

    def _create_customer(self, password):
        user = User.objects.create_user(
            username=CUSTOMER_EMAIL, email=CUSTOMER_EMAIL, password=password, first_name='Demo', last_name='Customer'
        )
        CustomerProfile.objects.create(
            user=user,
            document_type='CNPJ',
            document_number='27.041.737/0001-09',
            company_name='Demo Company LTDA',
            phone='11999998888',
            postal_code='01310-100',
            street='Av. Paulista',
            number='1000',
            district='Bela Vista',
            city='São Paulo',
            state='SP',
            verified=True,
            verified_at=timezone.now(),
            terms_accepted_at=timezone.now(),
        )

        # A paid and delivered VPS
        settings = VPSSettings.current()
        vps_os = OperatingSystem.objects.filter(available_for_vps=True, name__startswith='Ubuntu 24').first()
        vps = VPSOrder(
            customer=user,
            vcpu=4,
            ram_gb=8,
            disk_gb=100,
            operating_system=vps_os,
            hostname='app01.democompany.com',
            monthly_price=settings.calculate(4, 8, 100, vps_os),
        )
        vps.apply_coupon(Coupon.objects.filter(code='BLACKVPS50').first(), 'vps')
        vps.save()
        Invoice.for_order(vps).mark_paid('pix')
        service = Service.objects.get(vps_order=vps)
        service.status, service.activated_at = Service.Status.ACTIVE, timezone.now()
        service.primary_ip, service.auto_renew = '203.0.113.10', True
        service.access_details = 'SSH: root@203.0.113.10\nThe password was sent by e-mail during provisioning.'
        service.save()
        vps.status = 'active'
        vps.save(update_fields=['status'])

        # A dedicated server awaiting payment
        server = DedicatedServer.objects.filter(available=True).order_by('monthly_price').first()
        dedicated_os = OperatingSystem.objects.filter(available_for_dedicated=True).first()
        if server:
            dedicated = DedicatedOrder.objects.create(
                customer=user,
                server=server,
                server_name=server.name,
                specs=server.specs_summary(),
                monthly_price=server.monthly_price,
                operating_system=dedicated_os,
                hostname='db01.democompany.com',
                options_summary='IP: 1× IPv4 (included)',
            )
            Invoice.for_order(dedicated)

        # Credit, colocation, mitigation and a support ticket
        Invoice.objects.create(
            customer=user,
            kind=Invoice.Kind.CREDIT,
            description='Account credit top-up',
            amount=Decimal('200.00'),
            due_date=timezone.localdate(),
        ).mark_paid('pix')

        colocation_settings = ColocationSettings.current()
        items = [('Dell R640', 1, 450), ('Synology storage', 2, 300)]
        req = ColocationRequest.objects.create(
            customer=user,
            estimated_price=colocation_settings.calculate((size, watts) for _, size, watts in items),
            status='in_review',
        )
        for model, size, watts in items:
            ColocationItem.objects.create(request=req, model=model, size_u=size, watts=watts)

        MitigationRequest.objects.create(
            customer=user,
            name='Demo Customer',
            email=CUSTOMER_EMAIL,
            phone='11999998888',
            company='Demo Company LTDA',
            bandwidth='2 Gbps',
            delivery_mode='GRE tunnel',
        )

        ticket = Ticket.objects.create(
            customer=user,
            category=TicketCategory.objects.get(name='Servers / Access'),
            subject='Open port 8080 on the firewall',
            service=service,
            status=Ticket.Status.WAITING_CUSTOMER,
        )
        TicketMessage.objects.create(ticket=ticket, author=user, body='Hi! Could you open port 8080 on my VPS?')
        TicketMessage.objects.create(
            ticket=ticket,
            from_staff=True,
            body='Hi! Port 8080/TCP is now open. Please test it and let us know if you need anything else.',
        )
