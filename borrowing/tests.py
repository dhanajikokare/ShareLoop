from datetime import date
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from listings.models import Category, Listing
from .models import BorrowRequest

User = get_user_model()


class BorrowingTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create_user(username='book_owner', password='Password@123', email='bo@test.in')
        self.borrower = User.objects.create_user(username='book_borrower', password='Password@123', email='bb@test.in')
        self.cat = Category.objects.create(name='Books', slug='books')

        self.listing = Listing.objects.create(
            owner=self.owner,
            category=self.cat,
            title='Python Programming Book',
            description='Comprehensive reference',
            locality='Shivaji Nagar',
            pincode='411005',
            can_borrow=True,
            is_free_borrow=True,
            borrow_max_days=14,
            status='ACTIVE',
        )

    def test_free_borrow_request_creation(self):
        self.client.login(username='book_borrower', password='Password@123')
        response = self.client.post(reverse('borrowing:create_request', args=[self.listing.id]), {
            'start_date': '2026-11-01',
            'end_date': '2026-11-07',
            'borrower_message': 'Preparing for coding interviews in Pune.',
            'agreed_to_terms': 'on',
        })
        self.assertEqual(response.status_code, 302)

        req = BorrowRequest.objects.get(listing=self.listing)
        self.assertTrue(req.is_free)
        self.assertEqual(req.status, 'PENDING')
        self.assertEqual(req.total_days, 7)

    def test_borrow_duration_limit_enforced(self):
        # Max is 14 days, attempting 20 days
        self.client.login(username='book_borrower', password='Password@123')
        response = self.client.post(reverse('borrowing:create_request', args=[self.listing.id]), {
            'start_date': '2026-11-01',
            'end_date': '2026-11-20',
            'borrower_message': 'Want for long time',
            'agreed_to_terms': 'on',
        })
        self.assertEqual(BorrowRequest.objects.count(), 0)
