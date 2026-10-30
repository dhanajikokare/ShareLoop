from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from .forms import HandoverLogForm, ReviewForm
from .models import HandoverLog, Review
from rentals.models import RentalBooking
from borrowing.models import BorrowRequest
from orders.models import SalesOrder
from core.models import Notification


@login_required
def evidence_list_view(request):
    """
    List of all handover and return logs for transactions the current user was involved in.
    """
    user = request.user
    logs = HandoverLog.objects.filter(
        Q(recorded_by=user) |
        Q(rental_booking__renter=user) |
        Q(rental_booking__listing__owner=user) |
        Q(borrow_request__borrower=user) |
        Q(borrow_request__listing__owner=user) |
        Q(sales_order__buyer=user) |
        Q(sales_order__seller=user)
    ).distinct().order_by('-timestamp')

    return render(request, 'reviews/evidence_list.html', {'logs': logs})


@login_required
def add_evidence_view(request):
    """
    Record handover or return condition and photograph.
    Enforces strict access control: only authorized transaction participants can attach evidence.
    """
    booking_id = request.GET.get('booking_id') or request.POST.get('booking_id') or request.POST.get('rental_booking')
    borrow_id = request.GET.get('borrow_id') or request.POST.get('borrow_id') or request.POST.get('borrow_request')
    order_id = request.GET.get('order_id') or request.POST.get('order_id') or request.POST.get('sales_order')

    booking = None
    borrow_req = None
    order = None

    if booking_id:
        booking = get_object_or_404(RentalBooking, pk=booking_id)
        if request.user not in (booking.renter, booking.listing.owner) and not request.user.is_staff:
            messages.error(request, "You are not authorized to log evidence for this rental.")
            return redirect('accounts:dashboard')

    elif borrow_id:
        borrow_req = get_object_or_404(BorrowRequest, pk=borrow_id)
        if request.user not in (borrow_req.borrower, borrow_req.listing.owner) and not request.user.is_staff:
            messages.error(request, "You are not authorized to log evidence for this borrow request.")
            return redirect('accounts:dashboard')

    elif order_id:
        order = get_object_or_404(SalesOrder, pk=order_id)
        if request.user not in (order.buyer, order.seller) and not request.user.is_staff:
            messages.error(request, "You are not authorized to log evidence for this order.")
            return redirect('accounts:dashboard')
    else:
        messages.error(request, "No transaction specified.")
        return redirect('accounts:dashboard')

    if request.method == 'POST':
        form = HandoverLogForm(request.POST, request.FILES)
        if form.is_valid():
            log = form.save(commit=False)
            log.recorded_by = request.user
            if booking:
                log.rental_booking = booking
            elif borrow_req:
                log.borrow_request = borrow_req
            elif order:
                log.sales_order = order
            log.save()

            messages.success(request, "Handover condition log and photo recorded securely.")
            if booking:
                return redirect('rentals:rental_detail', pk=booking.id)
            elif borrow_req:
                return redirect('borrowing:borrow_detail', pk=borrow_req.id)
            elif order:
                return redirect('orders:order_detail', pk=order.id)
    else:
        # Prepopulate appropriate default log_type
        initial = {}
        if booking:
            initial['log_type'] = 'RENTAL_HANDOVER' if booking.status in ('ACCEPTED', 'CONFIRMED') else 'RENTAL_RETURN'
        elif borrow_req:
            initial['log_type'] = 'BORROW_HANDOVER' if borrow_req.status == 'ACCEPTED' else 'BORROW_RETURN'
        elif order:
            initial['log_type'] = 'SALE_HANDOVER'
        form = HandoverLogForm(initial=initial)

    context = {
        'form': form,
        'booking': booking,
        'borrow_req': borrow_req,
        'order': order,
    }
    return render(request, 'reviews/add_evidence.html', context)


@login_required
def create_review_view(request):
    """
    Submit a review for a completed transaction. Prevents duplicate reviews.
    """
    tx_type = request.GET.get('type') or request.POST.get('type')
    tx_id = request.GET.get('id') or request.POST.get('id')

    booking = None
    borrow_req = None
    order = None
    reviewee = None
    listing = None

    if tx_type == 'RENTAL':
        booking = get_object_or_404(RentalBooking, pk=tx_id, status='COMPLETED')
        if request.user == booking.renter:
            reviewee = booking.listing.owner
        elif request.user == booking.listing.owner:
            reviewee = booking.renter
        else:
            messages.error(request, "You were not a participant in this rental.")
            return redirect('accounts:dashboard')
        listing = booking.listing

    elif tx_type == 'BORROW':
        borrow_req = get_object_or_404(BorrowRequest, pk=tx_id, status='COMPLETED')
        if request.user == borrow_req.borrower:
            reviewee = borrow_req.listing.owner
        elif request.user == borrow_req.listing.owner:
            reviewee = borrow_req.borrower
        else:
            messages.error(request, "You were not a participant in this borrow transaction.")
            return redirect('accounts:dashboard')
        listing = borrow_req.listing

    elif tx_type == 'SALE':
        order = get_object_or_404(SalesOrder, pk=tx_id, status='COMPLETED')
        if request.user == order.buyer:
            reviewee = order.seller
        elif request.user == order.seller:
            reviewee = order.buyer
        else:
            messages.error(request, "You were not a participant in this purchase.")
            return redirect('accounts:dashboard')
        first_item = order.items.first()
        listing = first_item.listing if first_item else None
    else:
        messages.error(request, "Invalid transaction type.")
        return redirect('accounts:dashboard')

    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.reviewer = request.user
            review.reviewee = reviewee
            review.listing = listing
            review.transaction_type = tx_type
            review.rental_booking = booking
            review.borrow_request = borrow_req
            review.sales_order = order

            try:
                review.full_clean()
                review.save()

                Notification.objects.create(
                    user=reviewee,
                    title=f"New Review Received ({review.rating}★)",
                    message=f"{request.user.display_name} wrote a review for your transaction on '{listing.title}'.",
                    notification_type='REVIEW',
                    link_url=f"/accounts/user/{reviewee.username}/",
                )

                messages.success(request, "Your review has been published. Thank you for building community trust!")
                return redirect('accounts:public_profile', username=reviewee.username)
            except ValidationError as e:
                messages.error(request, str(e.messages[0] if hasattr(e, 'messages') else e))
    else:
        form = ReviewForm()

    context = {
        'form': form,
        'tx_type': tx_type,
        'tx_id': tx_id,
        'reviewee': reviewee,
        'listing': listing,
    }
    return render(request, 'reviews/create_review.html', context)
