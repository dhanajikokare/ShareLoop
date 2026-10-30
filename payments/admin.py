from django.contrib import admin
from .models import Payment, Refund, WebhookEvent


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'payment_for', 'amount', 'currency', 'status', 'gateway', 'gateway_order_id', 'created_at')
    list_filter = ('status', 'payment_for', 'gateway', 'currency', 'created_at')
    search_fields = ('user__username', 'gateway_order_id', 'gateway_payment_id')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ('id', 'payment', 'amount', 'status', 'gateway_refund_id', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('payment__gateway_order_id', 'gateway_refund_id', 'reason')


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ('event_id', 'event_type', 'is_processed', 'received_at')
    list_filter = ('is_processed', 'event_type', 'received_at')
    search_fields = ('event_id', 'event_type', 'payload')
    readonly_fields = ('event_id', 'event_type', 'payload', 'received_at')
