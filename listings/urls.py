from django.urls import path
from . import views

app_name = 'listings'

urlpatterns = [
    path('browse/', views.browse_view, name='browse'),
    path('create/', views.create_listing_view, name='create'),
    path('my-listings/', views.my_listings_view, name='my_listings'),
    path('<int:pk>-<slug:slug>/', views.detail_view, name='detail'),
    path('<int:pk>/edit/', views.edit_listing_view, name='edit'),
    path('<int:pk>/delete/', views.delete_listing_view, name='delete'),
    path('<int:pk>/report/', views.report_listing_view, name='report'),
]
