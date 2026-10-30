from decimal import Decimal
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.db.models import Sum, Q
from django.shortcuts import get_object_or_404, redirect, render
from .forms import RegistrationForm, UserUpdateForm, ProfileUpdateForm, AddressForm
from .models import Address
from listings.models import Listing
from rentals.models import RentalBooking
from borrowing.models import BorrowRequest
from orders.models import SalesOrder
from reviews.models import Review

User = get_user_model()


import json
import logging
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.core.exceptions import ValidationError
from .otp_service import (
    send_registration_email_otp,
    verify_registration_email_otp,
    send_password_reset_otp,
    verify_password_reset_otp,
    execute_password_reset,
)

logger = logging.getLogger(__name__)


def _get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _parse_request_data(request):
    if request.content_type == 'application/json' and request.body:
        try:
            return json.loads(request.body.decode('utf-8'))
        except Exception:
            return request.POST
    return request.POST



def register_view(request):
    if request.user.is_authenticated:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept', ''):
            return JsonResponse({'redirect_url': reverse('core:home')})
        return redirect('core:home')

    is_ajax = (
        request.headers.get('x-requested-with') == 'XMLHttpRequest'
        or 'application/json' in request.headers.get('Accept', '')
        or request.content_type == 'application/json'
    )

    if request.method == 'POST':
        if request.content_type == 'application/json' and request.body:
            try:
                data = json.loads(request.body)
            except Exception:
                data = request.POST
        else:
            data = request.POST

        form = RegistrationForm(data)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Welcome to ShareLoop, {user.first_name}! Your account has been created.")
            if is_ajax:
                return JsonResponse({
                    'success': True,
                    'message': f"Welcome to ShareLoop, {user.first_name}! Your account has been created.",
                    'redirect_url': reverse('accounts:dashboard')
                }, status=200)
            return redirect('accounts:dashboard')
        else:
            if is_ajax:
                structured_errors = {
                    field: [str(err) for err in err_list]
                    for field, err_list in form.errors.items()
                }
                return JsonResponse({
                    'success': False,
                    'errors': structured_errors,
                    'error': form.errors.as_text()
                }, status=400)
    else:
        initial_role = request.GET.get('role', 'INDIVIDUAL').upper()
        if initial_role not in ('INDIVIDUAL', 'BUSINESS'):
            initial_role = 'INDIVIDUAL'
        form = RegistrationForm(initial={'user_type': initial_role})

    return render(request, 'accounts/register.html', {'form': form})



def login_view(request):
    if request.user.is_authenticated:
        return redirect('core:home')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user:
                login(request, user)
                messages.success(request, f"Welcome back, {user.display_name}!")
                next_url = request.GET.get('next') or request.POST.get('next')
                if next_url:
                    return redirect(next_url)
                return redirect('accounts:dashboard')
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()

    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    if request.method == 'POST':
        logout(request)
        messages.info(request, "You have been logged out successfully.")
    return redirect('core:home')


@login_required
def profile_view(request):
    if request.method == 'POST':
        u_form = UserUpdateForm(request.POST, request.FILES, instance=request.user)
        p_form = ProfileUpdateForm(request.POST, instance=request.user.profile)
        if u_form.is_valid() and p_form.is_valid():
            u_form.save()
            p_form.save()
            messages.success(request, "Your profile has been updated successfully.")
            return redirect('accounts:profile')
    else:
        u_form = UserUpdateForm(instance=request.user)
        p_form = ProfileUpdateForm(instance=request.user.profile)

    addresses = request.user.addresses.all()
    addr_form = AddressForm()

    context = {
        'u_form': u_form,
        'p_form': p_form,
        'addr_form': addr_form,
        'addresses': addresses,
    }
    return render(request, 'accounts/profile.html', context)


@login_required
def address_add_view(request):
    if request.method == 'POST':
        form = AddressForm(request.POST)
        if form.is_valid():
            address = form.save(commit=False)
            address.user = request.user
            address.save()
            messages.success(request, "New address added.")
        else:
            messages.error(request, "Please check the address form fields.")
    return redirect('accounts:profile')


@login_required
def address_delete_view(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)
    if request.method == 'POST':
        address.delete()
        messages.success(request, "Address removed.")
    return redirect('accounts:profile')


