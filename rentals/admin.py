from django.contrib import admin
from .models import RentalBooking


@admin.register(RentalBooking)
class RentalBookingAdmin(admin.ModelAdmin):
    list_display = (
        'booking_reference', 'listing', 'renter', 'start_date', 'end_date',
        'total_days', 'rental_fee', 'security_deposit', 'total_amount', 'status', 'created_at'
    )
    list_filter = ('status', 'start_date', 'end_date', 'created_at')
    search_fields = ('booking_reference', 'listing__title', 'renter__username', 'renter_message')
    readonly_fields = ('booking_reference', 'created_at', 'updated_at')
