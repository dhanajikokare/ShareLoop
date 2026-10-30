from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    path('checkout/rental/<int:booking_id>/', views.checkout_rental_view, name='checkout_rental'),
    path('verify/', views.verify_payment_view, name='verify_payment'),
    path('webhook/razorpay/', views.razorpay_webhook_view, name='razorpay_webhook'),
]
