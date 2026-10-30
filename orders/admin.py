from django.contrib import admin
from .models import SalesOrder, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('listing', 'unit_price', 'quantity', 'subtotal')


@admin.register(SalesOrder)
class SalesOrderAdmin(admin.ModelAdmin):
    inlines = [OrderItemInline]
    list_display = (
        'order_number', 'buyer', 'seller', 'items_total',
        'platform_fee', 'total_amount', 'fulfillment_type', 'status', 'created_at'
    )
    list_filter = ('status', 'fulfillment_type', 'created_at')
    search_fields = ('order_number', 'buyer__username', 'seller__username', 'delivery_address')
    readonly_fields = ('order_number', 'created_at', 'updated_at')