@login_required
def dashboard_view(request):
    """
    Seller and User Dashboard:
    Distinguishes gross sales and rental income from refundable security deposits.
    """
    user = request.user

    # Listings summary
    user_listings = Listing.objects.filter(owner=user)
    total_listings = user_listings.count()
    active_listings = user_listings.filter(status='ACTIVE').count()

    # Incoming Requests (Where current user is the owner/seller)
    incoming_rentals = RentalBooking.objects.filter(listing__owner=user)
    pending_rentals_count = incoming_rentals.filter(status='PENDING').count()
    active_rentals_count = incoming_rentals.filter(status__in=['CONFIRMED', 'ACTIVE']).count()

    incoming_borrows = BorrowRequest.objects.filter(listing__owner=user)
    pending_borrows_count = incoming_borrows.filter(status='PENDING').count()
    active_borrows_count = incoming_borrows.filter(status='ACTIVE').count()

    incoming_orders = SalesOrder.objects.filter(seller=user)
    pending_orders_count = incoming_orders.filter(status__in=['PENDING', 'CONFIRMED', 'PROCESSING']).count()

    total_pending_requests = pending_rentals_count + pending_borrows_count + pending_orders_count

    # Financial Metrics (Real completed transactions only)
    # Rental income = actual rental fees (NOT refundable deposits)
    completed_rentals = incoming_rentals.filter(status='COMPLETED')
    rental_earnings = completed_rentals.aggregate(total=Sum('rental_fee'))['total'] or Decimal('0.00')

    # Sales earnings = total_item_amount for completed sales
    completed_sales = incoming_orders.filter(status='COMPLETED')
    sales_earnings = completed_sales.aggregate(total=Sum('items_total'))['total'] or Decimal('0.00')

    total_earnings = rental_earnings + sales_earnings
    completed_transactions_count = completed_rentals.count() + completed_sales.count()

    # Recent incoming rental & borrow requests
    recent_rentals = incoming_rentals.order_by('-created_at')[:5]
    recent_borrows = incoming_borrows.order_by('-created_at')[:5]
    recent_orders = incoming_orders.order_by('-created_at')[:5]

    context = {
        'total_listings': total_listings,
        'active_listings': active_listings,
        'total_pending_requests': total_pending_requests,
        'pending_rentals_count': pending_rentals_count,
        'pending_borrows_count': pending_borrows_count,
        'pending_orders_count': pending_orders_count,
        'active_rentals_count': active_rentals_count,
        'active_borrows_count': active_borrows_count,
        'completed_transactions_count': completed_transactions_count,
        'rental_earnings': rental_earnings,
        'sales_earnings': sales_earnings,
        'total_earnings': total_earnings,
        'recent_rentals': recent_rentals,
        'recent_borrows': recent_borrows,
        'recent_orders': recent_orders,
    }
    return render(request, 'accounts/dashboard.html', context)


def public_profile_view(request, username):
    """
    Public seller or individual user profile.
    Verification badge shown only when is_verified is True.
    """
    seller = get_object_or_404(User, username=username)
    active_listings = Listing.objects.filter(
        owner=seller,
        status='ACTIVE',
        moderation_status='APPROVED'
    ).order_by('-created_at')

    reviews = Review.objects.filter(reviewee=seller, moderation_status='PUBLISHED').order_by('-created_at')
    rating_avg = reviews.aggregate(avg=Sum('rating'))['avg']
    avg_score = round(rating_avg / reviews.count(), 1) if reviews.count() > 0 and rating_avg else None

    context = {
        'seller': seller,
        'active_listings': active_listings,
        'reviews': reviews,
        'avg_score': avg_score,
        'review_count': reviews.count(),
    }
    return render(request, 'accounts/seller_profile.html', context)


# ==========================================
# Email OTP & Password Recovery Endpoints
# ==========================================

@require_POST
def register_send_email_otp(request):
    """
    POST /accounts/register/send-email-otp/
    Accepts: { 'email': 'user@example.com' }
    Sends a cryptographically secure 6-digit OTP to the registration email.
    """
    data = _parse_request_data(request)
    email = data.get('email', '')
    try:
        result = send_registration_email_otp(email, ip_address=_get_client_ip(request))
        return JsonResponse(result, status=200)
    except ValidationError as e:
        msg = e.messages[0] if hasattr(e, 'messages') else str(e)
        return JsonResponse({'success': False, 'error': msg}, status=400)
    except Exception as e:
        logger.error(f"Error in register_send_email_otp: {str(e)}")
        return JsonResponse({'success': False, 'error': 'Server error sending verification email. Please try again.'}, status=500)


@require_POST
def register_verify_email_otp(request):
    """
    POST /accounts/register/verify-email-otp/
    Accepts: { 'email': 'user@example.com', 'otp': '123456' }
    Verifies the email OTP and returns a single-use verification token.
    """
    data = _parse_request_data(request)
    email = data.get('email', '')
    otp = data.get('otp', '')
    try:
        result = verify_registration_email_otp(email, otp)
        return JsonResponse(result, status=200)
    except ValidationError as e:
        msg = e.messages[0] if hasattr(e, 'messages') else str(e)
        return JsonResponse({'success': False, 'error': msg}, status=400)
    except Exception as e:
        logger.error(f"Error in register_verify_email_otp: {str(e)}")
        return JsonResponse({'success': False, 'error': 'Server error verifying code. Please try again.'}, status=500)


