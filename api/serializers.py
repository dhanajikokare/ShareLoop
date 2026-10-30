from rest_framework import serializers
from decimal import Decimal
from accounts.models import User, UserProfile, Address
from listings.models import Category, Listing, ListingImage, ListingReport
from rentals.models import RentalBooking
from borrowing.models import BorrowRequest
from orders.models import SalesOrder
from payments.models import Payment
from reviews.models import Review, HandoverLog
from core.models import Notification

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = [
            'shop_name', 'shop_description', 'business_registration_number',
            'gst_number', 'alternate_phone', 'emergency_contact', 'preferred_language'
        ]

class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = [
            'id', 'full_name', 'phone_number', 'address_line1', 'address_line2',
            'locality', 'city', 'state', 'pincode', 'is_default'
        ]
        read_only_fields = ['id']

class UserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)
    addresses = AddressSerializer(many=True, read_only=True)
    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'user_type', 'phone_number', 'is_verified', 'avatar',
            'bio', 'display_name', 'profile', 'addresses'
        ]
        read_only_fields = ['id', 'is_verified']

class CategorySerializer(serializers.ModelSerializer):
    listings_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description', 'icon_class', 'display_order', 'listings_count']

    def get_listings_count(self, obj):
        return obj.listings.filter(status='ACTIVE').count()

class ListingImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ListingImage
        fields = ['id', 'image', 'image_url', 'is_primary']

    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None


def resolve_product_image_url(title, category_name=None):
    t = (title or '').lower()
    c = (category_name or '').lower()
    rules = [
        (['canon', 'nikon', 'sony alpha', 'dslr', 'camera kit', 'lens', 'camera'], 'https://images.unsplash.com/photo-1516035069371-29a1b244cc32?w=800&auto=format&fit=crop&q=80'),
        (['gopro', 'action cam', 'hero 11', 'action camera'], 'https://images.unsplash.com/photo-1526170375885-4d8ecf77b99f?w=800&auto=format&fit=crop&q=80'),
        (['drone', 'dji', 'mavic', 'mini 3', 'quadcopter'], 'https://images.unsplash.com/photo-1508614589041-895b88991e3e?w=800&auto=format&fit=crop&q=80'),
        (['tv', 'television', 'samsung', 'crystal 4k', 'uhd', 'smart tv', 'oled'], 'https://images.unsplash.com/photo-1593359677879-a4bb92f829d1?w=800&auto=format&fit=crop&q=80'),
        (['guitar', 'yamaha', 'acoustic', 'f310', 'musical'], 'https://images.unsplash.com/photo-1510915361894-db8b60106cb1?w=800&auto=format&fit=crop&q=80'),
        (['keyboard', 'mechanical', 'rgb', 'gaming keyboard', 'keychron'], 'https://images.unsplash.com/photo-1587829741301-dc798b83add3?w=800&auto=format&fit=crop&q=80'),
        (['tent', 'quechua', 'camping', 'backpack', 'trekking', 'groundsheet'], 'https://images.unsplash.com/photo-1504280390367-361c6d9f38f4?w=800&auto=format&fit=crop&q=80'),
        (['bike', 'bicycle', 'cycle', 'mountain bike', 'firefox'], 'https://images.unsplash.com/photo-1485965120184-e220f721d03e?w=800&auto=format&fit=crop&q=80'),
        (['drill', 'bosch', 'impact drill', 'power tool', 'tool kit'], 'https://images.unsplash.com/photo-1504148455328-c376907d081c?w=800&auto=format&fit=crop&q=80'),
        (['monitor', 'ultrasharp', 'dell', '4k display', 'screen', 'u2720q'], 'https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?w=800&auto=format&fit=crop&q=80'),
        (['projector', 'epson', 'home cinema', 'lumens'], 'https://images.unsplash.com/photo-1517604931442-7e0c8ed2963c?w=800&auto=format&fit=crop&q=80'),
        (['book', 'upsc', 'mpsc', 'polity', 'laxmikanth', 'study'], 'https://images.unsplash.com/photo-1497633762265-9d179a990aa6?w=800&auto=format&fit=crop&q=80'),
    ]
    for keywords, url in rules:
        if any(k in t for k in keywords):
            return url
    cat_rules = {
        'cameras & photography': 'https://images.unsplash.com/photo-1516035069371-29a1b244cc32?w=800&auto=format&fit=crop&q=80',
        'electronics': 'https://images.unsplash.com/photo-1550009158-9ebf69173e03?w=800&auto=format&fit=crop&q=80',
        'tools & equipment': 'https://images.unsplash.com/photo-1504148455328-c376907d081c?w=800&auto=format&fit=crop&q=80',
        'travel & camping': 'https://images.unsplash.com/photo-1504280390367-361c6d9f38f4?w=800&auto=format&fit=crop&q=80',
        'sports & fitness': 'https://images.unsplash.com/photo-1485965120184-e220f721d03e?w=800&auto=format&fit=crop&q=80',
        'party & event supplies': 'https://images.unsplash.com/photo-1517604931442-7e0c8ed2963c?w=800&auto=format&fit=crop&q=80',
        'books & study materials': 'https://images.unsplash.com/photo-1497633762265-9d179a990aa6?w=800&auto=format&fit=crop&q=80',
        'musical instruments': 'https://images.unsplash.com/photo-1510915361894-db8b60106cb1?w=800&auto=format&fit=crop&q=80',
    }
    for cat_name, url in cat_rules.items():
        if cat_name in c or c in cat_name:
            return url
    return 'https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=800&auto=format&fit=crop&q=80'

class ListingListSerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    primary_image_url = serializers.SerializerMethodField()
    available_modes = serializers.ListField(source='available_modes_display', read_only=True)

    class Meta:
        model = Listing
        fields = [
            'id', 'title', 'slug', 'description', 'item_condition',
            'city', 'locality', 'pincode', 'status',
            'can_rent', 'can_borrow', 'can_sell',
            'rent_price_per_day', 'rent_price_per_week', 'rent_security_deposit',
            'min_rental_days', 'max_rental_days',
            'is_free_borrow', 'borrow_security_deposit', 'borrow_max_days',
            'sell_price', 'sell_price_negotiable', 'quantity',
            'owner', 'category', 'primary_image_url', 'available_modes',
            'pickup_available', 'delivery_available', 'created_at'
        ]

    def get_primary_image_url(self, obj):
        img = obj.primary_image
        if img and img.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(img.image.url)
            return img.image.url
        cat_name = obj.category.name if obj.category else ''
        return resolve_product_image_url(obj.title, cat_name)

class ListingDetailSerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    images = ListingImageSerializer(many=True, read_only=True)
    available_modes = serializers.ListField(source='available_modes_display', read_only=True)

    class Meta:
        model = Listing
        fields = '__all__'

class RentalBookingSerializer(serializers.ModelSerializer):
    renter = UserSerializer(read_only=True)
    listing_title = serializers.CharField(source='listing.title', read_only=True)
    listing_id = serializers.IntegerField(source='listing.id', read_only=True)
    listing_image_url = serializers.SerializerMethodField()
    owner_username = serializers.CharField(source='listing.owner.username', read_only=True)
    owner_phone = serializers.CharField(source='listing.owner.phone_number', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = RentalBooking
        fields = '__all__'
        read_only_fields = ['booking_reference', 'status', 'created_at', 'updated_at']

    def get_listing_image_url(self, obj):
        if obj.listing:
            img = obj.listing.primary_image
            if img and img.image:
                request = self.context.get('request')
                if request:
                    return request.build_absolute_uri(img.image.url)
                return img.image.url
            cat = obj.listing.category.name if obj.listing.category else ''
            return resolve_product_image_url(obj.listing.title, cat)
        return None

class BorrowRequestSerializer(serializers.ModelSerializer):
    borrower = UserSerializer(read_only=True)
    listing_title = serializers.CharField(source='listing.title', read_only=True)
    listing_id = serializers.IntegerField(source='listing.id', read_only=True)
    owner_username = serializers.CharField(source='listing.owner.username', read_only=True)

    class Meta:
        model = BorrowRequest
        fields = '__all__'
        read_only_fields = ['request_reference', 'status', 'created_at', 'updated_at']

class SalesOrderSerializer(serializers.ModelSerializer):
    buyer = UserSerializer(read_only=True)
    seller = UserSerializer(read_only=True)

    class Meta:
        model = SalesOrder
        fields = '__all__'
        read_only_fields = ['order_number', 'status', 'created_at', 'updated_at']

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = '__all__'

class ReviewSerializer(serializers.ModelSerializer):
    reviewer_name = serializers.CharField(source='reviewer.display_name', read_only=True)
    listing_title = serializers.CharField(source='listing.title', read_only=True)

    class Meta:
        model = Review
        fields = '__all__'
        read_only_fields = ['reviewer', 'created_at', 'updated_at']

class HandoverLogSerializer(serializers.ModelSerializer):
    recorded_by_name = serializers.CharField(source='recorded_by.display_name', read_only=True)

    class Meta:
        model = HandoverLog
        fields = '__all__'
        read_only_fields = ['recorded_by', 'timestamp']

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = '__all__'
