"""Loads the catalog published on bbhost.com.br (public site and customer area) on 2026-11-20."""

import datetime
from decimal import Decimal

from django.db import migrations
from django.utils.text import slugify

SAO_PAULO = 'São Paulo - Brazil'

# OS list from the VPS builder (/vps)
VPS_OS = [
    'CentOS 8',
    'Debian 10',
    'Debian 12',
    'Debian 13',
    'Ubuntu 18.04',
    'Ubuntu 20.04',
    'Ubuntu 22.04',
    'Ubuntu 24.04',
    'Windows Server 2019',
    'Windows Server 2022',
]

# OS list from the dedicated "Configure" page: (name, family, asks for license, asks which OS)
DEDICATED_OS = [
    ('Ubuntu 24.04 LTS', 'linux', False, False),
    ('Ubuntu 22.04 LTS', 'linux', False, False),
    ('Debian 12 (Bookworm)', 'linux', False, False),
    ('Debian 13 (Trixie)', 'linux', False, False),
    ('Ubuntu 20.04 LTS (end of standard support)', 'linux', False, False),
    ('AlmaLinux 9 (CentOS/RHEL 9 compatible)', 'linux', False, False),
    ('Rocky Linux 9 (CentOS/RHEL 9 compatible)', 'linux', False, False),
    ('Windows Server 2019 (180-day trial)', 'windows', False, False),
    ('Windows Server 2022 (180-day trial)', 'windows', False, False),
    ('Windows Server 2025', 'windows', False, False),
    ('Proxmox VE 9', 'panel', False, False),
    ('Virtualizor (on AlmaLinux 9)', 'panel', True, False),
    ('cPanel/WHM (on AlmaLinux 9)', 'panel', True, False),
    ('Other — please specify (installed by our team)', 'other', False, True),
]

# name, cpu, ram, storage, bandwidth, price, available, featured
DEDICATED = [
    ('Xeon Silver 4316', '2× Intel Xeon Silver 4316 (40c/80t)', '512 GB DDR4 ECC', '2× 4TB NVMe + 8TB HDD',
     '1 Gbps 95th @ 10 Gbps', 3000, True, True),
    ('Xeon E3-1260L v5', 'Intel Xeon E3-1260L v5 (4c/8t)', '32 GB', '480GB SATA SSD', '1 Gbps', 400, True, False),
    ('Ryzen 9 7950X', 'AMD Ryzen 9 7950X (16c/32t)', '128 GB DDR5', '2TB NVMe', '1 Gbps 95th @ 10 Gbps',
     2000, False, True),
    ('Xeon E3-1240 v2', 'Intel Xeon E3-1240 v2 (4c/8t)', '16 GB', '240GB SATA SSD', '1 Gbps', 400, False, False),
    ('Xeon E-2286G', 'Intel Xeon E-2286G (6c/12t)', '32 GB', '1 TB NVMe', '1 Gbps', 600, False, False),
    ('Xeon E-2356G', 'Intel Xeon E-2356G (6c/12t)', '64 GB', '1 TB NVMe', '1 Gbps', 800, False, False),
    ('Xeon Silver 4110', '2× Intel Xeon Silver 4110 (16c/32t)', '128 GB', '800GB SATA SSD', '1 Gbps 95th @ 10 Gbps',
     800, False, False),
    ('Xeon Silver 4114', '2× Intel Xeon Silver 4114 (20c/40t)', '128 GB', '800GB SATA SSD', '1 Gbps 95th @ 10 Gbps',
     800, False, False),
    ('Xeon E-2388G', 'Intel Xeon E-2388G (8c/16t)', '64 GB', '1 TB NVMe', '1 Gbps', 1000, False, False),
    ('Ryzen 9 9950X', 'AMD Ryzen 9 9950X (16c/32t)', '192 GB', '2 TB NVMe', '1 Gbps 95th @ 10 Gbps',
     2500, False, False),
]  # fmt: skip

# Options seen on the Xeon Silver 4316 page: (group, name, price, default)
XEON_4316_OPTIONS = [
    ('bandwidth', '1 Gbps 95th @ 10 Gbps', 0, True),
    ('bandwidth', '10 Gbps unmetered', 3000, False),
    ('partitioning', 'Default (everything on /)', 0, True),
    ('partitioning', 'Separate /home (50%/50%)', 0, False),
]

# name, kind, prefix, usable IPs, price
IP_BLOCKS = [
    ('IPv4 /29 block (5 usable IPs)', 'ipv4', 29, 5, 80),
    ('IPv4 /28 block (13 usable IPs)', 'ipv4', 28, 13, 208),
    ('IPv4 /27 block (29 usable IPs)', 'ipv4', 27, 29, 464),
    ('IPv4 /26 block (61 usable IPs)', 'ipv4', 26, 61, 976),
    ('BYO-IP /24 (announce your own block)', 'byoip', 24, 0, 1000),
    ('IPv4 /25 block (125 usable IPs)', 'ipv4', 25, 125, 1600),
    ('IPv4 /24 block (253 usable IPs)', 'ipv4', 24, 253, 2500),
]

