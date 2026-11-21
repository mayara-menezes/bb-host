from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.filter
def money(value):
    """1234.5 -> '1,234.50' (amounts are in Brazilian reais, shown as R$)."""
    try:
        value = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return value
    return f'{value:,.2f}'
