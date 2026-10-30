from decimal import Decimal
from django.core.exceptions import ValidationError
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from .models import Category, Listing

User = get_user_model()


class ListingsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create_user(
            username='seller_one',
            email='seller1@shareloop.in',
            password='Password@123',
            user_type='BUSINESS',
        )
        self.other_user = User.objects.create_user(
            username='other_user',
            email='other@shareloop.in',
            password='Password@123',
            user_type='INDIVIDUAL',
        )
        self.category = Category.objects.create(
            name='Cameras & Lenses',
            slug='cameras-lenses',
            icon_class='bi-camera',
        )
        self.listing = Listing.objects.create(
            owner=self.owner,
            category=self.category,
            title='Canon EOS R5 Mirrorless Camera',
            description='Professional 8K video & 45MP photo camera.',
            item_condition='LIKE_NEW',
            locality='Baner',
            pincode='411045',
            can_rent=True,
            rent_price_per_day=Decimal('2000.00'),
            rent_security_deposit=Decimal('5000.00'),
            can_borrow=False,
            can_sell=True,
            sell_price=Decimal('250000.00'),
            quantity=1,
            status='ACTIVE',
        )

    def test_listing_model_validation_at_least_one_mode(self):
        # A listing with no modes enabled should fail validation
        invalid_listing = Listing(
            owner=self.owner,
            category=self.category,
            title='Broken Listing',
            description='No mode selected',
            locality='Kothrud',
            pincode='411038',
            can_rent=False,
            can_borrow=False,
            can_sell=False,
        )
        with self.assertRaises(ValidationError):
            invalid_listing.clean()

    def test_invalid_negative_price_rejection(self):
        invalid_listing = Listing(
            owner=self.owner,
            category=self.category,
            title='Negative Rent',
            description='Invalid rent',
            locality='Kothrud',
            pincode='411038',
            can_rent=True,
            rent_price_per_day=Decimal('-100.00'),
        )
        with self.assertRaises(ValidationError):
            invalid_listing.clean()

    def test_browse_search_and_filter(self):
        # Search by keyword
        response = self.client.get(reverse('listings:browse') + '?q=Canon')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Canon EOS R5')

        # Filter by locality
        response = self.client.get(reverse('listings:browse') + '?locality=Baner')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Canon EOS R5')

        # Filter by non-matching locality
        response = self.client.get(reverse('listings:browse') + '?locality=Hadapsar')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Canon EOS R5')

    def test_unauthorized_edit_rejection(self):
        # other_user tries to edit owner's listing
        self.client.login(username='other_user', password='Password@123')
        response = self.client.post(reverse('listings:edit', args=[self.listing.id]), {
            'title': 'Hacked Title',
            'category': self.category.id,
            'description': 'Changed',
            'item_condition': 'GOOD',
            'locality': 'Baner',
            'pincode': '411045',
            'can_sell': True,
            'sell_price': 1000,
            'quantity': 1,
        })
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.title, 'Canon EOS R5 Mirrorless Camera')
