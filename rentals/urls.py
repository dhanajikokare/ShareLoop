from django.urls import path
from . import views

app_name = 'rentals'

urlpatterns = [
    path('request/<int:listing_id>/', views.create_booking_view, name='create_booking'),
    path('my-rentals/', views.my_rentals_view, name='my_rentals'),
    path('incoming/', views.incoming_rentals_view, name='incoming_rentals'),
    path('booking/<int:pk>/', views.rental_detail_view, name='rental_detail'),
    path('booking/<int:pk>/accept/', views.accept_rental_view, name='accept_rental'),
    path('booking/<int:pk>/reject/', views.reject_rental_view, name='reject_rental'),
    path('booking/<int:pk>/handover/', views.mark_rental_active_view, name='mark_active'),
    path('booking/<int:pk>/complete/', views.mark_rental_completed_view, name='mark_completed'),
]
