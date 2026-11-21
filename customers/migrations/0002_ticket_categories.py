"""Ticket categories used by the original customer area."""

from django.db import migrations

CATEGORIES = [
    'Abuse / Security',
    'Customer service / Triage',
    'Sales',
    'Sales / Anti-DDoS',
    'Sales / Colocation',
    'Sales / New order',
    'Sales / Service scope',
    'Sales / Licensing',
    'Sales / Plans',
    'Contracts / Digital signature',
    'Billing',
    'Control panel / Account',
    'Procedures',
    'Servers',
    'Servers / Access',
    'Servers / Remote desktop (RDP)',
    'Servers / CDN cache',
    'Servers / Network and mitigation',
    'Servers / Operating system',
    'Services / Discontinuation',
    'Technical',
]


def load(apps, schema_editor):
    Category = apps.get_model('customers', 'TicketCategory')
    for i, name in enumerate(CATEGORIES):
        Category.objects.get_or_create(name=name, defaults={'sort_order': i})


class Migration(migrations.Migration):
    dependencies = [('customers', '0001_initial')]
    operations = [migrations.RunPython(load, migrations.RunPython.noop)]
