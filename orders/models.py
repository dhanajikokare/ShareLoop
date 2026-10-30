from decimal import Decimal
from django.conf import settings
from django.db import models, transaction
from django.core.exceptions import ValidationError


class SalesOrder(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Order Placed (Awaiting Confirmation)'),
        ('PAYMENT_PENDING', 'Awaiting Payment'),
        ('CONFIRMED', 'Order Confirmed'),
        ('PROCESSING', 'Processing Order'),
        ('READY_FOR_PICKUP', 'Ready for Pickup'),
        ('SHIPPED', 'Shipped / Dispatched'),
        ('DELIVERED', 'Delivered'),
        ('COMPLETED', 'Completed & Received'),
        ('CANCELLED', 'Cancelled'),
        ('REFUNDED', 'Refunded'),
    ]

    FULFILLMENT_CHOICES = [
        ('PICKUP', 'Self Pickup by Buyer'),
        ('DELIVERY', 'Direct Delivery / Courier'),
    ]

    order_number = models.CharField(max_length=32, unique=True, editable=False)
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='sales_orders_bought')
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='sales_orders_sold')

    items_total = models.DecimalField(max_digits=10, decimal_places=2)
    platform_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)

    fulfillment_type = models.CharField(max_length=20, choices=FULFILLMENT_CHOICES, default='PICKUP')
    delivery_address = models.TextField(blank=True, help_text='Pickup instructions or buyer shipping address')
    buyer_note = models.TextField(blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.order_number:
            import uuid
            self.order_number = f"ORD-{uuid.uuid4().hex[:10].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.order_number} - {self.seller.display_name} -> {self.buyer.display_name} ({self.get_status_display()})"


class OrderItem(models.Model):
    order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE, related_name='items')
    listing = models.ForeignKey('listings.Listing', on_delete=models.PROTECT, related_name='order_items')
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)

    def save(self, *args, **kwargs):
        self.subtotal = Decimal(self.quantity) * self.unit_price
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.quantity}x {self.listing.title} @ ₹{self.unit_price}"
