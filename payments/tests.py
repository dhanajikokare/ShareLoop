import json
from decimal import Decimal
from datetime import date
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from listings.models import Category, Listing
from rentals.models import RentalBooking
from .models import Payment, WebhookEvent

User = get_user_model()


class PaymentsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create_user(username='pay_owner', password='Password@123', email='po@test.in')
        self.renter = User.objects.create_user(username='pay_renter', password='Password@123', email='pr@test.in')
        self.cat = Category.objects.create(name='Audio', slug='audio')

        self.listing = Listing.objects.create(
            owner=self.owner,
            category=self.cat,
            title='Studio Microphone',
            locality='Koregaon Park',
            pincode='411001',
            can_rent=True,
            rent_price_per_day=Decimal('400.00'),
            rent_security_deposit=Decimal('500.00'),
            status='ACTIVE',
        )

        self.booking = RentalBooking.objects.create(
            listing=self.listing,
            renter=self.renter,
            start_date=date(2026, 11, 1),
            end_date=date(2026, 11, 2),
            daily_rate=Decimal('400.00'),
            rental_fee=Decimal('800.00'),
            platform_fee=Decimal('40.00'),
            security_deposit=Decimal('500.00'),
            total_amount=Decimal('1340.00'),
            status='ACCEPTED',
        )

    def test_payment_verification_and_booking_confirmation(self):
        payment = Payment.objects.create(
            user=self.renter,
            payment_for='RENTAL',
            rental_booking=self.booking,
            amount=self.booking.total_amount,
            status='PENDING',
        )

        self.client.login(username='pay_renter', password='Password@123')
        response = self.client.post(reverse('payments:verify_payment'), {
            'payment_id': payment.id,
            'razorpay_payment_id': 'pay_test_123456',
            'razorpay_order_id': 'order_test_123',
            'razorpay_signature': 'valid_sig',
            'is_simulated': 'true',
        })
        self.assertEqual(response.status_code, 302)

        payment.refresh_from_db()
        self.assertEqual(payment.status, 'SUCCESS')
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, 'CONFIRMED')

    def test_webhook_idempotency(self):
        event_payload = json.dumps({
            'event_id': 'evt_test_unique_999',
            'event': 'payment.captured',
            'payload': {
                'payment': {
                    'entity': {
                        'id': 'pay_gateway_888',
                        'order_id': 'order_dummy',
                        'amount': 134000,
                    }
                }
            }
        })

        # Send webhook first time
        response1 = self.client.post(
            reverse('payments:razorpay_webhook'),
            data=event_payload,
            content_type='application/json'
        )
        self.assertEqual(response1.status_code, 200)
        self.assertEqual(response1.json()['status'], 'success')
        self.assertEqual(WebhookEvent.objects.filter(event_id='evt_test_unique_999').count(), 1)

        # Send same webhook second time (duplicate event delivery)
        response2 = self.client.post(
            reverse('payments:razorpay_webhook'),
            data=event_payload,
            content_type='application/json'
        )
        self.assertEqual(response2.status_code, 200)
        self.assertEqual(response2.json()['status'], 'already_processed')
        # Ensure still only 1 record exists
        self.assertEqual(WebhookEvent.objects.filter(event_id='evt_test_unique_999').count(), 1)
