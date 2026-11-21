import datetime
from decimal import Decimal
from unittest import mock

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase

from .models import ColocationSettings, Coupon, OperatingSystem, VPSSettings
from .templatetags.bb import money


class MoneyFilterTest(SimpleTestCase):
    def test_formats_amounts(self):
        self.assertEqual(money(Decimal('3000')), '3,000.00')
        self.assertEqual(money('43.5'), '43.50')
        self.assertEqual(money(1234567.891), '1,234,567.89')

    def test_invalid_value_is_returned_unchanged(self):
        self.assertEqual(money('abc'), 'abc')


class VPSSettingsTest(TestCase):
    def test_price_matches_the_original_site(self):
        settings = VPSSettings.current()
        self.assertEqual(settings.calculate(1, 1, 30), Decimal('43.00'))
        self.assertEqual(settings.calculate(4, 8, 100), Decimal('200.00'))

    def test_operating_system_surcharge(self):
        windows = OperatingSystem(name='Win', monthly_price=Decimal('50'))
        self.assertEqual(VPSSettings.current().calculate(1, 1, 30, windows), Decimal('93.00'))

    def test_limits(self):
        settings = VPSSettings.current()
        settings.validate(16, 32, 500)
        for combination in [(17, 1, 30), (1, 0, 30), (1, 1, 35), (1, 1, 510)]:
            with self.subTest(combination=combination), self.assertRaises(ValidationError):
                settings.validate(*combination)

    def test_single_row_table(self):
        VPSSettings(price_per_vcpu=Decimal('99')).save()
        self.assertEqual(VPSSettings.objects.count(), 1)
        self.assertEqual(VPSSettings.current().price_per_vcpu, Decimal('99'))


class ColocationSettingsTest(TestCase):
    def test_estimate_by_units_and_watts(self):
        self.assertEqual(ColocationSettings.current().calculate([(1, 450)]), Decimal('438.00'))


class CouponTest(TestCase):
    def test_validity_and_product(self):
        coupon = Coupon.objects.create(
            code=' promo10 ', product='vps', discount_percent=10, valid_until=datetime.date(2026, 12, 31)
        )
        self.assertEqual(coupon.code, 'PROMO10')
        with mock.patch('django.utils.timezone.localdate', return_value=datetime.date(2026, 12, 1)):
            self.assertTrue(coupon.applies_to('vps'))
            self.assertFalse(coupon.applies_to('dedicated'))
        with mock.patch('django.utils.timezone.localdate', return_value=datetime.date(2027, 1, 1)):
            self.assertFalse(coupon.applies_to('vps'))
        self.assertEqual(coupon.discount_on(Decimal('43')), Decimal('4.30'))
