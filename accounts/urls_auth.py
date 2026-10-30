from django.urls import path
from . import views

urlpatterns = [
    path('register/send-email-otp', views.register_send_email_otp, name='auth_register_send_email_otp'),
    path('register/send-email-otp/', views.register_send_email_otp),
    path('register/verify-email-otp', views.register_verify_email_otp, name='auth_register_verify_email_otp'),
    path('register/verify-email-otp/', views.register_verify_email_otp),
    path('register', views.register_view, name='auth_register'),
    path('register/', views.register_view),
    path('forgot-password/email', views.auth_forgot_password_email, name='auth_forgot_password_email'),
    path('forgot-password/email/', views.auth_forgot_password_email),
    path('forgot-password/phone', views.auth_forgot_password_phone, name='auth_forgot_password_phone'),
    path('forgot-password/phone/', views.auth_forgot_password_phone),
    path('forgot-password/verify-otp', views.forgot_password_verify_otp, name='auth_forgot_password_verify_otp'),
    path('forgot-password/verify-otp/', views.forgot_password_verify_otp),
    path('reset-password', views.reset_password_view, name='auth_reset_password'),
    path('reset-password/', views.reset_password_view),
]
