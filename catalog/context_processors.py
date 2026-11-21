from .models import Coupon


def promo(request):
    """Coupon shown in the top banner (the first current coupon flagged for the banner)."""
    if request.path.startswith('/admin/'):
        return {}
    return {'promo': Coupon.objects.current().filter(show_in_banner=True).first()}
