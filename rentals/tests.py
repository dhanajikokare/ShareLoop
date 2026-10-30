from datetime import date, timedelta
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from listings.models import Category, Listing
from .models import RentalBooking

User = get_user_model()


class RentalsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create_user(username='renter_owner', password='Password@123', email='o@test.in')
        self.renter = User.objects.create_user(username='renter_user', password='Password@123', email='r@test.in')
        self.cat = Category.objects.create(name='Camping Gear', slug='camping-gear')

        self.listing = Listing.objects.create(
            owner=self.owner,
            category=self.cat,
            title='4-Person Camping Tent',
            description='Waterproof trekking tent',
            locality='Kothrud',
            pincode='411038',
            can_rent=True,
            rent_price_per_day=Decimal('500.00'),
            rent_security_deposit=Decimal('1000.00'),
            min_rental_days=1,
            max_rental_days=10,
            status='ACTIVE',
        )

    def test_cost_calculation(self):
        start = date(2026, 11, 1)
        end = date(2026, 11, 3)  # 3 days inclusive
        calc = RentalBooking.calculate_cost(self.listing, start, end)

        self.assertEqual(calc['days'], 3)
        self.assertEqual(calc['rental_fee'], Decimal('1500.00'))
        self.assertEqual(calc['security_deposit'], Decimal('1000.00'))
        # 5% platform fee on 1500 = 75.00
        self.assertEqual(calc['platform_fee'], Decimal('75.00'))
        self.assertEqual(calc['total_amount'], Decimal('2575.00'))

    def test_overlapping_booking_rejection(self):
        # Create an accepted booking for Nov 1 to Nov 5
        start1 = date(2026, 11, 1)
        end1 = date(2026, 11, 5)
        RentalBooking.objects.create(
            listing=self.listing,
            renter=self.renter,
            start_date=start1,
            end_date=end1,
            daily_rate=Decimal('500.00'),
            rental_fee=Decimal('2500.00'),
            total_amount=Decimal('3625.00'),
            status='CONFIRMED',
        )

        # Check overlapping dates (Nov 3 to Nov 7)
        is_avail, reason = self.listing.is_available_for_dates(date(2026, 11, 3), date(2026, 11, 7))
        self.assertFalse(is_avail)
        self.assertIn('already booked', reason)

        # Non-overlapping dates (Nov 10 to Nov 15) should be available
        is_avail2, _ = self.listing.is_available_for_dates(date(2026, 11, 10), date(2026, 11, 15))
        self.assertTrue(is_avail2)

    def test_cannot_rent_own_item(self):
        self.client.login(username='renter_owner', password='Password@123')
        response = self.client.post(reverse('rentals:create_booking', args=[self.listing.id]), {
            'start_date': '2026-11-10',
            'end_date': '2026-11-12',
        })
        self.assertEqual(RentalBooking.objects.count(), 0)

    def test_owner_acceptance_flow(self):
        booking = RentalBooking.objects.create(
            listing=self.listing,
            renter=self.renter,
            start_date=date(2026, 11, 10),
            end_date=date(2026, 11, 12),
            daily_rate=Decimal('500.00'),
            rental_fee=Decimal('1500.00'),
            total_amount=Decimal('2575.00'),
            status='PENDING',
        )

        # Non-owner cannot accept
        self.client.login(username='renter_user', password='Password@123')
        self.client.post(reverse('rentals:accept_rental', args=[booking.id]))
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'PENDING')

        # Owner can accept
        self.client.login(username='renter_owner', password='Password@123')
        self.client.post(reverse('rentals:accept_rental', args=[booking.id]))
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'ACCEPTED')
