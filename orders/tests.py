from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from listings.models import Category, Listing
from .models import SalesOrder

User = get_user_model()


class OrdersTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.seller = User.objects.create_user(username='cycle_seller', password='Password@123', email='cs@test.in')
        self.buyer = User.objects.create_user(username='cycle_buyer', password='Password@123', email='cb@test.in')
        self.cat = Category.objects.create(name='Sports', slug='sports')

        self.listing = Listing.objects.create(
            owner=self.seller,
            category=self.cat,
            title='Commuter Bicycle',
            description='City cycle in great condition',
            locality='Aundh',
            pincode='411007',
            can_sell=True,
            sell_price=Decimal('6000.00'),
            quantity=1,
            status='ACTIVE',
        )

    def test_order_creation_deducts_inventory_and_marks_sold(self):
        self.client.login(username='cycle_buyer', password='Password@123')
        response = self.client.post(reverse('orders:create_order', args=[self.listing.id]), {
            'quantity': 1,
            'fulfillment_type': 'PICKUP',
            'delivery_address': 'Aundh Main Road',
        })
        self.assertEqual(response.status_code, 302)

        order = SalesOrder.objects.get(buyer=self.buyer)
        self.assertEqual(order.items_total, Decimal('6000.00'))
        self.assertEqual(order.platform_fee, Decimal('300.00'))  # 5%
        self.assertEqual(order.total_amount, Decimal('6300.00'))

        self.listing.refresh_from_db()
        self.assertEqual(self.listing.quantity, 0)
        self.assertEqual(self.listing.status, 'SOLD')

    def test_overselling_prevention(self):
        # Attempting to buy 2 when only 1 is in stock
        self.client.login(username='cycle_buyer', password='Password@123')
        response = self.client.post(reverse('orders:create_order', args=[self.listing.id]), {
            'quantity': 2,
            'fulfillment_type': 'PICKUP',
        })
        self.assertEqual(SalesOrder.objects.count(), 0)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.quantity, 1)
        self.assertEqual(self.listing.status, 'ACTIVE')
