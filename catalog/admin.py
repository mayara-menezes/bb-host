from django.contrib import admin
from django.shortcuts import redirect
from django.urls import reverse

from .models import (
    ColocationSettings,
    Coupon,
    DedicatedOption,
    DedicatedServer,
    IPBlock,
    MitigationDeliveryMode,
    MitigationTier,
    OperatingSystem,
    VPSSettings,
)

admin.site.site_header = 'BB Host · Administration'
admin.site.site_title = 'BB Host'
admin.site.index_title = 'Staff dashboard'


class SingletonAdmin(admin.ModelAdmin):
    """Single-row table: the list page jumps straight to the edit form."""

    def has_add_permission(self, request):
        return not self.model.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        obj = self.model.current()
        return redirect(reverse(f'admin:{obj._meta.app_label}_{obj._meta.model_name}_change', args=[obj.pk]))


@admin.register(VPSSettings)
class VPSSettingsAdmin(SingletonAdmin):
    fieldsets = [
        ('Price per resource (R$/month)', {'fields': ['price_per_vcpu', 'price_per_gb_ram', 'price_per_gb_disk']}),
        (
            'Builder limits',
            {'fields': [('vcpu_min', 'vcpu_max'), ('ram_min', 'ram_max'), ('disk_min', 'disk_max', 'disk_step')]},
        ),
        (None, {'fields': ['sales_enabled']}),
    ]


@admin.register(ColocationSettings)
class ColocationSettingsAdmin(SingletonAdmin):
    fields = ['price_per_u', 'price_per_watt', 'default_watts', 'max_unit_size', 'max_servers']


@admin.register(OperatingSystem)
class OperatingSystemAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'family',
        'monthly_price',
        'available_for_vps',
        'available_for_dedicated',
        'requires_panel_license',
        'requires_description',
        'sort_order',
    ]
    list_editable = ['monthly_price', 'available_for_vps', 'available_for_dedicated', 'sort_order']
    list_filter = ['family', 'available_for_vps', 'available_for_dedicated']
    search_fields = ['name']


class OptionInline(admin.TabularInline):
    model = DedicatedOption.servers.through
    extra = 0
    verbose_name = 'extra option'
    verbose_name_plural = 'extra options (bandwidth, partitioning...)'


@admin.register(DedicatedServer)
class DedicatedServerAdmin(admin.ModelAdmin):
    list_display = ['name', 'cpu', 'ram', 'monthly_price', 'available', 'stock', 'featured', 'published', 'sort_order']
    list_editable = ['monthly_price', 'available', 'stock', 'featured', 'published', 'sort_order']
    list_filter = ['available', 'featured', 'published', 'location']
    search_fields = ['name', 'cpu', 'ram', 'storage']
    prepopulated_fields = {'slug': ['name']}
    inlines = [OptionInline]
    fieldsets = [
        (None, {'fields': ['name', 'slug', 'description']}),
        ('Hardware', {'fields': ['cpu', 'ram', 'storage', 'bandwidth', 'location']}),
        ('Pricing', {'fields': ['monthly_price', 'setup_fee']}),
        ('Storefront', {'fields': ['available', 'stock', 'featured', 'published', 'sort_order']}),
    ]


@admin.register(DedicatedOption)
class DedicatedOptionAdmin(admin.ModelAdmin):
    list_display = ['name', 'group', 'monthly_price', 'is_default', 'active', 'server_list']
    list_editable = ['monthly_price', 'is_default', 'active']
    list_filter = ['group', 'active']
    filter_horizontal = ['servers']

    @admin.display(description='servers')
    def server_list(self, obj):
        names = [s.name for s in obj.servers.all()]
        return ', '.join(names) if names else 'All'


@admin.register(IPBlock)
class IPBlockAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'kind',
        'prefix',
        'usable_ips',
        'monthly_price',
        'available_standalone',
        'available_for_dedicated',
        'sort_order',
    ]
    list_editable = ['monthly_price', 'available_standalone', 'available_for_dedicated', 'sort_order']


@admin.register(MitigationTier)
class MitigationTierAdmin(admin.ModelAdmin):
    list_display = ['label', 'mbps', 'is_default', 'sort_order']
    list_editable = ['mbps', 'is_default', 'sort_order']


@admin.register(MitigationDeliveryMode)
class MitigationDeliveryModeAdmin(admin.ModelAdmin):
    list_display = ['name', 'sort_order']
    list_editable = ['sort_order']


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ['code', 'product', 'discount_percent', 'months', 'valid_until', 'active', 'show_in_banner']
    list_editable = ['active', 'show_in_banner']
    list_filter = ['product', 'active']
    search_fields = ['code', 'description']
    fieldsets = [
        (None, {'fields': ['code', 'description', 'product', 'active']}),
        ('Discount', {'fields': ['discount_percent', 'months', ('valid_from', 'valid_until')]}),
        ('Top banner', {'fields': ['show_in_banner', 'banner_tag', 'banner_text', 'banner_fine_print']}),
    ]
