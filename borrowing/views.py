from datetime import datetime
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from .models import BorrowRequest
from listings.models import Listing
from core.models import Notification


@login_required
def create_request_view(request, listing_id):
    """
    Submits a free borrow request. Ensures zero rental fee is charged.
    """
    listing = get_object_or_404(Listing, pk=listing_id, status='ACTIVE', can_borrow=True)

    if listing.owner == request.user:
        messages.error(request, "You cannot borrow your own item.")
        return redirect('listings:detail', pk=listing.id, slug=listing.slug)

    if request.method == 'POST':
        start_date_str = request.POST.get('start_date')
        end_date_str = request.POST.get('end_date')
        borrower_message = request.POST.get('borrower_message', '').strip()
        agreed_to_terms = request.POST.get('agreed_to_terms') == 'on'

        if not agreed_to_terms:
            messages.error(request, "You must agree to the borrowing care guidelines and return policy.")
            return redirect('listings:detail', pk=listing.id, slug=listing.slug)

        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            messages.error(request, "Please enter valid borrow dates.")
            return redirect('listings:detail', pk=listing.id, slug=listing.slug)

        today = timezone.now().date()
        if start_date < today:
            messages.error(request, "Borrow date cannot be in the past.")
            return redirect('listings:detail', pk=listing.id, slug=listing.slug)

        if end_date < start_date:
            messages.error(request, "Return date must be on or after borrow date.")
            return redirect('listings:detail', pk=listing.id, slug=listing.slug)

        days = (end_date - start_date).days + 1
        if days > listing.borrow_max_days:
            messages.error(request, f"Maximum allowed borrowing period for this item is {listing.borrow_max_days} days.")
            return redirect('listings:detail', pk=listing.id, slug=listing.slug)

        with transaction.atomic():
            is_avail, reason = listing.is_available_for_dates(start_date, end_date)
            if not is_avail:
                messages.error(request, f"Cannot borrow: {reason}")
                return redirect('listings:detail', pk=listing.id, slug=listing.slug)

            borrow_req = BorrowRequest.objects.create(
                listing=listing,
                borrower=request.user,
                start_date=start_date,
                end_date=end_date,
                total_days=days,
                is_free=True,
                security_deposit=listing.borrow_security_deposit,
                borrower_message=borrower_message,
                agreed_to_terms=True,
                status='PENDING',
            )

            # Notify owner
            Notification.objects.create(
                user=listing.owner,
                title=f"New Free Borrow Request: {listing.title}",
                message=f"{request.user.display_name} requested to borrow '{listing.title}' for {days} day(s) from {start_date} to {end_date}.",
                notification_type='BORROW_REQUEST',
                link_url=f"/borrowing/request/{borrow_req.id}/",
            )

            messages.success(request, f"Free borrow request #{borrow_req.request_reference} submitted to owner!")
            return redirect('borrowing:borrow_detail', pk=borrow_req.id)

    return redirect('listings:detail', pk=listing.id, slug=listing.slug)


@login_required
def my_borrows_view(request):
    requests = BorrowRequest.objects.filter(borrower=request.user).select_related('listing', 'listing__owner').order_by('-created_at')
    return render(request, 'borrowing/my_borrows.html', {'requests': requests})


@login_required
def incoming_borrows_view(request):
    requests = BorrowRequest.objects.filter(listing__owner=request.user).select_related('listing', 'borrower').order_by('-created_at')
    return render(request, 'borrowing/incoming_borrows.html', {'requests': requests})


@login_required
def borrow_detail_view(request, pk):
    borrow_req = get_object_or_404(
        BorrowRequest.objects.select_related('listing', 'listing__owner', 'borrower'),
        pk=pk
    )

    is_borrower = request.user.id == borrow_req.borrower_id
    is_owner = request.user.id == borrow_req.listing.owner_id
    is_staff = request.user.is_staff

    if not (is_borrower or is_owner or is_staff):
        messages.error(request, "Permission denied.")
        return redirect('accounts:dashboard')

    handover_logs = borrow_req.handover_logs.all().order_by('-timestamp')

    context = {
        'borrow_req': borrow_req,
        'is_borrower': is_borrower,
        'is_owner': is_owner,
        'handover_logs': handover_logs,
    }
    return render(request, 'borrowing/borrow_detail.html', context)


