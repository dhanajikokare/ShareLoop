from datetime import date
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from listings.models import Category, Listing
from rentals.models import RentalBooking
from .models import HandoverLog, Review

User = get_user_model()


class ReviewsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create_user(username='rev_owner', password='Password@123', email='ro@test.in')
        self.renter = User.objects.create_user(username='rev_renter', password='Password@123', email='rr@test.in')
        self.stranger = User.objects.create_user(username='stranger', password='Password@123', email='s@test.in')

        self.cat = Category.objects.create(name='Instruments', slug='instruments')
        self.listing = Listing.objects.create(
            owner=self.owner,
            category=self.cat,
            title='Guitar',
            locality='Kothrud',
            pincode='411038',
            can_rent=True,
            rent_price_per_day=Decimal('300.00'),
            status='ACTIVE',
        )

        self.booking = RentalBooking.objects.create(
            listing=self.listing,
            renter=self.renter,
            start_date=date(2026, 11, 1),
            end_date=date(2026, 11, 2),
            daily_rate=Decimal('300.00'),
            rental_fee=Decimal('600.00'),
            total_amount=Decimal('630.00'),
            status='COMPLETED',
        )

    def test_handover_evidence_access_control(self):
        log = HandoverLog.objects.create(
            log_type='RENTAL_HANDOVER',
            recorded_by=self.owner,
            rental_booking=self.booking,
            item_condition='GOOD',
            notes='All guitar strings intact.',
        )

        # Participants can access
        self.assertTrue(log.can_access(self.owner))
        self.assertTrue(log.can_access(self.renter))

        # Stranger cannot access
        self.assertFalse(log.can_access(self.stranger))

    def test_duplicate_review_prevention(self):
        Review.objects.create(
            reviewer=self.renter,
            reviewee=self.owner,
            listing=self.listing,
            transaction_type='RENTAL',
            rental_booking=self.booking,
            rating=5,
            comment='Guitar was in pristine condition, great lender!',
        )

        # Attempting second review for same transaction
        duplicate_review = Review(
            reviewer=self.renter,
            reviewee=self.owner,
            listing=self.listing,
            transaction_type='RENTAL',
            rental_booking=self.booking,
            rating=4,
            comment='Another review',
        )
        with self.assertRaises(ValidationError):
            duplicate_review.clean()

    def test_self_review_prevention(self):
        self_rev = Review(
            reviewer=self.owner,
            reviewee=self.owner,
            listing=self.listing,
            transaction_type='RENTAL',
            rental_booking=self.booking,
            rating=5,
            comment='I am reviewing myself',
        )
        with self.assertRaises(ValidationError):
            self_rev.clean()
