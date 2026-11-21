from django.contrib import admin, messages
from django.utils import timezone

from .models import (
    ColocationItem,
    ColocationRequest,
    CreditTransaction,
    DedicatedOrder,
    Invoice,
    MitigationRequest,
    Service,
    VPSOrder,
)


class InvoiceInline(admin.TabularInline):
    model = Invoice
    extra = 0
    fields = ['number', 'description', 'amount', 'due_date', 'status', 'paid_at']
    readonly_fields = fields
    can_delete = False
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(VPSOrder)
class VPSOrderAdmin(admin.ModelAdmin):
    list_display = [
        'code',
        'customer',
        'vcpu',
        'ram_gb',
        'disk_gb',
        'operating_system',
        'monthly_price',
        'coupon',
        'status',
        'created_at',
    ]
    list_filter = ['status', 'operating_system', 'coupon']
    search_fields = ['customer__email', 'hostname']
    list_select_related = ['customer', 'operating_system', 'coupon']
    autocomplete_fields = ['customer']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [InvoiceInline]


@admin.register(DedicatedOrder)
class DedicatedOrderAdmin(admin.ModelAdmin):
    list_display = ['code', 'customer', 'server_name', 'monthly_price', 'coupon', 'status', 'created_at']
    list_filter = ['status', 'server']
    search_fields = ['customer__email', 'server_name', 'hostname']
    list_select_related = ['customer', 'coupon']
    autocomplete_fields = ['customer']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [InvoiceInline]


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = [
        'code',
        'customer',
        'kind',
        'description',
        'hostname',
        'primary_ip',
        'monthly_price',
        'status',
        'next_renewal',
    ]
    list_filter = ['kind', 'status', 'auto_renew']
    search_fields = ['customer__email', 'description', 'hostname', 'primary_ip']
    list_select_related = ['customer']
    autocomplete_fields = ['customer']
    inlines = [InvoiceInline]
    actions = ['activate']

    @admin.action(description='Mark as active (delivered)')
    def activate(self, request, queryset):
        for s in queryset:
            s.status, s.activated_at = Service.Status.ACTIVE, s.activated_at or timezone.now()
            s.save(update_fields=['status', 'activated_at'])
            order = s.vps_order or s.dedicated_order
            if order:
                order.status = 'active'
                order.save(update_fields=['status'])


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['number', 'customer', 'kind', 'description', 'amount', 'due_date', 'status', 'paid_at']
    list_filter = ['status', 'kind', 'payment_method']
    search_fields = ['customer__email', 'description']
    list_select_related = ['customer']
    autocomplete_fields = ['customer', 'service']
    readonly_fields = ['created_at']
    actions = ['pay_pix', 'pay_boleto', 'cancel']
    date_hierarchy = 'due_date'

    def _pay(self, request, queryset, method):
        n = 0
        for invoice in queryset.filter(status=Invoice.Status.OPEN):
            invoice.mark_paid(method)
            n += 1
        messages.success(request, f'{n} invoice(s) settled. New services were created as "Provisioning".')

    @admin.action(description='Mark as paid (PIX)')
    def pay_pix(self, request, queryset):
        self._pay(request, queryset, 'pix')

    @admin.action(description='Mark as paid (boleto)')
    def pay_boleto(self, request, queryset):
        self._pay(request, queryset, 'boleto')

    @admin.action(description='Cancel invoice')
    def cancel(self, request, queryset):
        queryset.filter(status=Invoice.Status.OPEN).update(status=Invoice.Status.CANCELLED)


@admin.register(CreditTransaction)
class CreditTransactionAdmin(admin.ModelAdmin):
    list_display = ['customer', 'amount', 'description', 'invoice', 'created_at']
    search_fields = ['customer__email', 'description']
    autocomplete_fields = ['customer', 'invoice']


class ColocationItemInline(admin.TabularInline):
    model = ColocationItem
    extra = 0


@admin.register(ColocationRequest)
class ColocationRequestAdmin(admin.ModelAdmin):
    list_display = [
        'code',
        'customer',
        'total_units',
        'estimated_price',
        'desired_move_in_date',
        'status',
        'created_at',
    ]
    list_filter = ['status']
    search_fields = ['customer__email']
    autocomplete_fields = ['customer']
    inlines = [ColocationItemInline]


@admin.register(MitigationRequest)
class MitigationRequestAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'company', 'email', 'phone', 'bandwidth', 'delivery_mode', 'status', 'created_at']
    list_filter = ['status', 'bandwidth', 'delivery_mode']
    search_fields = ['name', 'company', 'email', 'phone']