@login_required
def accept_borrow_view(request, pk):
    borrow_req = get_object_or_404(BorrowRequest, pk=pk)
    if borrow_req.listing.owner != request.user and not request.user.is_staff:
        messages.error(request, "Only the owner can accept this request.")
        return redirect('borrowing:borrow_detail', pk=borrow_req.id)

    if borrow_req.status == 'PENDING':
        borrow_req.status = 'ACCEPTED'
        borrow_req.save()

        Notification.objects.create(
            user=borrow_req.borrower,
            title=f"Borrow Request Accepted: {borrow_req.listing.title}",
            message=f"The owner approved your free loan request #{borrow_req.request_reference}. Contact them to coordinate pickup in Pune.",
            notification_type='BORROW_STATUS',
            link_url=f"/borrowing/request/{borrow_req.id}/",
        )
        messages.success(request, "Borrow request accepted.")
    return redirect('borrowing:borrow_detail', pk=borrow_req.id)


@login_required
def reject_borrow_view(request, pk):
    borrow_req = get_object_or_404(BorrowRequest, pk=pk)
    if borrow_req.listing.owner != request.user and not request.user.is_staff:
        messages.error(request, "Only the owner can decline this request.")
        return redirect('borrowing:borrow_detail', pk=borrow_req.id)

    if request.method == 'POST':
        reason = request.POST.get('rejection_reason', 'Currently unavailable.').strip()
        borrow_req.status = 'REJECTED'
        borrow_req.rejection_reason = reason
        borrow_req.save()

        Notification.objects.create(
            user=borrow_req.borrower,
            title=f"Borrow Request Declined: {borrow_req.listing.title}",
            message=f"Your borrow request was declined: {reason}",
            notification_type='BORROW_STATUS',
            link_url=f"/borrowing/request/{borrow_req.id}/",
        )
        messages.info(request, "Borrow request declined.")
    return redirect('borrowing:borrow_detail', pk=borrow_req.id)


@login_required
def mark_borrow_active_view(request, pk):
    borrow_req = get_object_or_404(BorrowRequest, pk=pk)
    if request.user not in (borrow_req.listing.owner, borrow_req.borrower) and not request.user.is_staff:
        messages.error(request, "Permission denied.")
        return redirect('borrowing:borrow_detail', pk=borrow_req.id)

    if borrow_req.status == 'ACCEPTED':
        borrow_req.status = 'ACTIVE'
        borrow_req.save()
        messages.success(request, "Item marked as borrowed / ACTIVE. Record pickup condition in the Handover Log.")
    return redirect('borrowing:borrow_detail', pk=borrow_req.id)


@login_required
def mark_borrow_completed_view(request, pk):
    borrow_req = get_object_or_404(BorrowRequest, pk=pk)
    if borrow_req.listing.owner != request.user and not request.user.is_staff:
        messages.error(request, "Only the owner can confirm return.")
        return redirect('borrowing:borrow_detail', pk=borrow_req.id)

    if borrow_req.status in ('ACTIVE', 'RETURN_PENDING'):
        borrow_req.status = 'COMPLETED'
        borrow_req.save()

        Notification.objects.create(
            user=borrow_req.borrower,
            title=f"Borrow Loan Completed: {borrow_req.listing.title}",
            message=f"Thank you for returning '{borrow_req.listing.title}' on time! Please leave a review for the owner.",
            notification_type='BORROW_STATUS',
            link_url=f"/borrowing/request/{borrow_req.id}/",
        )
        messages.success(request, "Borrow loan marked as COMPLETED.")
    return redirect('borrowing:borrow_detail', pk=borrow_req.id)
