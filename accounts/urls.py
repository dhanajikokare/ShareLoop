from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('register/send-email-otp/', views.register_send_email_otp, name='register_send_email_otp'),
    path('register/verify-email-otp/', views.register_verify_email_otp, name='register_verify_email_otp'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('forgot-password/', views.forgot_password_view, name='forgot_password'),
    path('forgot-password/send-otp/', views.forgot_password_send_otp, name='forgot_password_send_otp'),
    path('forgot-password/verify-otp/', views.forgot_password_verify_otp, name='forgot_password_verify_otp'),
    path('reset-password/', views.reset_password_view, name='reset_password'),
    path('profile/', views.profile_view, name='profile'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('address/add/', views.address_add_view, name='address_add'),
    path('address/<int:pk>/delete/', views.address_delete_view, name='address_delete'),
    path('user/<str:username>/', views.public_profile_view, name='public_profile'),
]
