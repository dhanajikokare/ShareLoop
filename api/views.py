from decimal import Decimal
from datetime import datetime
from django.contrib.auth import authenticate
from django.db import transaction
from django.db.models import Q, Avg
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from accounts.models import User, Address, UserProfile
from listings.models import Category, Listing, ListingImage, ListingReport
from rentals.models import RentalBooking
from borrowing.models import BorrowRequest
from orders.models import SalesOrder
from payments.models import Payment
from reviews.models import Review, HandoverLog
from core.models import Notification
from .models import Favorite, Conversation, ChatMessage
from .serializers import (
    UserSerializer, AddressSerializer, CategorySerializer,
    ListingListSerializer, ListingDetailSerializer,
    RentalBookingSerializer, BorrowRequestSerializer,
    SalesOrderSerializer, PaymentSerializer,
    ReviewSerializer, HandoverLogSerializer, NotificationSerializer
)

# ----------------------------------------------------
# AUTHENTICATION & PROFILE
# ----------------------------------------------------

@api_view(['POST'])
@permission_classes([AllowAny])
def api_login(request):
    username_or_email = request.data.get('username', '').strip()
    password = request.data.get('password', '')

    if not username_or_email or not password:
        return Response({'error': 'Please provide both username/email and password.'}, status=status.HTTP_400_BAD_REQUEST)

    # Check if user passed email instead of username
    user = None
    if '@' in username_or_email:
        user_obj = User.objects.filter(email__iexact=username_or_email).first()
        if user_obj:
            user = authenticate(username=user_obj.username, password=password)
    if not user:
        user = authenticate(username=username_or_email, password=password)

    if not user:
        return Response({'error': 'Invalid credentials. Please verify username and password.'}, status=status.HTTP_401_UNAUTHORIZED)

    if not user.is_active:
        return Response({'error': 'Your account is currently disabled. Contact support.'}, status=status.HTTP_403_FORBIDDEN)

    token, _ = Token.objects.get_or_create(user=user)
    return Response({
        'token': token.key,
        'user': UserSerializer(user, context={'request': request}).data
    })


from accounts.validators import validate_and_normalize_indian_phone, validate_email_format
from accounts.otp_service import (
    send_registration_email_otp,
    verify_registration_email_otp,
    check_email_is_verified_for_registration,
    mark_registration_verification_used,
    send_password_reset_otp,
    verify_password_reset_otp,
    execute_password_reset,
)
from django.core.exceptions import ValidationError

