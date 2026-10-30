from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, UserProfile, Address, AuditLog


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Shop Profile'


class AddressInline(admin.TabularInline):
    model = Address
    extra = 0


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline, AddressInline)
    list_display = ('username', 'email', 'first_name', 'last_name', 'user_type', 'is_verified', 'is_staff')
    list_filter = ('user_type', 'is_verified', 'is_staff', 'is_active')
    search_fields = ('username', 'email', 'first_name', 'last_name', 'phone_number')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('ShareLoop Profile', {
            'fields': ('user_type', 'phone_number', 'is_verified', 'avatar', 'bio')
        }),
    )
    actions = ['verify_users', 'unverify_users']

    @admin.action(description='Mark selected users as Verified')
    def verify_users(self, request, queryset):
        queryset.update(is_verified=True)

    @admin.action(description='Remove verification from selected users')
    def unverify_users(self, request, queryset):
        queryset.update(is_verified=False)


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ('user', 'full_name', 'locality', 'city', 'pincode', 'is_default')
    list_filter = ('locality', 'city', 'is_default')
    search_fields = ('user__username', 'full_name', 'address_line1', 'locality', 'pincode')


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user', 'action', 'ip_address')
    list_filter = ('action', 'timestamp')
    search_fields = ('user__username', 'action', 'details', 'ip_address')
    readonly_fields = ('timestamp', 'user', 'action', 'ip_address', 'details')
