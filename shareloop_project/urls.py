from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('accounts/', include('accounts.urls')),
    path('auth/', include('accounts.urls_auth')),
    path('listings/', include('listings.urls')),
    path('rentals/', include('rentals.urls')),
    path('borrowing/', include('borrowing.urls')),
    path('orders/', include('orders.urls')),
    path('payments/', include('payments.urls')),
    path('reviews/', include('reviews.urls')),
    path('api/v1/', include('api.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Custom Admin Branding
admin.site.site_header = "ShareLoop Administration"
admin.site.site_title = "ShareLoop Admin Portal"
admin.site.index_title = "ShareLoop Marketplace Management"
