from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    path('buy/<int:listing_id>/', views.create_order_view, name='create_order'),
    path('my-orders/', views.my_orders_view, name='my_orders'),
    path('order/<int:pk>/', views.order_detail_view, name='order_detail'),
    path('order/<int:pk>/status/', views.update_order_status_view, name='update_status'),
]
