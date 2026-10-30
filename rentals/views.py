from datetime import datetime
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from .models import RentalBooking
from listings.models import Listing
from core.models import Notification


@login_required
def create_booking_view(request, listing_id):
    """
    Submits a rental booking request after strict availability & date range validation.
    """
    listing = get_object_or_404(Listing, pk=listing_id, status='ACTIVE', can_rent=True)

    if listing.owner == request.user:
        messages.error(request, "You cannot rent your own item.")
        return redirect('listings:detail', pk=listing.id, slug=listing.slug)

    if request.method == 'POST':
        start_date_str = request.POST.get('start_date')
        end_date_str = request.POST.get('end_date')
        renter_message = request.POST.get('renter_message', '').strip()

        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            messages.error(request, "Please enter valid pickup and return dates.")
            return redirect('listings:detail', pk=listing.id, slug=listing.slug)

        today = timezone.now().date()
        if start_date < today:
            messages.error(request, "Pickup date cannot be in the past.")
            return redirect('listings:detail', pk=listing.id, slug=listing.slug)

        if end_date < start_date:
            messages.error(request, "Return date must be on or after pickup date.")
            return redirect('listings:detail', pk=listing.id, slug=listing.slug)

        days = (end_date - start_date).days + 1
        if days < listing.min_rental_days:
            messages.error(request, f"Minimum rental duration for this item is {listing.min_rental_days} day(s).")
            return redirect('listings:detail', pk=listing.id, slug=listing.slug)

        if days > listing.max_rental_days:
            messages.error(request, f"Maximum rental duration for this item is {listing.max_rental_days} day(s).")
            return redirect('listings:detail', pk=listing.id, slug=listing.slug)

        # Atomic availability check
        with transaction.atomic():
            is_avail, reason = listing.is_available_for_dates(start_date, end_date)
            if not is_avail:
                messages.error(request, f"Cannot book: {reason}")
                return redirect('listings:detail', pk=listing.id, slug=listing.slug)

            cost = RentalBooking.calculate_cost(listing, start_date, end_date)

            booking = RentalBooking.objects.create(
                listing=listing,
                renter=request.user,
                start_date=start_date,
                end_date=end_date,
                total_days=cost['days'],
                daily_rate=cost['daily_rate'],
                rental_fee=cost['rental_fee'],
                security_deposit=cost['security_deposit'],
                platform_fee=cost['platform_fee'],
                total_amount=cost['total_amount'],
                renter_message=renter_message,
                status='PENDING',
            )

            # Notify the listing owner
            Notification.objects.create(
                user=listing.owner,
                title=f"New Rental Request: {listing.title}",
                message=f"{request.user.display_name} requested to rent '{listing.title}' for {days} day(s) from {start_date} to {end_date}.",
                notification_type='RENTAL_REQUEST',
                link_url=f"/rentals/booking/{booking.id}/",
            )

            messages.success(request, f"Rental booking request #{booking.booking_reference} sent to owner!")
            return redirect('rentals:rental_detail', pk=booking.id)

    return redirect('listings:detail', pk=listing.id, slug=listing.slug)


@login_required
def my_rentals_view(request):
    """
    Listings rented by the current user.
    """
    bookings = RentalBooking.objects.filter(renter=request.user).select_related('listing', 'listing__owner').order_by('-created_at')
    return render(request, 'rentals/my_rentals.html', {'bookings': bookings})


@login_required
def incoming_rentals_view(request):
    """
    Rental requests received by the owner for their listings.
    """
    bookings = RentalBooking.objects.filter(listing__owner=request.user).select_related('listing', 'renter').order_by('-created_at')
    return render(request, 'rentals/incoming_rentals.html', {'bookings': bookings})