def forgot_password_view(request):
    """
    GET /accounts/forgot-password/
    Renders password recovery page with Email & Phone options.
    """
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')
    return render(request, 'accounts/forgot_password.html')


@require_POST
def forgot_password_send_otp(request):
    """
    POST /accounts/forgot-password/send-otp/
    Accepts: { 'contact_type': 'email'|'phone', 'contact_value': '...' }
    Dispatches recovery OTP via email or real SMS provider.
    """
    data = _parse_request_data(request)
    contact_type = data.get('contact_type', 'email')
    contact_value = data.get('contact_value') or data.get('email') or data.get('phone_number') or data.get('phone') or ''
    try:
        result = send_password_reset_otp(contact_type, contact_value, ip_address=_get_client_ip(request))
        return JsonResponse(result, status=200)
    except ValidationError as e:
        msg = e.messages[0] if hasattr(e, 'messages') else str(e)
        return JsonResponse({'success': False, 'error': msg}, status=400)
    except Exception as e:
        logger.error(f"Error in forgot_password_send_otp: {str(e)}")
        return JsonResponse({'success': False, 'error': 'Server error sending recovery code. Please try again.'}, status=500)


@require_POST
def forgot_password_verify_otp(request):
    """
    POST /accounts/forgot-password/verify-otp/
    Accepts: { 'contact_type': 'email'|'phone', 'contact_value': '...', 'otp': '123456' }
    Verifies OTP and returns a cryptographically secure single-use reset authorization token.
    """
    data = _parse_request_data(request)
    contact_type = data.get('contact_type', 'email')
    contact_value = data.get('contact_value') or data.get('email') or data.get('phone_number') or data.get('phone') or ''
    otp = data.get('otp', '')
    try:
        result = verify_password_reset_otp(contact_type, contact_value, otp)
        return JsonResponse(result, status=200)
    except ValidationError as e:
        msg = e.messages[0] if hasattr(e, 'messages') else str(e)
        return JsonResponse({'success': False, 'error': msg}, status=400)
    except Exception as e:
        logger.error(f"Error in forgot_password_verify_otp: {str(e)}")
        return JsonResponse({'success': False, 'error': 'Server error verifying recovery code. Please try again.'}, status=500)


@require_POST
def reset_password_view(request):
    """
    POST /accounts/reset-password/
    Accepts: { 'reset_token': '...', 'password1': '...', 'password2': '...' }
    Updates the password, invalidates the token, and resets session.
    """
    data = _parse_request_data(request)
    reset_token = data.get('reset_token', '')
    password1_raw = data.get('password1') or data.get('password') or data.get('new_password') or ''
    password2_raw = data.get('password2') or data.get('confirm_password') or data.get('new_password2') or ''
    try:
        result = execute_password_reset(reset_token, password1_raw, password2_raw)
        messages.success(request, "Your password has been reset successfully! Please log in with your new password.")
        result['redirect_url'] = reverse('accounts:login')
        return JsonResponse(result, status=200)
    except ValidationError as e:
        msg = e.messages[0] if hasattr(e, 'messages') else str(e)
        return JsonResponse({'success': False, 'error': msg}, status=400)
    except Exception as e:
        logger.error(f"Error in reset_password_view: {str(e)}")
        return JsonResponse({'success': False, 'error': 'Server error resetting password. Please try again.'}, status=500)


# Dedicated aliases for Feature 6 routes
@require_POST
def auth_forgot_password_email(request):
    data = _parse_request_data(request)
    email = data.get('email', '')
    try:
        result = send_password_reset_otp('email', email, ip_address=_get_client_ip(request))
        return JsonResponse(result, status=200)
    except ValidationError as e:
        msg = e.messages[0] if hasattr(e, 'messages') else str(e)
        return JsonResponse({'success': False, 'error': msg}, status=400)


@require_POST
def auth_forgot_password_phone(request):
    data = _parse_request_data(request)
    phone = data.get('phone_number') or data.get('phone') or ''
    try:
        result = send_password_reset_otp('phone', phone, ip_address=_get_client_ip(request))
        return JsonResponse(result, status=200)
    except ValidationError as e:
        msg = e.messages[0] if hasattr(e, 'messages') else str(e)
        return JsonResponse({'success': False, 'error': msg}, status=400)

