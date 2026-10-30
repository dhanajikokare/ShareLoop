from django.urls import path
from . import views

app_name = 'borrowing'

urlpatterns = [
    path('request/<int:listing_id>/', views.create_request_view, name='create_request'),
    path('my-borrows/', views.my_borrows_view, name='my_borrows'),
    path('incoming/', views.incoming_borrows_view, name='incoming_borrows'),
    path('request/<int:pk>/detail/', views.borrow_detail_view, name='borrow_detail'),
    path('request/<int:pk>/accept/', views.accept_borrow_view, name='accept_borrow'),
    path('request/<int:pk>/reject/', views.reject_borrow_view, name='reject_borrow'),
    path('request/<int:pk>/handover/', views.mark_borrow_active_view, name='mark_active'),
    path('request/<int:pk>/complete/', views.mark_borrow_completed_view, name='mark_completed'),
]
