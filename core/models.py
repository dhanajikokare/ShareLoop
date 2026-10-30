from django.conf import settings
from django.db import models


class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('RENTAL_REQUEST', 'Rental Request'),
        ('RENTAL_STATUS', 'Rental Status Update'),
        ('BORROW_REQUEST', 'Borrow Request'),
        ('BORROW_STATUS', 'Borrow Status Update'),
        ('ORDER_PLACED', 'Order Placed'),
        ('ORDER_STATUS', 'Order Status Update'),
        ('PAYMENT', 'Payment Update'),
        ('REVIEW', 'New Review'),
        ('REPORT', 'Report Update'),
        ('SYSTEM', 'System Announcement'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=150)
    message = models.TextField()
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES, default='SYSTEM')
    link_url = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification for {self.user.username}: {self.title}"


class PlatformSetting(models.Model):
    key = models.CharField(max_length=50, unique=True)
    value = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.key} = {self.value}"

    @classmethod
    def get_setting(cls, key, default=''):
        try:
            return cls.objects.get(key=key).value
        except cls.DoesNotExist:
            return default
