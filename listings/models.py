from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True)
    icon_class = models.CharField(
        max_length=50,
        default='bi-box-seam',
        help_text='Bootstrap icon class name, e.g. bi-camera, bi-laptop, bi-tools',
    )
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['display_order', 'name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Listing(models.Model):
    CONDITION_CHOICES = [
        ('NEW', 'Brand New'),
        ('LIKE_NEW', 'Like New'),
        ('GOOD', 'Good Condition'),
        ('FAIR', 'Fair / Functional'),
    ]

    STATUS_CHOICES = [
        ('ACTIVE', 'Active / Available'),
        ('INACTIVE', 'Paused / Inactive'),
        ('SOLD', 'Sold Out'),
        ('SUSPENDED', 'Suspended by Moderator'),
    ]

    MODERATION_CHOICES = [
        ('APPROVED', 'Approved'),
        ('PENDING', 'Under Review'),
        ('FLAGGED', 'Flagged for Review'),
    ]

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='listings')
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='listings')
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, blank=True)
    description = models.TextField()
    item_condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default='GOOD')

    # Location
    city = models.CharField(max_length=100, default='Pune')
    locality = models.CharField(max_length=100, help_text='Locality in Pune (e.g., Kothrud, Baner, Viman Nagar)')
    pincode = models.CharField(max_length=10)
    pickup_available = models.BooleanField(default=True)
    delivery_available = models.BooleanField(default=False)

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    moderation_status = models.CharField(max_length=20, choices=MODERATION_CHOICES, default='APPROVED')

    # Listing Modes
    can_rent = models.BooleanField(default=False, help_text='Available to Rent for a daily/weekly fee')
    can_borrow = models.BooleanField(default=False, help_text='Available to Borrow for FREE')
    can_sell = models.BooleanField(default=False, help_text='Available to Buy/Purchase')

    # Rent Mode Fields
    rent_price_per_day = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    rent_price_per_week = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    rent_security_deposit = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), blank=True)
    min_rental_days = models.PositiveIntegerField(default=1)
    max_rental_days = models.PositiveIntegerField(default=30)
    rental_cancellation_policy = models.TextField(blank=True, default='Free cancellation up to 24 hours before pickup.')

    # Borrow Mode Fields
    is_free_borrow = models.BooleanField(default=True, help_text='Borrowing is always free of rental charges')
    borrow_security_deposit = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        blank=True,
        help_text='Optional refundable deposit only when strictly disclosed and approved',
    )
    borrow_max_days = models.PositiveIntegerField(default=7)
    borrow_return_conditions = models.TextField(
        blank=True,
        default='Please return the item in the same clean and functional condition as received.',
    )

    # Sell Mode Fields
    sell_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    sell_price_negotiable = models.BooleanField(default=False)
    quantity = models.PositiveIntegerField(default=1, help_text='Available physical quantity')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def clean(self):
        super().clean()
        if not (self.can_rent or self.can_borrow or self.can_sell):
            raise ValidationError('At least one listing mode (Rent, Borrow, or Sell) must be enabled.')

        if self.can_rent:
            if not self.rent_price_per_day or self.rent_price_per_day <= 0:
                raise ValidationError({'rent_price_per_day': 'Please specify a positive daily rental price.'})
            if self.rent_security_deposit is not None and self.rent_security_deposit < 0:
                raise ValidationError({'rent_security_deposit': 'Security deposit cannot be negative.'})

        if self.can_sell:
            if not self.sell_price or self.sell_price <= 0:
                raise ValidationError({'sell_price': 'Please specify a positive selling price.'})
            if self.status != 'SOLD' and self.quantity < 1:
                raise ValidationError({'quantity': 'Available quantity for sale must be at least 1.'})

        if self.can_borrow:
            if self.borrow_security_deposit is not None and self.borrow_security_deposit < 0:
                raise ValidationError({'borrow_security_deposit': 'Borrow security deposit cannot be negative.'})

    def save(self, *args, **kwargs):
        self.clean()
        if not self.slug:
            base_slug = slugify(self.title)
            # Add short unique token if needed
            self.slug = f"{base_slug[:180]}-{slugify(self.locality)[:20]}" if base_slug else "listing"
        super().save(*args, **kwargs)

    @property
    def primary_image(self):
        primary = self.images.filter(is_primary=True).first()
        if not primary:
            primary = self.images.first()
        return primary

    @property
    def primary_image_url(self):
        img = self.primary_image
        if img and img.image:
            try:
                return img.image.url
            except Exception:
                pass
        return None

    @property
    def available_modes_display(self):
        modes = []
        if self.can_rent:
            modes.append('Rent')
        if self.can_borrow:
            modes.append('Borrow')
        if self.can_sell:
            modes.append('Sell')
        return modes

    def is_available_for_dates(self, start_date, end_date, exclude_rental_id=None, exclude_borrow_id=None):
        """
        Validates that the physical item is not already booked or borrowed for overlapping dates.
        """
        # Check active or confirmed rental bookings
        active_rentals = self.rental_bookings.filter(
            status__in=['ACCEPTED', 'PAYMENT_PENDING', 'CONFIRMED', 'ACTIVE'],
            start_date__lte=end_date,
            end_date__gte=start_date,
        )
        if exclude_rental_id:
            active_rentals = active_rentals.exclude(pk=exclude_rental_id)
        if active_rentals.exists():
            return False, 'Item is already booked for rent during these dates.'

        # Check active or approved borrow requests
        active_borrows = self.borrow_requests.filter(
            status__in=['ACCEPTED', 'ACTIVE'],
            start_date__lte=end_date,
            end_date__gte=start_date,
        )
        if exclude_borrow_id:
            active_borrows = active_borrows.exclude(pk=exclude_borrow_id)
        if active_borrows.exists():
            return False, 'Item is already reserved for borrowing during these dates.'

        return True, 'Item is available.'

    def __str__(self):
        return f"{self.title} ({self.locality}, {self.city})"


class ListingImage(models.Model):
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='listings/%Y/%m/')
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_primary', 'created_at']

    def save(self, *args, **kwargs):
        if self.is_primary:
            # Unset is_primary on other images of the same listing
            ListingImage.objects.filter(listing=self.listing, is_primary=True).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Image for {self.listing.title}"


class ListingReport(models.Model):
    REPORT_REASONS = [
        ('FRAUD', 'Suspected Fraud or Scam'),
        ('FAKE', 'Counterfeit / Fake Product'),
        ('MISLEADING', 'Inaccurate or Misleading Description'),
        ('INAPPROPRIATE', 'Inappropriate or Prohibited Content'),
        ('DAMAGE_DISPUTE', 'Damage or Non-Return Dispute'),
        ('OTHER', 'Other Violation'),
    ]

    STATUS_CHOICES = [
        ('PENDING', 'Pending Admin Review'),
        ('REVIEWED', 'Under Investigation'),
        ('RESOLVED', 'Resolved / Action Taken'),
        ('DISMISSED', 'Dismissed'),
    ]

    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='reports')
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='submitted_reports')
    reason = models.CharField(max_length=30, choices=REPORT_REASONS)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    admin_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Report #{self.id} on {self.listing.title} ({self.get_reason_display()})"
