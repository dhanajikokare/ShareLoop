from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class User(AbstractUser):
    USER_TYPE_CHOICES = [
        ('INDIVIDUAL', 'Individual User'),
        ('BUSINESS', 'Business Seller'),
    ]

    user_type = models.CharField(
        max_length=20,
        choices=USER_TYPE_CHOICES,
        default='INDIVIDUAL',
        help_text='Account type: Individual or Business shop',
    )
    phone_number = models.CharField(max_length=15, blank=True, help_text='Contact phone number')
    is_verified = models.BooleanField(
        default=False,
        help_text='Indicates if identity or shop verification has been completed by admin',
    )
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    bio = models.TextField(blank=True, max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def is_business_seller(self):
        return self.user_type == 'BUSINESS'

    @property
    def display_name(self):
        if self.is_business_seller and hasattr(self, 'profile') and self.profile.shop_name:
            return self.profile.shop_name
        full_name = self.get_full_name()
        return full_name if full_name else self.username

    def __str__(self):
        return f"{self.username} ({self.get_user_type_display()})"


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    shop_name = models.CharField(max_length=150, blank=True)
    shop_description = models.TextField(blank=True)
    business_registration_number = models.CharField(max_length=50, blank=True)
    gst_number = models.CharField(max_length=20, blank=True)
    alternate_phone = models.CharField(max_length=15, blank=True)
    emergency_contact = models.CharField(max_length=100, blank=True)
    preferred_language = models.CharField(max_length=10, default='en')

    def __str__(self):
        return f"Profile for {self.user.username}"


class Address(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses')
    full_name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=15)
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True)
    locality = models.CharField(max_length=100, help_text='Pune locality (e.g. Kothrud, Baner, Hinjewadi)')
    city = models.CharField(max_length=100, default='Pune')
    state = models.CharField(max_length=100, default='Maharashtra')
    pincode = models.CharField(max_length=10)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Addresses'
        ordering = ['-is_default', '-created_at']

    def save(self, *args, **kwargs):
        if self.is_default:
            # Set all other addresses for this user to is_default=False
            Address.objects.filter(user=self.user, is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.address_line1}, {self.locality}, {self.city} - {self.pincode}"


class AuditLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    action = models.CharField(max_length=100)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    details = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        username = self.user.username if self.user else 'System'
        return f"[{self.timestamp:%Y-%m-%d %H:%M}] {username}: {self.action}"


@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
    else:
        if hasattr(instance, 'profile'):
            instance.profile.save()


import hashlib
import secrets
from datetime import timedelta
from django.conf import settings
from django.utils import timezone


class OTPVerification(models.Model):
    PURPOSE_REGISTRATION_EMAIL = 'REGISTRATION_EMAIL'
    PURPOSE_PASSWORD_RESET_EMAIL = 'PASSWORD_RESET_EMAIL'
    PURPOSE_PASSWORD_RESET_PHONE = 'PASSWORD_RESET_PHONE'

    PURPOSE_CHOICES = [
        (PURPOSE_REGISTRATION_EMAIL, 'Registration Email Verification'),
        (PURPOSE_PASSWORD_RESET_EMAIL, 'Password Reset via Email'),
        (PURPOSE_PASSWORD_RESET_PHONE, 'Password Reset via Phone'),
    ]

    purpose = models.CharField(max_length=30, choices=PURPOSE_CHOICES)
    identifier = models.CharField(max_length=150, db_index=True)
    otp_hash = models.CharField(max_length=128)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='otp_verifications')

    attempts = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=5)

    is_verified = models.BooleanField(default=False)
    is_used = models.BooleanField(default=False)

    reset_token = models.CharField(max_length=64, blank=True, null=True, unique=True, db_index=True)
    reset_token_expires_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    last_sent_at = models.DateTimeField(default=timezone.now)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['identifier', 'purpose']),
            models.Index(fields=['reset_token']),
        ]

    def set_otp(self, plain_otp):
        salt = settings.SECRET_KEY
        self.otp_hash = hashlib.sha256(f"{plain_otp}:{salt}".encode('utf-8')).hexdigest()

    def check_otp(self, plain_otp):
        salt = settings.SECRET_KEY
        expected = hashlib.sha256(f"{plain_otp}:{salt}".encode('utf-8')).hexdigest()
        return secrets.compare_digest(self.otp_hash, expected)

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    def cooldown_remaining(self):
        elapsed = (timezone.now() - self.last_sent_at).total_seconds()
        remaining = 60 - int(elapsed)
        return max(0, remaining)

    def issue_reset_token(self):
        self.reset_token = secrets.token_urlsafe(32)
        self.reset_token_expires_at = timezone.now() + timedelta(minutes=10)
        self.save(update_fields=['reset_token', 'reset_token_expires_at'])
        return self.reset_token

    def __str__(self):
        return f"{self.purpose} for {self.identifier} (verified={self.is_verified})"

