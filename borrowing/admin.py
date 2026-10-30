from django.contrib import admin
from .models import BorrowRequest


@admin.register(BorrowRequest)
class BorrowRequestAdmin(admin.ModelAdmin):
    list_display = (
        'request_reference', 'listing', 'borrower', 'start_date', 'end_date',
        'total_days', 'is_free', 'security_deposit', 'status', 'created_at'
    )
    list_filter = ('status', 'is_free', 'start_date', 'end_date', 'created_at')
    search_fields = ('request_reference', 'listing__title', 'borrower__username', 'borrower_message')
    readonly_fields = ('request_reference', 'is_free', 'created_at', 'updated_at')
