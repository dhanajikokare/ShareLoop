from decimal import Decimal
from django.conf import settings
from django.db import models


class Payment(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending Payment'),
        ('SUCCESS', 'Payment Successful / Verified'),
        ('FAILED', 'Payment Failed'),
        ('REFUNDED', 'Refunded'),
    ]

    PAYMENT_FOR_CHOICES = [
        ('RENTAL', 'Rental Booking Fee & Deposit'),
        ('SALE', 'Product Purchase Order'),
        ('BORROW_DEPOSIT', 'Borrow Refundable Deposit'),
    ]

    GATEWAY_CHOICES = [
        ('RAZORPAY', 'Razorpay Payment Gateway'),
        ('SIMULATED_TEST', 'ShareLoop Test Mode / Sandbox (Safe Demo)'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='payments')
    payment_for = models.CharField(max_length=20, choices=PAYMENT_FOR_CHOICES)

    # Specific relations
    rental_booking = models.ForeignKey(
        'rentals.RentalBooking',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments',
    )
    sales_order = models.ForeignKey(
        'orders.SalesOrder',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments',
    )
    borrow_request = models.ForeignKey(
        'borrowing.BorrowRequest',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments',
    )

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='INR')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    gateway = models.CharField(max_length=20, choices=GATEWAY_CHOICES, default='RAZORPAY')

    gateway_order_id = models.CharField(max_length=100, blank=True)
    gateway_payment_id = models.CharField(max_length=100, blank=True)
    gateway_signature = models.CharField(max_length=255, blank=True)

    error_code = models.CharField(max_length=100, blank=True)
    error_description = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Payment #{self.id} (₹{self.amount} - {self.get_status_display()})"


class Refund(models.Model):
    STATUS_CHOICES = [
        ('INITIATED', 'Initiated'),
        ('PROCESSED', 'Processed'),
        ('FAILED', 'Failed'),
    ]

    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name='refunds')
    gateway_refund_id = models.CharField(max_length=100, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='INITIATED')
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Refund for Payment #{self.payment_id}: ₹{self.amount} ({self.status})"


class WebhookEvent(models.Model):
    event_id = models.CharField(max_length=100, unique=True, help_text='Unique Gateway Event ID to enforce idempotency')
    event_type = models.CharField(max_length=100)
    payload = models.TextField(help_text='Raw webhook JSON body')
    is_processed = models.BooleanField(default=False)
    error_message = models.TextField(blank=True)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-received_at']

    def __str__(self):
        return f"Webhook {self.event_type} - {self.event_id}"