TIERS = [
    ('100 Mbps', 100),
    ('200 Mbps', 200),
    ('300 Mbps', 300),
    ('500 Mbps', 500),
    ('1 Gbps', 1000),
    ('2 Gbps', 2000),
    ('3 Gbps', 3000),
    ('5 Gbps', 5000),
    ('10 Gbps+', 10000),
]

DELIVERY_MODES = ['GRE tunnel', 'Dedicated VLAN', 'Direct Connect (cross-connect / PNI)', 'Not sure — advise me']


def load(apps, schema_editor):
    def model(name):
        return apps.get_model('catalog', name)

    model('VPSSettings').objects.update_or_create(
        pk=1,
        defaults={
            'price_per_vcpu': Decimal('15.00'),
            'price_per_gb_ram': Decimal('10.00'),
            'price_per_gb_disk': Decimal('0.60'),
            'vcpu_min': 1,
            'vcpu_max': 16,
            'ram_min': 1,
            'ram_max': 32,
            'disk_min': 30,
            'disk_max': 500,
            'disk_step': 10,
        },
    )
    model('ColocationSettings').objects.update_or_create(
        pk=1,
        defaults={
            'price_per_u': Decimal('150.00'),
            'price_per_watt': Decimal('0.64'),
            'default_watts': 450,
            'max_unit_size': 10,
        },
    )

    OS = model('OperatingSystem')
    for i, name in enumerate(VPS_OS):
        OS.objects.get_or_create(
            name=name,
            defaults={
                'family': 'windows' if name.startswith('Windows') else 'linux',
                'sort_order': i,
                'available_for_vps': True,
                'available_for_dedicated': False,
            },
        )
    for i, (name, family, license_, description) in enumerate(DEDICATED_OS):
        OS.objects.get_or_create(
            name=name,
            defaults={
                'family': family,
                'sort_order': 100 + i,
                'available_for_vps': False,
                'available_for_dedicated': True,
                'requires_panel_license': license_,
                'requires_description': description,
            },
        )

    Server = model('DedicatedServer')
    for i, (name, cpu, ram, storage, bandwidth, price, available, featured) in enumerate(DEDICATED):
        Server.objects.get_or_create(
            name=name,
            defaults={
                'slug': slugify(name),
                'cpu': cpu,
                'ram': ram,
                'storage': storage,
                'bandwidth': bandwidth,
                'location': SAO_PAULO,
                'monthly_price': Decimal(price),
                'available': available,
                'stock': 1 if available else 0,
                'featured': featured,
                'sort_order': i,
            },
        )

    xeon_4316 = Server.objects.get(name='Xeon Silver 4316')
    Option = model('DedicatedOption')
    for i, (group, name, price, default) in enumerate(XEON_4316_OPTIONS):
        option, _ = Option.objects.get_or_create(
            group=group,
            name=name,
            defaults={'monthly_price': Decimal(price), 'is_default': default, 'sort_order': i},
        )
        option.servers.add(xeon_4316)

    Block = model('IPBlock')
    for i, (name, kind, prefix, ips, price) in enumerate(IP_BLOCKS):
        Block.objects.get_or_create(
            name=name,
            defaults={
                'kind': kind,
                'prefix': prefix,
                'usable_ips': ips,
                'monthly_price': Decimal(price),
                'sort_order': i,
            },
        )

    Tier = model('MitigationTier')
    for i, (label, mbps) in enumerate(TIERS):
        Tier.objects.get_or_create(label=label, defaults={'mbps': mbps, 'sort_order': i, 'is_default': mbps == 1000})

    Mode = model('MitigationDeliveryMode')
    for i, name in enumerate(DELIVERY_MODES):
        Mode.objects.get_or_create(name=name, defaults={'sort_order': i})

    model('Coupon').objects.get_or_create(
        code='BLACKVPS50',
        defaults={
            'description': 'Black Friday: 50% off the first 3 VPS invoices',
            'product': 'vps',
            'discount_percent': Decimal('50'),
            'months': 3,
            'valid_until': datetime.date(2026, 12, 7),
            'show_in_banner': True,
            'banner_tag': 'BLACK FRIDAY',
            'banner_text': 'on VPS for 3 months',
            'banner_fine_print': 'New monthly plans · discount on the first 3 invoices · cannot be combined',
        },
    )


class Migration(migrations.Migration):
    dependencies = [('catalog', '0001_initial')]
    operations = [migrations.RunPython(load, migrations.RunPython.noop)]
