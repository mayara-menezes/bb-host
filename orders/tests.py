"""End-to-end tests of the site flows (run with: python manage.py test)."""

import datetime
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from catalog.models import Coupon, DedicatedOption, DedicatedServer, OperatingSystem, VPSSettings
from customers.models import ContactMessage, CustomerProfile, StockAlert, Ticket, TicketCategory

from .models import (
    ColocationRequest,
    DedicatedOrder,
    Invoice,
    MitigationRequest,
    Service,
    VPSOrder,
    add_months,
)

User = get_user_model()
VALID_CPF = '529.982.247-25'


class BaseTestCase(TestCase):
    def create_customer(self, email='customer@test.com', verified=False):
        user = User.objects.create_user(username=email, email=email, password='Strong-pass-123', first_name='Ana')
        CustomerProfile.objects.create(user=user, document_number=VALID_CPF, phone='11999998888', verified=verified)
        self.client.force_login(user)
        return user


class PublicPagesTest(BaseTestCase):
    def test_pages_load_and_show_database_data(self):
        for name in ['index', 'vps', 'dedicated', 'colocation', 'mitigation', 'about', 'contact']:
            self.assertEqual(self.client.get(reverse(f'home:{name}')).status_code, 200, name)
        response = self.client.get(reverse('home:dedicated'))
        self.assertContains(response, 'Xeon Silver 4316')
        self.assertContains(response, '3,000.00')
        self.assertContains(response, '2 plans available now')
        self.assertContains(self.client.get('/'), 'BLACKVPS50')  # the banner comes from the coupon

    def test_price_edited_in_the_database_shows_on_the_site(self):
        DedicatedServer.objects.filter(name='Xeon E3-1260L v5').update(monthly_price=Decimal('450'))
        self.assertContains(self.client.get(reverse('home:dedicated')), '450.00')
        settings = VPSSettings.current()
        settings.price_per_vcpu = Decimal('20')
        settings.save()
        self.assertContains(self.client.get(reverse('home:vps')), 'data-pcpu="20.00"')

    def test_dedicated_sorting(self):
        response = self.client.get(reverse('home:dedicated') + '?sort=price-desc')
        self.assertEqual(response.context['servers'][0].name, 'Xeon Silver 4316')


class SignupLoginTest(BaseTestCase):
    def test_signup_creates_user_and_profile(self):
        response = self.client.post(
            reverse('customers:signup'),
            {
                'name': 'Maria Souza',
                'email': 'Maria@Test.com',
                'phone': '(11) 98888-7777',
                'document_type': 'CPF',
                'document_number': '52998224725',
                'password': 'Strong-pass-123',
                'password2': 'Strong-pass-123',
                'accept_terms': 'on',
            },
        )
        self.assertRedirects(response, reverse('customers:dashboard'))
        user = User.objects.get(email='maria@test.com')
        self.assertEqual(user.profile.document_number, VALID_CPF)
        self.assertEqual(user.first_name, 'Maria')

    def test_invalid_cpf_is_rejected(self):
        response = self.client.post(
            reverse('customers:signup'),
            {
                'name': 'X',
                'email': 'x@t.com',
                'phone': '11988887777',
                'document_type': 'CPF',
                'document_number': '111.111.111-11',
                'password': 'Strong-pass-123',
                'password2': 'Strong-pass-123',
                'accept_terms': 'on',
            },
        )
        self.assertContains(response, 'Invalid CPF')

    def test_login_with_email(self):
        User.objects.create_user(username='a@b.com', email='a@b.com', password='Strong-pass-123')
        response = self.client.post(reverse('customers:login'), {'username': 'A@B.com', 'password': 'Strong-pass-123'})
        self.assertRedirects(response, reverse('customers:dashboard'))


