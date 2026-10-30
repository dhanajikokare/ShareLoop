from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class HandoverLog(models.Model):
    LOG_TYPES = [
        ('RENTAL_HANDOVER', 'Rental Initial Handover (Pickup)'),
        ('RENTAL_RETURN', 'Rental Return (Inspection)'),
        ('BORROW_HANDOVER', 'Borrow Initial Handover'),
        ('BORROW_RETURN', 'Borrow Return (Inspection)'),
        ('SALE_HANDOVER', 'Sale Handover / Delivery'),
    ]

    CONDITION_ASSESSMENT = [
        ('PRISTINE', 'Pristine / Like New'),
        ('GOOD', 'Good - Normal Expected Wear'),
        ('SCRATCHES_MINOR', 'Minor Scratches / Cosmetic Wear'),
        ('DAMAGED', 'Damaged / Needs Attention'),
        ('MISSING_PARTS', 'Missing Accessories or Parts'),
    ]

    log_type = models.CharField(max_length=30, choices=LOG_TYPES)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='recorded_handovers')

    # Associated transaction links
    rental_booking = models.ForeignKey(
        'rentals.RentalBooking',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='handover_logs',
    )
    borrow_request = models.ForeignKey(
        'borrowing.BorrowRequest',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='handover_logs',
    )
    sales_order = models.ForeignKey(
        'orders.SalesOrder',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='handover_logs',
    )

    item_condition = models.CharField(max_length=30, choices=CONDITION_ASSESSMENT, default='GOOD')
    notes = models.TextField(help_text='Detailed observation notes, defects noticed, or handover confirmation')
    evidence_photo = models.ImageField(upload_to='evidence/%Y/%m/', blank=True, null=True)

    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def can_access(self, user):
        """
        Only participants (buyer/renter/borrower or seller/owner) or staff can access this evidence.
        """
        if not user.is_authenticated:
            return False
        if user.is_staff or user.is_superuser:
            return True
        if self.rental_booking:
            return user.id in (self.rental_booking.renter_id, self.rental_booking.listing.owner_id)
        if self.borrow_request:
            return user.id in (self.borrow_request.borrower_id, self.borrow_request.listing.owner_id)
        if self.sales_order:
            return user.id in (self.sales_order.buyer_id, self.sales_order.seller_id)
        return False

    def __str__(self):
        return f"{self.get_log_type_display()} by {self.recorded_by.username} at {self.timestamp:%Y-%m-%d %H:%M}"


class Review(models.Model):
    TRANSACTION_TYPES = [
        ('RENTAL', 'Rental Transaction'),
        ('BORROW', 'Borrow Transaction'),
        ('SALE', 'Sale Purchase'),
    ]

    MODERATION_CHOICES = [
        ('PUBLISHED', 'Published'),
        ('UNDER_REVIEW', 'Under Moderation'),
        ('HIDDEN', 'Hidden by Admin'),
    ]

    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews_written')
    reviewee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews_received')
    listing = models.ForeignKey('listings.Listing', on_delete=models.CASCADE, related_name='reviews')

    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    rental_booking = models.ForeignKey('rentals.RentalBooking', on_delete=models.SET_NULL, null=True, blank=True)
    borrow_request = models.ForeignKey('borrowing.BorrowRequest', on_delete=models.SET_NULL, null=True, blank=True)
    sales_order = models.ForeignKey('orders.SalesOrder', on_delete=models.SET_NULL, null=True, blank=True)

    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text='Rating from 1 to 5 stars',
    )
    title = models.CharField(max_length=120, blank=True)
    comment = models.TextField()
    moderation_status = models.CharField(max_length=20, choices=MODERATION_CHOICES, default='PUBLISHED')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def clean(self):
        super().clean()
        if self.reviewer_id and self.reviewee_id and self.reviewer_id == self.reviewee_id:
            raise ValidationError('You cannot review yourself or your own transaction.')

        # Enforce single review per participant-transaction
        if self.rental_booking_id and self.reviewer_id:
            if Review.objects.filter(reviewer=self.reviewer, rental_booking=self.rental_booking).exclude(pk=self.pk).exists():
                raise ValidationError('You have already submitted a review for this rental booking.')

        if self.borrow_request_id and self.reviewer_id:
            if Review.objects.filter(reviewer=self.reviewer, borrow_request=self.borrow_request).exclude(pk=self.pk).exists():
                raise ValidationError('You have already submitted a review for this borrow request.')

        if self.sales_order_id and self.reviewer_id:
            if Review.objects.filter(reviewer=self.reviewer, sales_order=self.sales_order).exclude(pk=self.pk).exists():
                raise ValidationError('You have already submitted a review for this order.')

    def __str__(self):
        return f"{self.rating}★ by {self.reviewer.username} for {self.listing.title}"
