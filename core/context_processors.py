from django.conf import settings
from listings.models import Category
from core.models import Notification


PUNE_LOCALITIES = [
    'Kothrud',
    'Baner',
    'Hinjewadi',
    'Viman Nagar',
    'Koregaon Park',
    'Wakad',
    'Aundh',
    'Hadapsar',
    'Shivaji Nagar',
    'Magarpatta',
    'Kalyani Nagar',
    'Pimpri-Chinchwad',
    'Bavdhan',
    'Camp',
    'Swargate',
    'Senapati Bapat Road',
    'Karve Nagar',
    'Deccan Gymkhana',
]


def shareloop_context(request):
    unread_count = 0
    if request.user.is_authenticated:
        unread_count = Notification.objects.filter(user=request.user, is_read=False).count()

    # Cached or fast fetched active categories
    categories = Category.objects.filter(is_active=True).order_by('display_order', 'name')

    return {
        'SITE_NAME': 'ShareLoop',
        'SITE_TAGLINE': 'Rent it. Borrow it. Sell it.',
        'DEFAULT_CITY': getattr(settings, 'DEFAULT_CITY', 'Pune'),
        'DEFAULT_STATE': getattr(settings, 'DEFAULT_STATE', 'Maharashtra'),
        'PLATFORM_COMMISSION_PERCENTAGE': getattr(settings, 'PLATFORM_COMMISSION_PERCENTAGE', 5.0),
        'PUNE_LOCALITIES': PUNE_LOCALITIES,
        'global_categories': categories,
        'unread_notifications_count': unread_count,
    }