class VPSFlowTest(BaseTestCase):
    def test_vps_with_coupon_creates_order_invoice_and_service(self):
        os_choice = OperatingSystem.objects.filter(available_for_vps=True).first()
        # a visitor builds the VPS and is sent to the login page
        response = self.client.post(
            reverse('orders:vps_checkout'), {'cpu': 2, 'ram': 4, 'disk': 50, 'os': os_choice.pk}
        )
        self.assertRedirects(response, reverse('orders:vps_review'), fetch_redirect_response=False)
        self.assertRedirects(
            self.client.get(reverse('orders:vps_review')), reverse('customers:login') + '?next=/vps/review'
        )
        customer = self.create_customer()
        response = self.client.post(
            reverse('orders:vps_review'),
            {'action': 'confirm', 'coupon': 'BLACKVPS50', 'hostname': 'vps01.test.com'},
        )
        order = VPSOrder.objects.get(customer=customer)
        self.assertRedirects(response, reverse('orders:vps_detail', args=[order.pk]))
        self.assertEqual(order.monthly_price, Decimal('100.00'))  # 2*15 + 4*10 + 50*0.6
        self.assertEqual(order.monthly_discount, Decimal('50.00'))
        invoice = order.invoices.get()
        self.assertEqual(invoice.amount, Decimal('50.00'))

        invoice.mark_paid('pix')
        order.refresh_from_db()
        self.assertEqual(order.status, 'provisioning')
        service = Service.objects.get(customer=customer)
        self.assertEqual(service.hostname, 'vps01.test.com')
        self.assertContains(self.client.get(reverse('customers:services')), 'vps01.test.com')

    def test_vps_limits_are_validated(self):
        os_choice = OperatingSystem.objects.filter(available_for_vps=True).first()
        self.client.post(reverse('orders:vps_checkout'), {'cpu': 99, 'ram': 4, 'disk': 50, 'os': os_choice.pk})
        self.assertNotIn('vps_config', self.client.session)

    def test_coupon_for_another_product_is_rejected(self):
        Coupon.objects.create(code='DEDICATEDONLY', product='dedicated', discount_percent=10)
        os_choice = OperatingSystem.objects.filter(available_for_vps=True).first()
        self.create_customer()
        self.client.post(reverse('orders:vps_checkout'), {'cpu': 1, 'ram': 1, 'disk': 30, 'os': os_choice.pk})
        response = self.client.post(reverse('orders:vps_review'), {'action': 'confirm', 'coupon': 'DEDICATEDONLY'})
        self.assertContains(response, 'Invalid or expired coupon')
        self.assertFalse(VPSOrder.objects.exists())


class DedicatedFlowTest(BaseTestCase):
    def setUp(self):
        self.server = DedicatedServer.objects.get(name='Xeon Silver 4316')
        self.os = OperatingSystem.objects.get(name='Ubuntu 24.04 LTS')

    def test_options_add_to_the_price(self):
        self.create_customer()
        unmetered = DedicatedOption.objects.get(name='10 Gbps unmetered')
        response = self.client.post(
            reverse('orders:dedicated_configure', args=[self.server.slug]),
            {
                'bandwidth': unmetered.pk,
                'operating_system': self.os.pk,
                'partitioning': DedicatedOption.objects.get(name='Default (everything on /)').pk,
            },
        )
        order = DedicatedOrder.objects.get()
        self.assertRedirects(response, reverse('orders:dedicated_detail', args=[order.pk]))
        self.assertEqual(order.monthly_price, Decimal('6000.00'))
        self.assertIn('10 Gbps unmetered', order.options_summary)
        self.assertEqual(order.invoices.get().amount, Decimal('6000.00'))

    def test_cpanel_requires_a_license(self):
        self.create_customer()
        cpanel = OperatingSystem.objects.get(name__startswith='cPanel')
        response = self.client.post(
            reverse('orders:dedicated_configure', args=[self.server.slug]), {'operating_system': cpanel.pk}
        )
        self.assertContains(response, 'requires a panel license')
        self.assertFalse(DedicatedOrder.objects.exists())

    def test_unavailable_server_is_not_sold_and_accepts_alerts(self):
        self.create_customer()
        ryzen = DedicatedServer.objects.get(name='Ryzen 9 7950X')
        self.client.post(reverse('orders:dedicated_configure', args=[ryzen.slug]), {'operating_system': self.os.pk})
        self.assertFalse(DedicatedOrder.objects.exists())
        for _ in range(2):  # submitting twice does not duplicate
            self.client.post(reverse('home:notify_me', args=[ryzen.pk]), {'email': 'x@y.com'})
        self.assertEqual(StockAlert.objects.filter(server=ryzen).count(), 1)

    def test_visitor_is_sent_to_login(self):
        response = self.client.post(
            reverse('orders:dedicated_configure', args=[self.server.slug]), {'operating_system': self.os.pk}
        )
        self.assertTrue(response['Location'].startswith(reverse('customers:login')))


