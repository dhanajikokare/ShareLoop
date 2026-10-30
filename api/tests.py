from decimal import Decimal
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import User
from listings.models import Category, Listing
from rentals.models import RentalBooking
from borrowing.models import BorrowRequest
from orders.models import SalesOrder
from api.models import Conversation, ChatMessage, Favorite

class ShareLoopAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Users
        self.seller = User.objects.create_user(
            username='api_seller',
            email='seller@shareloop.in',
            password='Password@123',
            user_type='BUSINESS',
            phone_number='9876543210'
        )

        self.buyer = User.objects.create_user(
            username='api_buyer',
            email='buyer@shareloop.in',
            password='Password@123',
            user_type='INDIVIDUAL',
            phone_number='9876543211'
        )

        # Category
        self.category = Category.objects.create(name='Electronics', display_order=1)

        # Multi-mode Listing
        self.listing = Listing.objects.create(
            owner=self.seller,
            category=self.category,
            title='Canon EOS R5 Mirrorless Camera',
            description='High resolution professional camera',
            item_condition='LIKE_NEW',
            city='Pune',
            locality='Kothrud',
            pincode='411038',
            can_rent=True,
            rent_price_per_day=Decimal('1000.00'),
            rent_security_deposit=Decimal('5000.00'),
            min_rental_days=1,
            max_rental_days=14,
            can_borrow=True,
            is_free_borrow=True,
            borrow_max_days=5,
            can_sell=True,
            sell_price=Decimal('180000.00'),
            quantity=2,
            status='ACTIVE',
            moderation_status='APPROVED'
        )

    def test_01_api_login(self):
        res = self.client.post('/api/v1/auth/login/', {
            'username': 'api_buyer',
            'password': 'Password@123'
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('token', res.data)
        self.assertEqual(res.data['user']['username'], 'api_buyer')

    def test_02_api_categories(self):
        res = self.client.get('/api/v1/categories/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(res.data), 1)

    def test_03_api_listings_feed_and_filters(self):
        res = self.client.get('/api/v1/listings/?mode=rent')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(any(l['title'] == self.listing.title for l in res.data))

        res_loc = self.client.get('/api/v1/listings/?locality=Kothrud')
        self.assertEqual(res_loc.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(res_loc.data), 1)

    def test_04_api_listing_detail(self):
        res = self.client.get(f'/api/v1/listings/{self.listing.id}/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['title'], self.listing.title)
        self.assertIn('reviews', res.data)

    def test_05_api_rental_booking(self):
        login_res = self.client.post('/api/v1/auth/login/', {'username': 'api_buyer', 'password': 'Password@123'}, format='json')
        token = login_res.data['token']
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')

        res = self.client.post('/api/v1/rentals/book/', {
            'listing_id': self.listing.id,
            'start_date': '2026-11-01',
            'end_date': '2026-11-03',
            'message': 'Need for client shoot'
        }, format='json')

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertIn('booking_reference', res.data)
        self.assertEqual(res.data['total_days'], 3)
        self.assertEqual(Decimal(res.data['daily_rate']), Decimal('1000.00'))

    def test_06_api_free_borrow_request(self):
        login_res = self.client.post('/api/v1/auth/login/', {'username': 'api_buyer', 'password': 'Password@123'}, format='json')
        token = login_res.data['token']
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')

        res = self.client.post('/api/v1/borrowing/request/', {
            'listing_id': self.listing.id,
            'start_date': '2026-11-10',
            'end_date': '2026-11-12',
            'message': 'Will use carefully for student film project'
        }, format='json')

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data['is_free'])

    def test_07_api_sales_order_atomic(self):
        login_res = self.client.post('/api/v1/auth/login/', {'username': 'api_buyer', 'password': 'Password@123'}, format='json')
        token = login_res.data['token']
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')

        res = self.client.post('/api/v1/orders/create/', {
            'listing_id': self.listing.id,
            'fulfillment_type': 'PICKUP',
            'delivery_address': 'Kothrud, Pune',
        }, format='json')

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.quantity, 1)

    def test_08_api_chat_flow(self):
        login_res = self.client.post('/api/v1/auth/login/', {'username': 'api_buyer', 'password': 'Password@123'}, format='json')
        token = login_res.data['token']
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')

        # Start conversation
        res = self.client.post('/api/v1/chats/', {
            'other_user_id': self.seller.id,
            'listing_id': self.listing.id,
            'message': 'Hi, is this available this weekend?'
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        conv_id = res.data['id']

        # Send message
        msg_res = self.client.post(f'/api/v1/chats/{conv_id}/messages/', {
            'text': 'Also do you have extra batteries?'
        }, format='json')
        self.assertEqual(msg_res.status_code, status.HTTP_201_CREATED)

    def test_09_api_favorites(self):
        login_res = self.client.post('/api/v1/auth/login/', {'username': 'api_buyer', 'password': 'Password@123'}, format='json')
        token = login_res.data['token']
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')

        res = self.client.post('/api/v1/favorites/', {'listing_id': self.listing.id}, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data['is_favorited'])

        # Toggle off
        res_off = self.client.post('/api/v1/favorites/', {'listing_id': self.listing.id}, format='json')
        self.assertFalse(res_off.data['is_favorited'])
