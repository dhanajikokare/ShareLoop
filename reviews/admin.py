from django.contrib import admin
from .models import HandoverLog, Review


@admin.register(HandoverLog)
class HandoverLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'log_type', 'recorded_by', 'item_condition', 'timestamp')
    list_filter = ('log_type', 'item_condition', 'timestamp')
    search_fields = ('recorded_by__username', 'notes')
    readonly_fields = ('timestamp',)


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'reviewer', 'reviewee', 'listing', 'transaction_type', 'rating', 'moderation_status', 'created_at')
    list_filter = ('rating', 'transaction_type', 'moderation_status', 'created_at')
    search_fields = ('reviewer__username', 'reviewee__username', 'listing__title', 'comment')
    actions = ['publish_reviews', 'hide_reviews']

    @admin.action(description='Publish selected reviews')
    def publish_reviews(self, request, queryset):
        queryset.update(moderation_status='PUBLISHED')

    @admin.action(description='Hide selected reviews')
    def hide_reviews(self, request, queryset):
        queryset.update(moderation_status='HIDDEN')