@login_required
def rental_detail_view(request, pk):
    """
    Detailed view of a rental booking, cost breakdown, handover logs, and actions.
    """
    booking = get_object_or_404(
        RentalBooking.objects.select_related('listing', 'listing__owner', 'renter'),
        pk=pk
    )

    is_renter = request.user.id == booking.renter_id
    is_owner = request.user.id == booking.listing.owner_id
    is_staff = request.user.is_staff

    if not (is_renter or is_owner or is_staff):
        messages.error(request, "You do not have permission to view this rental booking.")
        return redirect('accounts:dashboard')

    handover_logs = booking.handover_logs.all().order_by('-timestamp')

    context = {
        'booking': booking,
        'is_renter': is_renter,
        'is_owner': is_owner,
        'handover_logs': handover_logs,
    }
    return render(request, 'rentals/rental_detail.html', context)


@login_required
def accept_rental_view(request, pk):
    """
    Owner accepts a rental booking request.
    """
    booking = get_object_or_404(RentalBooking, pk=pk)
    if booking.listing.owner != request.user and not request.user.is_staff:
        messages.error(request, "Only the listing owner can accept this request.")
        return redirect('rentals:rental_detail', pk=booking.id)

    if booking.status == 'PENDING':
        booking.status = 'ACCEPTED'
        booking.save()

        Notification.objects.create(
            user=booking.renter,
            title=f"Rental Request Accepted: {booking.listing.title}",
            message=f"The owner accepted your rental booking #{booking.booking_reference}. You can now proceed to payment and coordinate pickup.",
            notification_type='RENTAL_STATUS',
            link_url=f"/rentals/booking/{booking.id}/",
        )
        messages.success(request, f"Rental booking #{booking.booking_reference} accepted.")
    else:
        messages.warning(request, f"Booking status cannot be changed from {booking.get_status_display()}.")

    return redirect('rentals:rental_detail', pk=booking.id)


@login_required
def reject_rental_view(request, pk):
    """
    Owner rejects a rental booking request.
    """
    booking = get_object_or_404(RentalBooking, pk=pk)
    if booking.listing.owner != request.user and not request.user.is_staff:
        messages.error(request, "Only the listing owner can reject this request.")
        return redirect('rentals:rental_detail', pk=booking.id)

    if request.method == 'POST':
        reason = request.POST.get('rejection_reason', 'Item unavailable for requested dates.').strip()
        booking.status = 'REJECTED'
        booking.rejection_reason = reason
        booking.save()

        Notification.objects.create(
            user=booking.renter,
            title=f"Rental Request Declined: {booking.listing.title}",
            message=f"Your booking request was declined: {reason}",
            notification_type='RENTAL_STATUS',
            link_url=f"/rentals/booking/{booking.id}/",
        )
        messages.info(request, "Booking request rejected.")

    return redirect('rentals:rental_detail', pk=booking.id)


@login_required
def mark_rental_active_view(request, pk):
    """
    Marks that the physical item has been handed over to the renter.
    """
    booking = get_object_or_404(RentalBooking, pk=pk)
    if request.user not in (booking.listing.owner, booking.renter) and not request.user.is_staff:
        messages.error(request, "Permission denied.")
        return redirect('rentals:rental_detail', pk=booking.id)

    if booking.status in ('ACCEPTED', 'CONFIRMED'):
        booking.status = 'ACTIVE'
        booking.save()
        messages.success(request, "Rental is now ACTIVE. Please record pickup condition in the Handover Log.")
    return redirect('rentals:rental_detail', pk=booking.id)


@login_required
def mark_rental_completed_view(request, pk):
    """
    Marks that the physical item has been returned safely and rental completed.
    """
    booking = get_object_or_404(RentalBooking, pk=pk)
    if booking.listing.owner != request.user and not request.user.is_staff:
        messages.error(request, "Only the item owner can confirm safe return.")
        return redirect('rentals:rental_detail', pk=booking.id)

    if booking.status in ('ACTIVE', 'RETURN_PENDING'):
        booking.status = 'COMPLETED'
        booking.save()

        Notification.objects.create(
            user=booking.renter,
            title=f"Rental Completed: {booking.listing.title}",
            message=f"The owner confirmed return of '{booking.listing.title}'. Your deposit has been cleared. Please leave a review!",
            notification_type='RENTAL_STATUS',
            link_url=f"/rentals/booking/{booking.id}/",
        )
        messages.success(request, "Rental marked as COMPLETED. Deposit released.")
    return redirect('rentals:rental_detail', pk=booking.id)