@api_view(['POST'])
@permission_classes([AllowAny])
def api_register(request):
    errors = {}
    username = request.data.get('username', '').strip()
    first_name = request.data.get('first_name', '').strip()
    last_name = request.data.get('last_name', '').strip()
    email_raw = request.data.get('email', '')
    phone_raw = request.data.get('phone_number', '')
    password = request.data.get('password', '')
    user_type = request.data.get('user_type', 'INDIVIDUAL')
    shop_name = request.data.get('shop_name', '').strip()

    if not username:
        errors['username'] = ['Username is required.']
    elif User.objects.filter(username__iexact=username).exists():
        errors['username'] = ['This username is already taken. Choose another.']

    # Email validation
    normalized_email = None
    try:
        normalized_email = validate_email_format(email_raw)
        if User.objects.filter(email__iexact=normalized_email).exists():
            errors['email'] = ['An account with this email already exists.']
    except ValidationError as e:
        errors['email'] = list(e.messages)

    # Phone validation
    normalized_phone = None
    try:
        normalized_phone = validate_and_normalize_indian_phone(phone_raw)
        mobile_10 = normalized_phone.replace('+91', '')
        phone_variations = [
            normalized_phone,
            mobile_10,
            f"0{mobile_10}",
            f"+91 {mobile_10[:5]} {mobile_10[5:]}",
            f"+91 {mobile_10}",
        ]
        if User.objects.filter(phone_number__in=phone_variations).exists():
            errors['phone_number'] = ['An account with this phone number already exists.']
    except ValidationError as e:
        errors['phone_number'] = list(e.messages)

    # User role validation
    if user_type not in ('INDIVIDUAL', 'BUSINESS'):
        errors['user_type'] = ['Please select a valid account role (Individual User or Business Seller).']

    # Shop name validation
    if user_type == 'BUSINESS' and not shop_name:
        errors['shop_name'] = ['Shop or business name is required for Business Sellers.']
    elif len(shop_name) > 100:
        errors['shop_name'] = ['Shop or business name cannot exceed 100 characters.']

    # Password validation
    if not password:
        errors['password'] = ['Password is required.']
    elif not password.strip():
        errors['password'] = ['Password cannot consist entirely of whitespace.']
    elif len(password) < 8:
        errors['password'] = ['Password must be at least 8 characters long.']
    elif len(password) > 128:
        errors['password'] = ['Password cannot exceed 128 characters.']

    # Enforce email OTP verification on backend
    verification_token = request.data.get('email_verification_token')
    if normalized_email and not errors.get('email'):
        if not check_email_is_verified_for_registration(normalized_email, verification_token=verification_token):
            errors['email'] = ['Please verify your email address with the verification code before registering.']

    if errors:
        first_error = next(iter(errors.values()))[0]
        return Response({'errors': errors, 'error': first_error}, status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.create_user(
        username=username,
        email=normalized_email,
        password=password,
        first_name=first_name,
        last_name=last_name,
        user_type=user_type,
        phone_number=normalized_phone
    )

    if shop_name and hasattr(user, 'profile'):
        user.profile.shop_name = shop_name
        user.profile.save()

    mark_registration_verification_used(normalized_email)

    token, _ = Token.objects.get_or_create(user=user)
    return Response({
        'token': token.key,
        'user': UserSerializer(user, context={'request': request}).data
    }, status=status.HTTP_201_CREATED)



@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def api_me(request):
    user = request.user
    if request.method == 'PUT':
        user.first_name = request.data.get('first_name', user.first_name)
        user.last_name = request.data.get('last_name', user.last_name)
        user.phone_number = request.data.get('phone_number', user.phone_number)
        user.bio = request.data.get('bio', user.bio)
        user.save()

        if hasattr(user, 'profile') and user.user_type == 'BUSINESS':
            user.profile.shop_name = request.data.get('shop_name', user.profile.shop_name)
            user.profile.shop_description = request.data.get('shop_description', user.profile.shop_description)
            user.profile.save()

    return Response({
        'user': UserSerializer(user, context={'request': request}).data,
        'stats': {
            'listings_count': user.listings.count(),
            'rentals_as_renter': user.rental_bookings.count(),
            'rentals_as_owner': RentalBooking.objects.filter(listing__owner=user).count(),
            'borrows_count': user.borrow_requests.count(),
            'orders_bought': user.sales_orders_bought.count(),
            'orders_sold': user.sales_orders_sold.count(),
            'favorites_count': user.favorites.count(),
            'unread_notifications': user.notifications.filter(is_read=False).count(),
        }
    })


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def api_addresses(request):
    if request.method == 'GET':
        addresses = request.user.addresses.all()
        return Response(AddressSerializer(addresses, many=True).data)

    serializer = AddressSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ----------------------------------------------------
# CATEGORIES & PRODUCT DISCOVERY
# ----------------------------------------------------

@api_view(['GET'])
@permission_classes([AllowAny])
def api_categories(request):
    categories = Category.objects.filter(is_active=True).order_by('display_order', 'name')
    return Response(CategorySerializer(categories, many=True).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def api_listings(request):
    qs = Listing.objects.filter(status='ACTIVE', moderation_status='APPROVED').select_related('owner', 'category').prefetch_related('images').distinct()

    # Mode filter: rent, borrow, sell
    mode = request.GET.get('mode', '').lower()
    if mode == 'rent':
        qs = qs.filter(can_rent=True)
    elif mode == 'borrow':
        qs = qs.filter(can_borrow=True)
    elif mode == 'sell':
        qs = qs.filter(can_sell=True)

    # Category filter
    category_id = request.GET.get('category')
    if category_id:
        qs = qs.filter(category_id=category_id)

    # Locality filter (e.g. Pune localities)
    locality = request.GET.get('locality')
    if locality:
        qs = qs.filter(locality__iexact=locality)

    # Search keyword
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q) |
            Q(description__icontains=q) |
            Q(locality__icontains=q) |
            Q(category__name__icontains=q)
        )

    # Price range
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    if min_price:
        try:
            val = Decimal(min_price)
            qs = qs.filter(Q(rent_price_per_day__gte=val) | Q(sell_price__gte=val))
        except Exception:
            pass
    if max_price:
        try:
            val = Decimal(max_price)
            qs = qs.filter(Q(rent_price_per_day__lte=val) | Q(sell_price__lte=val))
        except Exception:
            pass

    # Sorting
    sort = request.GET.get('sort', 'newest')
    if sort == 'price_low':
        qs = qs.order_by('rent_price_per_day', 'sell_price')
    elif sort == 'price_high':
        qs = qs.order_by('-rent_price_per_day', '-sell_price')
    else:
        qs = qs.order_by('-created_at')

    serializer = ListingListSerializer(qs, many=True, context={'request': request})
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([AllowAny])
def api_listing_detail(request, pk):
    listing = get_object_or_404(Listing.objects.select_related('owner', 'category').prefetch_related('images', 'reviews'), pk=pk)
    data = ListingDetailSerializer(listing, context={'request': request}).data

    # Add reviews list and average rating
    reviews = listing.reviews.filter(moderation_status='PUBLISHED')
    avg_rating = reviews.aggregate(Avg('rating'))['rating__avg'] or 5.0
    data['reviews'] = ReviewSerializer(reviews, many=True).data
    data['reviews_count'] = reviews.count()
    data['average_rating'] = round(float(avg_rating), 1)

    # Check if favorited by requesting user
    data['is_favorited'] = False
    if request.user.is_authenticated:
        data['is_favorited'] = Favorite.objects.filter(user=request.user, listing=listing).exists()

    return Response(data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def api_listing_create(request):
    data = request.data
    title = data.get('title', '').strip()
    category_id = data.get('category_id') or data.get('category')
    description = data.get('description', '').strip()
    item_condition = data.get('item_condition', 'GOOD')
    locality = data.get('locality', 'Kothrud').strip()
    city = data.get('city', 'Pune').strip()
    pincode = data.get('pincode', '411038').strip()

    can_rent = str(data.get('can_rent', 'false')).lower() in ('true', '1')
    can_borrow = str(data.get('can_borrow', 'false')).lower() in ('true', '1')
    can_sell = str(data.get('can_sell', 'false')).lower() in ('true', '1')

    if not (can_rent or can_borrow or can_sell):
        return Response({'error': 'At least one listing mode (Rent, Borrow, or Sell) must be enabled.'}, status=status.HTTP_400_BAD_REQUEST)

    category = get_object_or_404(Category, pk=category_id)

    listing = Listing(
        owner=request.user,
        category=category,
        title=title,
        description=description,
        item_condition=item_condition,
        locality=locality,
        city=city,
        pincode=pincode,
        can_rent=can_rent,
        can_borrow=can_borrow,
        can_sell=can_sell,
        pickup_available=str(data.get('pickup_available', 'true')).lower() in ('true', '1'),
        delivery_available=str(data.get('delivery_available', 'false')).lower() in ('true', '1')
    )

    if can_rent:
        listing.rent_price_per_day = Decimal(str(data.get('rent_price_per_day', '100')))
        listing.rent_security_deposit = Decimal(str(data.get('rent_security_deposit', '0')))
        listing.min_rental_days = int(data.get('min_rental_days', 1))
        listing.max_rental_days = int(data.get('max_rental_days', 30))

    if can_borrow:
        listing.is_free_borrow = True
        listing.borrow_security_deposit = Decimal(str(data.get('borrow_security_deposit', '0')))
        listing.borrow_max_days = int(data.get('borrow_max_days', 7))

    if can_sell:
        listing.sell_price = Decimal(str(data.get('sell_price', '500')))
        listing.quantity = int(data.get('quantity', 1))

    listing.save()

    # Handle image upload if provided
    images = request.FILES.getlist('images') or request.FILES.getlist('image')
    for idx, img_file in enumerate(images):
        ListingImage.objects.create(
            listing=listing,
            image=img_file,
            is_primary=(idx == 0)
        )

    return Response(ListingDetailSerializer(listing, context={'request': request}).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_my_listings(request):
    listings = Listing.objects.filter(owner=request.user).order_by('-created_at')
    return Response(ListingListSerializer(listings, many=True, context={'request': request}).data)


# ----------------------------------------------------
# RENTAL WORKFLOW
# ----------------------------------------------------

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_rental_create(request):
    listing_id = request.data.get('listing_id')
    listing = get_object_or_404(Listing, pk=listing_id)

    if not listing.can_rent:
        return Response({'error': 'This item is not available for rent.'}, status=status.HTTP_400_BAD_REQUEST)

    if listing.owner_id == request.user.id:
        return Response({'error': 'You cannot rent your own item.'}, status=status.HTTP_400_BAD_REQUEST)

    start_str = request.data.get('start_date')
    end_str = request.data.get('end_date')
    renter_message = request.data.get('message', '')

    try:
        start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_str, '%Y-%m-%d').date()
    except Exception:
        return Response({'error': 'Invalid date format. Use YYYY-MM-DD.'}, status=status.HTTP_400_BAD_REQUEST)

    if end_date < start_date:
        return Response({'error': 'End date must be on or after start date.'}, status=status.HTTP_400_BAD_REQUEST)

    days = (end_date - start_date).days + 1
    if days < listing.min_rental_days:
        return Response({'error': f'Minimum rental period is {listing.min_rental_days} day(s).'}, status=status.HTTP_400_BAD_REQUEST)
    if days > listing.max_rental_days:
        return Response({'error': f'Maximum rental period is {listing.max_rental_days} day(s).'}, status=status.HTTP_400_BAD_REQUEST)

    # Check calendar conflict
    available, msg = listing.is_available_for_dates(start_date, end_date)
    if not available:
        return Response({'error': msg}, status=status.HTTP_409_CONFLICT)

    # Financial calculations
    daily_rate = listing.rent_price_per_day
    rental_fee = daily_rate * days
    security_deposit = listing.rent_security_deposit or Decimal('0.00')
    platform_fee = (rental_fee * Decimal('0.05')).quantize(Decimal('0.01'))
    total_amount = rental_fee + security_deposit + platform_fee

    booking = RentalBooking.objects.create(
        listing=listing,
        renter=request.user,
        start_date=start_date,
        end_date=end_date,
        total_days=days,
        daily_rate=daily_rate,
        rental_fee=rental_fee,
        security_deposit=security_deposit,
        platform_fee=platform_fee,
        total_amount=total_amount,
        renter_message=renter_message,
        status='PENDING'
    )

    # Notify Owner
    Notification.objects.create(
        user=listing.owner,
        title='New Rental Request',
        message=f"{request.user.display_name} requested to rent '{listing.title}' for {days} day(s).",
        notification_type='RENTAL_REQUEST'
    )

    return Response(RentalBookingSerializer(booking).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_my_rentals(request):
    as_renter = RentalBooking.objects.filter(renter=request.user).order_by('-created_at')
    as_owner = RentalBooking.objects.filter(listing__owner=request.user).order_by('-created_at')
    return Response({
        'as_renter': RentalBookingSerializer(as_renter, many=True).data,
        'as_owner': RentalBookingSerializer(as_owner, many=True).data,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_rental_action(request, pk):
    booking = get_object_or_404(RentalBooking, pk=pk)
    action = request.data.get('action') # 'accept', 'reject', 'handover', 'return'
    user = request.user

    is_owner = (booking.listing.owner_id == user.id)
    is_renter = (booking.renter_id == user.id)

    if not (is_owner or is_renter):
        return Response({'error': 'Unauthorized to modify this booking.'}, status=status.HTTP_403_FORBIDDEN)

    if action == 'accept' and is_owner:
        if booking.status != 'PENDING':
            return Response({'error': 'Can only accept pending bookings.'}, status=status.HTTP_400_BAD_REQUEST)
        booking.status = 'CONFIRMED'
        booking.save()
        Notification.objects.create(
            user=booking.renter,
            title='Rental Request Accepted!',
            message=f"Owner accepted your booking for '{booking.listing.title}'.",
            notification_type='RENTAL_STATUS'
        )
    elif action == 'reject' and is_owner:
        booking.status = 'REJECTED'
        booking.rejection_reason = request.data.get('reason', 'Unavailable for requested dates.')
        booking.save()
    elif action == 'handover' and is_owner:
        booking.status = 'ACTIVE'
        booking.save()
    elif action == 'return' and is_owner:
        booking.status = 'COMPLETED'
        booking.save()
    else:
        return Response({'error': 'Invalid action or permissions.'}, status=status.HTTP_400_BAD_REQUEST)

    return Response(RentalBookingSerializer(booking).data)


# ----------------------------------------------------
# BORROW WORKFLOW (100% FREE PEER LOAN)
# ----------------------------------------------------

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_borrow_create(request):
    listing_id = request.data.get('listing_id')
    listing = get_object_or_404(Listing, pk=listing_id)

    if not listing.can_borrow:
        return Response({'error': 'This item is not available for borrowing.'}, status=status.HTTP_400_BAD_REQUEST)

    if listing.owner_id == request.user.id:
        return Response({'error': 'You cannot borrow your own item.'}, status=status.HTTP_400_BAD_REQUEST)

    start_str = request.data.get('start_date')
    end_str = request.data.get('end_date')
    borrower_message = request.data.get('message', 'I promise to handle this item with great care.')

    try:
        start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_str, '%Y-%m-%d').date()
    except Exception:
        return Response({'error': 'Invalid date format. Use YYYY-MM-DD.'}, status=status.HTTP_400_BAD_REQUEST)

    days = (end_date - start_date).days + 1
    if days > listing.borrow_max_days:
        return Response({'error': f'Maximum borrow duration is {listing.borrow_max_days} days.'}, status=status.HTTP_400_BAD_REQUEST)

    available, msg = listing.is_available_for_dates(start_date, end_date)
    if not available:
        return Response({'error': msg}, status=status.HTTP_409_CONFLICT)

    req = BorrowRequest.objects.create(
        listing=listing,
        borrower=request.user,
        start_date=start_date,
        end_date=end_date,
        total_days=days,
        is_free=True,
        security_deposit=listing.borrow_security_deposit or Decimal('0.00'),
        borrower_message=borrower_message,
        agreed_to_terms=True,
        status='PENDING'
    )

    Notification.objects.create(
        user=listing.owner,
        title='New Borrow Request',
        message=f"{request.user.display_name} requested to borrow '{listing.title}' for {days} day(s).",
        notification_type='BORROW_REQUEST'
    )

    return Response(BorrowRequestSerializer(req).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_my_borrows(request):
    as_borrower = BorrowRequest.objects.filter(borrower=request.user).order_by('-created_at')
    as_owner = BorrowRequest.objects.filter(listing__owner=request.user).order_by('-created_at')
    return Response({
        'as_borrower': BorrowRequestSerializer(as_borrower, many=True).data,
        'as_owner': BorrowRequestSerializer(as_owner, many=True).data,
    })


# ----------------------------------------------------
# BUY & SELL WORKFLOW (ATOMIC TRANSACTION)
# ----------------------------------------------------

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_order_create(request):
    listing_id = request.data.get('listing_id')
    fulfillment_type = request.data.get('fulfillment_type', 'PICKUP')
    delivery_address = request.data.get('delivery_address', '')
    buyer_note = request.data.get('buyer_note', '')

    with transaction.atomic():
        listing = Listing.objects.select_for_update().filter(pk=listing_id).first()
        if not listing:
            return Response({'error': 'Listing not found.'}, status=status.HTTP_404_NOT_FOUND)

        if not listing.can_sell:
            return Response({'error': 'This item is not available for purchase.'}, status=status.HTTP_400_BAD_REQUEST)

        if listing.owner_id == request.user.id:
            return Response({'error': 'You cannot buy your own listing.'}, status=status.HTTP_400_BAD_REQUEST)

        if listing.status == 'SOLD' or listing.quantity < 1:
            return Response({'error': 'Item is already sold out.'}, status=status.HTTP_409_CONFLICT)

        items_total = listing.sell_price
        platform_fee = (items_total * Decimal('0.02')).quantize(Decimal('0.01'))
        delivery_fee = Decimal('50.00') if fulfillment_type == 'DELIVERY' else Decimal('0.00')
        total_amount = items_total + platform_fee + delivery_fee

        order = SalesOrder.objects.create(
            buyer=request.user,
            seller=listing.owner,
            items_total=items_total,
            platform_fee=platform_fee,
            delivery_fee=delivery_fee,
            total_amount=total_amount,
            fulfillment_type=fulfillment_type,
            delivery_address=delivery_address,
            buyer_note=buyer_note,
            status='CONFIRMED'
        )

        listing.quantity -= 1
        if listing.quantity == 0:
            listing.status = 'SOLD'
        listing.save()

        Notification.objects.create(
            user=listing.owner,
            title='Product Sold!',
            message=f"{request.user.display_name} purchased '{listing.title}' (Order: {order.order_number}).",
            notification_type='ORDER_PLACED'
        )

    return Response(SalesOrderSerializer(order).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_my_orders(request):
    bought = SalesOrder.objects.filter(buyer=request.user).order_by('-created_at')
    sold = SalesOrder.objects.filter(seller=request.user).order_by('-created_at')
    return Response({
        'orders_bought': SalesOrderSerializer(bought, many=True).data,
        'orders_sold': SalesOrderSerializer(sold, many=True).data,
    })


# ----------------------------------------------------
# CHAT & MESSAGING
# ----------------------------------------------------

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def api_conversations(request):
    user = request.user
    if request.method == 'GET':
        convs = user.conversations.select_related('listing').prefetch_related('participants', 'messages').order_by('-updated_at')
        results = []
        for c in convs:
            other = c.participants.exclude(id=user.id).first()
            last_msg = c.messages.last()
            unread_count = c.messages.filter(is_read=False).exclude(sender=user).count()
            results.append({
                'id': c.id,
                'listing_id': c.listing_id,
                'listing_title': c.listing.title if c.listing else 'Direct Inquiry',
                'other_user': UserSerializer(other, context={'request': request}).data if other else None,
                'last_message': last_msg.text if last_msg else '',
                'last_message_time': last_msg.created_at if last_msg else c.updated_at,
                'unread_count': unread_count
            })
        return Response(results)

    # POST: start or get existing conversation
    other_user_id = request.data.get('other_user_id')
    listing_id = request.data.get('listing_id')
    other_user = get_object_or_404(User, pk=other_user_id)

    # Find existing
    conv = Conversation.objects.filter(participants=user).filter(participants=other_user)
    if listing_id:
        conv = conv.filter(listing_id=listing_id)
    conv = conv.first()

    if not conv:
        conv = Conversation.objects.create(listing_id=listing_id)
        conv.participants.add(user, other_user)

    initial_text = request.data.get('message')
    if initial_text:
        ChatMessage.objects.create(conversation=conv, sender=user, text=initial_text)

    return Response({'id': conv.id}, status=status.HTTP_201_CREATED)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def api_conversation_messages(request, pk):
    conv = get_object_or_404(Conversation, pk=pk)
    if not conv.participants.filter(id=request.user.id).exists():
        return Response({'error': 'Unauthorized to view this conversation.'}, status=status.HTTP_403_FORBIDDEN)

    if request.method == 'GET':
        # Mark incoming as read
        conv.messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)
        messages = conv.messages.select_related('sender').order_by('created_at')
        return Response([
            {
                'id': m.id,
                'sender_id': m.sender_id,
                'sender_name': m.sender.display_name,
                'is_me': (m.sender_id == request.user.id),
                'text': m.text,
                'created_at': m.created_at,
                'is_read': m.is_read
            }
            for m in messages
        ])

    text = request.data.get('text', '').strip()
    if not text:
        return Response({'error': 'Message text cannot be empty.'}, status=status.HTTP_400_BAD_REQUEST)

    msg = ChatMessage.objects.create(conversation=conv, sender=request.user, text=text)
    conv.save() # bump updated_at

    return Response({
        'id': msg.id,
        'sender_id': msg.sender_id,
        'sender_name': msg.sender.display_name,
        'is_me': True,
        'text': msg.text,
        'created_at': msg.created_at,
        'is_read': False
    }, status=status.HTTP_201_CREATED)


# ----------------------------------------------------
# FAVORITES / WISHLIST
# ----------------------------------------------------

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def api_favorites(request):
    user = request.user
    if request.method == 'GET':
        favs = user.favorites.select_related('listing__owner', 'listing__category').prefetch_related('listing__images')
        listings = [f.listing for f in favs]
        return Response(ListingListSerializer(listings, many=True, context={'request': request}).data)

    listing_id = request.data.get('listing_id')
    listing = get_object_or_404(Listing, pk=listing_id)
    fav = Favorite.objects.filter(user=user, listing=listing).first()

    if fav:
        fav.delete()
        return Response({'is_favorited': False, 'message': 'Removed from favorites.'})
    else:
        Favorite.objects.create(user=user, listing=listing)
        return Response({'is_favorited': True, 'message': 'Added to favorites.'})


# ----------------------------------------------------
# NOTIFICATIONS
# ----------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_notifications(request):
    notifs = request.user.notifications.all()[:50]
    return Response(NotificationSerializer(notifs, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_notification_read(request, pk):
    notif = get_object_or_404(Notification, pk=pk, user=request.user)
    notif.is_read = True
    notif.save()
    return Response({'status': 'ok'})


def _get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


@api_view(['POST'])
@permission_classes([AllowAny])
def api_register_send_email_otp(request):
    email = request.data.get('email', '')
    try:
        result = send_registration_email_otp(email, ip_address=_get_client_ip(request))
        return Response(result, status=status.HTTP_200_OK)
    except ValidationError as e:
        msg = e.messages[0] if hasattr(e, 'messages') else str(e)
        return Response({'success': False, 'error': msg}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'success': False, 'error': 'Server error sending verification email.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def api_register_verify_email_otp(request):
    email = request.data.get('email', '')
    otp = request.data.get('otp', '')
    try:
        result = verify_registration_email_otp(email, otp)
        return Response(result, status=status.HTTP_200_OK)
    except ValidationError as e:
        msg = e.messages[0] if hasattr(e, 'messages') else str(e)
        return Response({'success': False, 'error': msg}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'success': False, 'error': 'Server error verifying code.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def api_forgot_password_email(request):
    email = request.data.get('email', '')
    try:
        result = send_password_reset_otp('email', email, ip_address=_get_client_ip(request))
        return Response(result, status=status.HTTP_200_OK)
    except ValidationError as e:
        msg = e.messages[0] if hasattr(e, 'messages') else str(e)
        return Response({'success': False, 'error': msg}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'success': False, 'error': 'Server error sending recovery email.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def api_forgot_password_phone(request):
    phone = request.data.get('phone_number') or request.data.get('phone') or ''
    try:
        result = send_password_reset_otp('phone', phone, ip_address=_get_client_ip(request))
        return Response(result, status=status.HTTP_200_OK)
    except ValidationError as e:
        msg = e.messages[0] if hasattr(e, 'messages') else str(e)
        return Response({'success': False, 'error': msg}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'success': False, 'error': 'Server error sending recovery SMS.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def api_forgot_password_verify_otp(request):
    contact_type = request.data.get('contact_type', 'email')
    contact_value = request.data.get('contact_value') or request.data.get('email') or request.data.get('phone_number') or request.data.get('phone') or ''
    otp = request.data.get('otp', '')
    try:
        result = verify_password_reset_otp(contact_type, contact_value, otp)
        return Response(result, status=status.HTTP_200_OK)
    except ValidationError as e:
        msg = e.messages[0] if hasattr(e, 'messages') else str(e)
        return Response({'success': False, 'error': msg}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'success': False, 'error': 'Server error verifying recovery code.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def api_reset_password(request):
    reset_token = request.data.get('reset_token', '')
    p1 = request.data.get('password1') or request.data.get('password') or request.data.get('new_password') or ''
    p2 = request.data.get('password2') or request.data.get('confirm_password') or request.data.get('new_password2') or ''
    try:
        result = execute_password_reset(reset_token, p1, p2)
        return Response(result, status=status.HTTP_200_OK)
    except ValidationError as e:
        msg = e.messages[0] if hasattr(e, 'messages') else str(e)
        return Response({'success': False, 'error': msg}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'success': False, 'error': 'Server error resetting password.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
