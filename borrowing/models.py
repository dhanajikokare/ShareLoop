from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class BorrowRequest(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending Owner Approval'),
        ('ACCEPTED', 'Accepted by Owner'),
        ('REJECTED', 'Rejected by Owner'),
        ('ACTIVE', 'Active / Borrowed'),
        ('RETURN_PENDING', 'Return Pending Inspection'),
        ('COMPLETED', 'Returned & Completed'),
        ('CANCELLED', 'Cancelled'),
    ]

    request_reference = models.CharField(max_length=32, unique=True, editable=False)
    listing = models.ForeignKey('listings.Listing', on_delete=models.PROTECT, related_name='borrow_requests')
    borrower = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='borrow_requests')

    start_date = models.DateField()
    end_date = models.DateField()
    total_days = models.PositiveIntegerField(default=1)

    # Free borrowing guarantee
    is_free = models.BooleanField(default=True, editable=False, help_text='Borrowing is always free of rental fees')
    security_deposit = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Refundable deposit if required by owner',
    )

    borrower_message = models.TextField(help_text='Why you need this item and how you will care for it')
    rejection_reason = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')

    agreed_to_terms = models.BooleanField(
        default=False,
        help_text='Borrower explicitly agreed to treat the item carefully and return on time',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def clean(self):
        super().clean()
        if self.start_date and self.end_date:
            if self.end_date < self.start_date:
                raise ValidationError({'end_date': 'Return date must be on or after borrow date.'})

            days = (self.end_date - self.start_date).days + 1
            if self.listing_id:
                listing = self.listing
                if self.borrower_id and listing.owner_id == self.borrower_id:
                    raise ValidationError('You cannot borrow your own item.')
                if days > listing.borrow_max_days:
                    raise ValidationError(f'Maximum allowed borrowing period for this item is {listing.borrow_max_days} days.')

        if not self.agreed_to_terms:
            raise ValidationError({'agreed_to_terms': 'You must agree to the borrowing conditions and return policy.'})

    def save(self, *args, **kwargs):
        if not self.request_reference:
            import uuid
            self.request_reference = f"BRW-{uuid.uuid4().hex[:10].upper()}"
        if self.start_date and self.end_date:
            self.total_days = (self.end_date - self.start_date).days + 1
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.request_reference} - {self.listing.title} ({self.get_status_display()})"
