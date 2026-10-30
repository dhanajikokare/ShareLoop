from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from listings.models import Category, Listing
from core.models import Notification


def home_view(request):
    """
    ShareLoop Home Page:
    - Hero with Pune search bar (keywords, category, locality, mode)
    - Categories grid
    - Featured real listings from database
    - How it works summary
    - Trust & safety guarantee
    """
    categories = Category.objects.filter(is_active=True).order_by('display_order', 'name')

    # Real database listings
    base_listings = Listing.objects.filter(
        status='ACTIVE',
        moderation_status='APPROVED'
    ).select_related('owner', 'category').prefetch_related('images')

    featured_rentals = base_listings.filter(can_rent=True)[:4]
    featured_borrows = base_listings.filter(can_borrow=True)[:4]
    featured_sales = base_listings.filter(can_sell=True)[:4]
    recent_listings = base_listings.order_by('-created_at')[:8]

    context = {
        'categories': categories,
        'featured_rentals': featured_rentals,
        'featured_borrows': featured_borrows,
        'featured_sales': featured_sales,
        'recent_listings': recent_listings,
    }
    return render(request, 'core/home.html', context)


def how_it_works_view(request):
    """
    Transparent explanation of all 3 marketplace modes: Rent, Borrow, and Sell.
    """
    return render(request, 'core/how_it_works.html')


def safety_view(request):
    """
    Trust and Safety Guidelines, Handover Evidence explanation, and fraud prevention.
    """
    return render(request, 'core/safety.html')


def terms_view(request):
    """
    Platform Terms and Conditions.
    """
    return render(request, 'core/terms.html')


def privacy_view(request):
    """
    User Privacy Policy and Data Handling.
    """
    return render(request, 'core/privacy.html')


def contact_view(request):
    """
    Contact & Community Support.
    """
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        subject = request.POST.get('subject', '').strip()
        message = request.POST.get('message', '').strip()

        if name and email and message:
            messages.success(request, f"Thank you, {name}! Your message has been received. Our Pune support team will get back to you at {email}.")
            return redirect('core:contact')
        else:
            messages.error(request, "Please fill out all required fields.")

    return render(request, 'core/contact.html')


@login_required
def notifications_view(request):
    """
    In-app user notifications dashboard.
    """
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'core/notifications.html', {'notifications': notifications})


@login_required
def mark_notification_read(request, pk):
    """
    Mark single notification as read and redirect to link.
    """
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.is_read = True
    notification.save()

    if notification.link_url:
        return redirect(notification.link_url)
    return redirect('core:notifications')


@login_required
def mark_all_notifications_read(request):
    """
    Mark all user's notifications as read.
    """
    if request.method == 'POST':
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        messages.success(request, "All notifications marked as read.")
    return redirect('core:notifications')
