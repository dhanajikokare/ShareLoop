from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from .forms import ListingForm, ListingReportForm
from .models import Category, Listing, ListingImage, ListingReport
from core.models import Notification


def browse_view(request):
    """
    Search and filter products across Pune.
    Supports keywords, categories, Pune localities, modes (Rent/Borrow/Sell), price ranges, and sorting.
    """
    listings = Listing.objects.filter(
        status='ACTIVE',
        moderation_status='APPROVED'
    ).select_related('owner', 'category').prefetch_related('images')

    # 1. Keyword search (Title & Description)
    q = request.GET.get('q', '').strip()
    if q:
        listings = listings.filter(Q(title__icontains=q) | Q(description__icontains=q))

    # 2. Category filter
    category_slug = request.GET.get('category', '').strip()
    selected_category = None
    if category_slug:
        listings = listings.filter(category__slug=category_slug)
        selected_category = Category.objects.filter(slug=category_slug).first()

    # 3. Mode filter (Rent / Borrow / Sell)
    mode = request.GET.get('mode', '').strip().lower()
    if mode == 'rent':
        listings = listings.filter(can_rent=True)
    elif mode == 'borrow':
        listings = listings.filter(can_borrow=True)
    elif mode == 'sell':
        listings = listings.filter(can_sell=True)

    # 4. Locality filter
    locality = request.GET.get('locality', '').strip()
    if locality:
        listings = listings.filter(locality__iexact=locality)

    # 5. Condition filter
    condition = request.GET.get('condition', '').strip()
    if condition:
        listings = listings.filter(item_condition=condition)

    # 6. Seller Type filter
    seller_type = request.GET.get('seller_type', '').strip().upper()
    if seller_type in ('INDIVIDUAL', 'BUSINESS'):
        listings = listings.filter(owner__user_type=seller_type)

    # 7. Price Filters
    min_price = request.GET.get('min_price', '').strip()
    max_price = request.GET.get('max_price', '').strip()
    try:
        if min_price:
            listings = listings.filter(
                Q(rent_price_per_day__gte=Decimal(min_price)) |
                Q(sell_price__gte=Decimal(min_price))
            )
        if max_price:
            listings = listings.filter(
                Q(rent_price_per_day__lte=Decimal(max_price)) |
                Q(sell_price__lte=Decimal(max_price))
            )
    except Exception:
        pass

    # 8. Sorting
    sort = request.GET.get('sort', 'newest')
    if sort == 'price_asc':
        listings = listings.order_by('rent_price_per_day', 'sell_price')
    elif sort == 'price_desc':
        listings = listings.order_by('-rent_price_per_day', '-sell_price')
    else:
        listings = listings.order_by('-created_at')

    # Pagination: 12 per page
    paginator = Paginator(listings, 12)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # Preserve GET parameters across pagination links
    query_params = request.GET.copy()
    if 'page' in query_params:
        query_params.pop('page')
    querystring = query_params.urlencode()

    categories = Category.objects.filter(is_active=True).order_by('name')

    context = {
        'page_obj': page_obj,
        'total_results': paginator.count,
        'categories': categories,
        'selected_category': selected_category,
        'current_mode': mode,
        'current_locality': locality,
        'current_condition': condition,
        'current_seller_type': seller_type,
        'current_sort': sort,
        'q': q,
        'querystring': querystring,
    }
    return render(request, 'listings/browse.html', context)


def detail_view(request, pk, slug):
    """
    Detailed product listing view with interactive booking, borrowing, and purchasing forms.
    """
    listing = get_object_or_404(
        Listing.objects.select_related('owner', 'category').prefetch_related('images'),
        pk=pk
    )

    # Reviews received for this listing
    reviews = listing.reviews.filter(moderation_status='PUBLISHED').order_by('-created_at')

    # Related items in same locality or category
    related_listings = Listing.objects.filter(
        status='ACTIVE',
        moderation_status='APPROVED'
    ).exclude(pk=listing.pk).filter(
        Q(category=listing.category) | Q(locality=listing.locality)
    )[:4]

    report_form = ListingReportForm()

    context = {
        'listing': listing,
        'reviews': reviews,
        'related_listings': related_listings,
        'report_form': report_form,
        'is_owner': request.user.is_authenticated and request.user.id == listing.owner_id,
    }
    return render(request, 'listings/detail.html', context)


