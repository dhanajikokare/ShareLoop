from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class RentalBooking(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending Owner Approval'),
        ('ACCEPTED', 'Accepted (Awaiting Payment)'),
        ('REJECTED', 'Rejected by Owner'),
        ('PAYMENT_PENDING', 'Payment Processing'),
        ('CONFIRMED', 'Confirmed & Ready for Handover'),
        ('ACTIVE', 'Active / Item Handed Over'),
        ('RETURN_PENDING', 'Return Initiated'),
        ('COMPLETED', 'Completed & Returned'),
        ('CANCELLED', 'Cancelled'),
        ('DISPUTED', 'Dispute Raised'),
        ('REFUNDED', 'Refunded'),
    ]

    booking_reference = models.CharField(max_length=32, unique=True, editable=False)
    listing = models.ForeignKey('listings.Listing', on_delete=models.PROTECT, related_name='rental_bookings')
    renter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='rental_bookings')

    start_date = models.DateField()
    end_date = models.DateField()
    total_days = models.PositiveIntegerField(default=1)

    daily_rate = models.DecimalField(max_digits=10, decimal_places=2)
    rental_fee = models.DecimalField(max_digits=10, decimal_places=2)
    security_deposit = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    platform_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    renter_message = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def clean(self):
        super().clean()
        if self.start_date and self.end_date:
            if self.end_date < self.start_date:
                raise ValidationError({'end_date': 'Return date must be on or after pickup date.'})

            days = (self.end_date - self.start_date).days + 1
            if self.listing_id:
                listing = self.listing
                if self.renter_id and listing.owner_id == self.renter_id:
                    raise ValidationError('You cannot rent your own item.')
                if days < listing.min_rental_days:
                    raise ValidationError(f'Minimum rental period is {listing.min_rental_days} day(s).')
                if days > listing.max_rental_days:
                    raise ValidationError(f'Maximum rental period is {listing.max_rental_days} day(s).')

    def save(self, *args, **kwargs):
        if not self.booking_reference:
            import uuid
            self.booking_reference = f"RNT-{uuid.uuid4().hex[:10].upper()}"
        if self.start_date and self.end_date:
            self.total_days = (self.end_date - self.start_date).days + 1
        super().save(*args, **kwargs)

    @classmethod
    def calculate_cost(cls, listing, start_date, end_date):
        """
        Pure calculation helper returning dictionary of all cost components.
        Never uses float for financial calculations.
        """
        days = (end_date - start_date).days + 1
        daily_rate = listing.rent_price_per_day
        rental_fee = Decimal(days) * daily_rate
        deposit = listing.rent_security_deposit or Decimal('0.00')

        commission_pct = Decimal(str(settings.PLATFORM_COMMISSION_PERCENTAGE)) / Decimal('100.00')
        platform_fee = (rental_fee * commission_pct).quantize(Decimal('0.01'))
        total_amount = rental_fee + deposit + platform_fee

        return {
            'days': days,
            'daily_rate': daily_rate,
            'rental_fee': rental_fee,
            'security_deposit': deposit,
            'platform_fee': platform_fee,
            'total_amount': total_amount,
        }

    def __str__(self):
        return f"{self.booking_reference} - {self.listing.title} ({self.get_status_display()})"