class ColocationMitigationFlowTest(BaseTestCase):
    def test_colocation_requires_a_verified_account(self):
        self.create_customer(verified=False)
        self.assertContains(self.client.get(reverse('orders:colocation_new')), 'Unverified account')

    def test_colocation_saves_items_and_estimate(self):
        self.create_customer(verified=True)
        rows = {'model': ['Dell R640', ''], 'size': ['1', '2'], 'watts': ['450', '300']}
        self.client.post(reverse('orders:colocation_start'), rows)
        response = self.client.post(reverse('orders:colocation_new'), rows)
        req = ColocationRequest.objects.get()
        self.assertRedirects(response, reverse('orders:colocation_detail', args=[req.pk]))
        self.assertEqual(req.items.count(), 2)
        self.assertEqual(req.estimated_price, Decimal('930.00'))  # 3U*150 + 750W*0.64

    def test_mitigation_quote_from_a_visitor(self):
        response = self.client.post(
            reverse('orders:mitigation_quote'),
            {
                'bandwidth': '5 Gbps',
                'delivery_mode': 'GRE tunnel',
                'name': 'John',
                'email': 'j@e.com',
                'phone': '11999990000',
                'company': 'Company X',
            },
        )
        self.assertRedirects(response, reverse('home:mitigation'))
        self.assertEqual(MitigationRequest.objects.get().bandwidth, '5 Gbps')


class CustomerAreaTest(BaseTestCase):
    def test_contact_form_saves_the_message(self):
        self.client.post(reverse('home:contact'), {'name': 'A', 'email': 'a@a.com', 'subject': 'Hi', 'message': 'Test'})
        self.assertEqual(ContactMessage.objects.count(), 1)

    def test_ticket_and_reply(self):
        customer = self.create_customer()
        category = TicketCategory.objects.get(name='Billing')
        self.client.post(
            reverse('customers:ticket_new'),
            {'subject': 'Tax invoice', 'category': category.pk, 'message': 'I need the tax invoice'},
        )
        ticket = Ticket.objects.get(customer=customer)
        self.client.post(reverse('customers:ticket', args=[ticket.pk]), {'action': 'reply', 'body': 'Thanks'})
        self.assertEqual(ticket.messages.count(), 2)
        someone_else = User.objects.create_user(username='b@b.com', email='b@b.com', password='x')
        self.client.force_login(someone_else)
        self.assertEqual(self.client.get(reverse('customers:ticket', args=[ticket.pk])).status_code, 404)

    def test_credit_becomes_balance_after_payment(self):
        customer = self.create_customer()
        self.client.post(reverse('customers:credit'), {'amount': '150'})
        invoice = Invoice.objects.get(customer=customer, kind='credit')
        invoice.mark_paid('pix')
        self.assertEqual(customer.profile.credit_balance, Decimal('150.00'))
        self.assertContains(self.client.get(reverse('customers:dashboard')), '150.00')

    def test_customer_area_requires_login(self):
        for name in ['dashboard', 'profile', 'services', 'invoices', 'credit', 'tickets']:
            response = self.client.get(reverse(f'customers:{name}'))
            self.assertTrue(response['Location'].startswith(reverse('customers:login')), name)


class AddMonthsTest(TestCase):
    def test_end_of_month_and_year_rollover(self):
        self.assertEqual(add_months(datetime.date(2026, 1, 31)), datetime.date(2026, 2, 28))
        self.assertEqual(add_months(datetime.date(2026, 12, 15)), datetime.date(2027, 1, 15))
        self.assertEqual(add_months(datetime.date(2026, 11, 30), 3), datetime.date(2027, 2, 28))


class SeedDemoTest(TestCase):
    def test_creates_data_and_is_idempotent(self):
        call_command('seed_demo', '--admin', stdout=StringIO())
        call_command('seed_demo', '--admin', stdout=StringIO())
        demo = User.objects.get(username='demo@bbhost.local')
        self.assertEqual(Service.objects.filter(customer=demo, status='active').count(), 1)
        self.assertEqual(demo.profile.credit_balance, Decimal('200.00'))
        self.assertTrue(User.objects.get(username='admin@bbhost.local').is_superuser)
