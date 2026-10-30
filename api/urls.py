from django.urls import path
from . import views

app_name = "api"

urlpatterns = [
    # Auth
    path("auth/login/", views.api_login, name="login"),
    path("auth/register/", views.api_register, name="register"),
    path("auth/register/send-otp/", views.api_register_send_email_otp, name="register_send_otp"),
    path("auth/register/verify-otp/", views.api_register_verify_email_otp, name="register_verify_otp"),
    path("auth/forgot-password/email/", views.api_forgot_password_email, name="forgot_password_email"),
    path("auth/forgot-password/phone/", views.api_forgot_password_phone, name="forgot_password_phone"),
    path("auth/forgot-password/verify-otp/", views.api_forgot_password_verify_otp, name="forgot_password_verify_otp"),
    path("auth/reset-password/", views.api_reset_password, name="reset_password"),
    path("auth/me/", views.api_me, name="me"),
    path("auth/addresses/", views.api_addresses, name="addresses"),

    # Categories & Listings
    path("categories/", views.api_categories, name="categories"),
    path("listings/", views.api_listings, name="listings"),
    path("listings/<int:pk>/", views.api_listing_detail, name="listing_detail"),
    path("listings/create/", views.api_listing_create, name="listing_create"),
    path("listings/my/", views.api_my_listings, name="my_listings"),

    # Rentals
    path("rentals/book/", views.api_rental_create, name="rental_book"),
    path("rentals/my/", views.api_my_rentals, name="my_rentals"),
    path("rentals/<int:pk>/action/", views.api_rental_action, name="rental_action"),

    # Borrowing
    path("borrowing/request/", views.api_borrow_create, name="borrow_request"),
    path("borrowing/my/", views.api_my_borrows, name="my_borrows"),

    # Orders (Buy/Sell)
    path("orders/create/", views.api_order_create, name="order_create"),
    path("orders/my/", views.api_my_orders, name="my_orders"),

    # Chats
    path("chats/", views.api_conversations, name="conversations"),
    path("chats/<int:pk>/messages/", views.api_conversation_messages, name="conversation_messages"),

    # Favorites
    path("favorites/", views.api_favorites, name="favorites"),

    # Notifications
    path("notifications/", views.api_notifications, name="notifications"),
    path("notifications/<int:pk>/read/", views.api_notification_read, name="notification_read"),
]
