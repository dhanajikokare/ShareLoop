from django.contrib import admin
from .models import Category, Listing, ListingImage, ListingReport


class ListingImageInline(admin.TabularInline):
    model = ListingImage
    extra = 1


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'icon_class', 'display_order', 'is_active')
    list_editable = ('display_order', 'is_active')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name', 'description')


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    inlines = [ListingImageInline]
    list_display = (
        'title', 'owner', 'category', 'locality', 'item_condition',
        'can_rent', 'can_borrow', 'can_sell', 'status', 'moderation_status', 'created_at'
    )
    list_filter = (
        'status', 'moderation_status', 'category', 'locality',
        'can_rent', 'can_borrow', 'can_sell', 'item_condition'
    )
    search_fields = ('title', 'description', 'owner__username', 'locality')
    actions = ['approve_listings', 'flag_listings', 'activate_listings', 'deactivate_listings']

    @admin.action(description='Approve selected listings')
    def approve_listings(self, request, queryset):
        queryset.update(moderation_status='APPROVED')

    @admin.action(description='Flag selected listings for review')
    def flag_listings(self, request, queryset):
        queryset.update(moderation_status='FLAGGED')

    @admin.action(description='Activate selected listings')
    def activate_listings(self, request, queryset):
        queryset.update(status='ACTIVE')

    @admin.action(description='Deactivate / Pause selected listings')
    def deactivate_listings(self, request, queryset):
        queryset.update(status='INACTIVE')


@admin.register(ListingReport)
class ListingReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'listing', 'reporter', 'reason', 'status', 'created_at')
    list_filter = ('status', 'reason', 'created_at')
    search_fields = ('listing__title', 'reporter__username', 'description', 'admin_notes')
    actions = ['mark_resolved', 'dismiss_reports']

    @admin.action(description='Mark selected reports as Resolved')
    def mark_resolved(self, request, queryset):
        queryset.update(status='RESOLVED')

    @admin.action(description='Dismiss selected reports')
    def dismiss_reports(self, request, queryset):
        queryset.update(status='DISMISSED')