@login_required
def create_listing_view(request):
    """
    Create a new listing with images and support for multiple modes (Rent, Borrow, Sell).
    """
    if request.method == 'POST':
        form = ListingForm(request.POST, request.FILES)
        if form.is_valid():
            listing = form.save(commit=False)
            listing.owner = request.user
            listing.status = 'ACTIVE'
            listing.moderation_status = 'APPROVED'
            listing.save()

            # Handle primary image upload
            primary_img = form.cleaned_data.get('primary_image')
            if primary_img:
                ListingImage.objects.create(listing=listing, image=primary_img, is_primary=True)

            messages.success(request, f"Your listing '{listing.title}' is now live in Pune!")
            return redirect('listings:detail', pk=listing.id, slug=listing.slug)
    else:
        # Prepopulate locality if user has a default address
        initial_data = {}
        default_addr = request.user.addresses.filter(is_default=True).first()
        if default_addr:
            initial_data['locality'] = default_addr.locality
            initial_data['pincode'] = default_addr.pincode
        form = ListingForm(initial=initial_data)

    return render(request, 'listings/form.html', {'form': form, 'is_edit': False})


@login_required
def edit_listing_view(request, pk):
    """
    Edit an existing listing. Ownership checked on the server side.
    """
    listing = get_object_or_404(Listing, pk=pk)
    if listing.owner != request.user and not request.user.is_staff:
        messages.error(request, "You are not authorized to edit this listing.")
        return redirect('listings:browse')

    if request.method == 'POST':
        form = ListingForm(request.POST, request.FILES, instance=listing)
        if form.is_valid():
            listing = form.save()
            primary_img = form.cleaned_data.get('primary_image')
            if primary_img:
                ListingImage.objects.create(listing=listing, image=primary_img, is_primary=True)

            messages.success(request, f"Listing '{listing.title}' updated successfully.")
            return redirect('listings:detail', pk=listing.id, slug=listing.slug)
    else:
        form = ListingForm(instance=listing)

    return render(request, 'listings/form.html', {'form': form, 'listing': listing, 'is_edit': True})


@login_required
def delete_listing_view(request, pk):
    """
    Delete or archive a listing safely.
    """
    listing = get_object_or_404(Listing, pk=pk)
    if listing.owner != request.user and not request.user.is_staff:
        messages.error(request, "You are not authorized to delete this listing.")
        return redirect('listings:browse')

    if request.method == 'POST':
        title = listing.title
        listing.delete()
        messages.success(request, f"Listing '{title}' has been deleted.")
    return redirect('listings:my_listings')


@login_required
def my_listings_view(request):
    """
    User's own listings management dashboard.
    """
    user_listings = Listing.objects.filter(owner=request.user).order_by('-created_at')
    return render(request, 'listings/my_listings.html', {'listings': user_listings})


@login_required
def report_listing_view(request, pk):
    """
    Report a fraudulent or problematic listing.
    """
    listing = get_object_or_404(Listing, pk=pk)
    if request.method == 'POST':
        form = ListingReportForm(request.POST)
        if form.is_valid():
            report = form.save(commit=False)
            report.listing = listing
            report.reporter = request.user
            report.save()

            messages.success(request, "Your report has been submitted for administrative review. Thank you for keeping Pune safe.")
            return redirect('listings:detail', pk=listing.id, slug=listing.slug)
    else:
        form = ListingReportForm()

    return render(request, 'listings/report.html', {'listing': listing, 'form': form})
