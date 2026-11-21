from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.utils import timezone

from .models import ContactMessage, CustomerProfile, StockAlert, Ticket, TicketCategory, TicketMessage

User = get_user_model()


class ProfileInline(admin.StackedInline):
    model = CustomerProfile
    can_delete = False
    extra = 0
    fk_name = 'user'


admin.site.unregister(User)


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    inlines = [ProfileInline]
    list_display = ['email', 'first_name', 'last_name', 'is_staff', 'date_joined']


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = [
        'display_name',
        'email',
        'document_type',
        'document_number',
        'phone',
        'support_plan',
        'verified',
        'balance',
        'created_at',
    ]
    list_filter = ['verified', 'support_plan', 'document_type', 'state']
    search_fields = [
        'user__email',
        'user__first_name',
        'user__last_name',
        'document_number',
        'company_name',
        'phone',
    ]
    readonly_fields = ['created_at', 'updated_at', 'terms_accepted_at', 'balance']
    autocomplete_fields = ['user']
    actions = ['mark_verified']
    fieldsets = [
        ('Account', {'fields': ['user', 'support_plan', ('verified', 'verified_at'), 'balance']}),
        ('Identification', {'fields': ['document_type', 'document_number', 'company_name', 'phone']}),
        (
            'Address',
            {'fields': ['country', 'postal_code', 'street', 'number', 'complement', 'district', 'city', 'state']},
        ),
        ('Internal', {'fields': ['internal_notes', 'terms_accepted_at', 'created_at', 'updated_at']}),
    ]

    @admin.display(description='e-mail', ordering='user__email')
    def email(self, obj):
        return obj.user.email

    @admin.display(description='credit balance (R$)')
    def balance(self, obj):
        return obj.credit_balance

    @admin.action(description='Mark account as verified')
    def mark_verified(self, request, queryset):
        n = queryset.update(verified=True, verified_at=timezone.now())
        messages.success(request, f'{n} account(s) verified.')


@admin.register(TicketCategory)
class TicketCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'sort_order', 'active']
    list_editable = ['sort_order', 'active']


class MessageInline(admin.StackedInline):
    model = TicketMessage
    extra = 1
    fields = ['body', 'from_staff', 'author', 'created_at']
    readonly_fields = ['from_staff', 'author', 'created_at']
    verbose_name_plural = 'conversation (write below to reply to the customer)'

    def has_change_permission(self, request, obj=None):
        return False  # sent messages are never edited; only new ones are added


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ['code', 'subject', 'customer', 'category', 'status', 'updated_at']
    list_filter = ['status', 'category']
    search_fields = ['subject', 'customer__email', 'messages__body']
    list_select_related = ['customer', 'category']
    autocomplete_fields = ['customer', 'service']
    inlines = [MessageInline]
    actions = ['mark_resolved']

    def save_formset(self, request, form, formset, change):
        new_messages = formset.save(commit=False)
        for msg in new_messages:
            if not msg.pk:
                msg.author = request.user
                msg.from_staff = True
            msg.save()
        formset.save_m2m()
        if any(m.from_staff for m in new_messages):
            ticket = form.instance
            if ticket.status in (Ticket.Status.OPEN, Ticket.Status.IN_PROGRESS):
                ticket.status = Ticket.Status.WAITING_CUSTOMER
                ticket.save(update_fields=['status', 'updated_at'])

    @admin.action(description='Mark as resolved')
    def mark_resolved(self, request, queryset):
        queryset.update(status=Ticket.Status.RESOLVED)


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'phone', 'subject', 'answered', 'created_at']
    list_editable = ['answered']
    list_filter = ['answered']
    search_fields = ['name', 'email', 'company', 'subject', 'message']
    readonly_fields = ['created_at', 'user']


@admin.register(StockAlert)
class StockAlertAdmin(admin.ModelAdmin):
    list_display = ['email', 'server', 'created_at', 'notified_at']
    list_filter = ['server', ('notified_at', admin.EmptyFieldListFilter)]
    search_fields = ['email']
    actions = ['mark_notified']

    @admin.action(description='Mark as notified')
    def mark_notified(self, request, queryset):
        queryset.update(notified_at=timezone.now())
