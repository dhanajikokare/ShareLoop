import json
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core import mail
from django.core.exceptions import ValidationError
from django.utils import timezone

from accounts.forms import RegistrationForm
from accounts.models import OTPVerification
from accounts.validators import validate_and_normalize_indian_phone, validate_email_format
from accounts.otp_service import (
    send_registration_email_otp,
    verify_registration_email_otp,
    send_password_reset_otp,
    verify_password_reset_otp,
    execute_password_reset,
)

User = get_user_model()


def create_verified_registration_token(email):
    """Helper to generate an active verified OTP record for testing registration."""
    rec = OTPVerification.objects.create(
        purpose=OTPVerification.PURPOSE_REGISTRATION_EMAIL,
        identifier=email.strip().lower(),
        otp_hash='preverified_hash',
        expires_at=timezone.now() + timedelta(minutes=15),
        is_verified=True,
        is_used=False,
    )
    return rec.issue_reset_token()


class AccountsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='pune_tester',
            email='tester@pune.in',
            password='Password@123',
            user_type='INDIVIDUAL',
            phone_number='+919876543210',
        )

    def test_user_registration(self):
        token = create_verified_registration_token('amit@pune.in')
        response = self.client.post(reverse('accounts:register'), {
            'username': 'new_user_pune',
            'first_name': 'Amit',
            'last_name': 'Joshi',
            'email': 'amit@pune.in',
            'phone_number': '9822000000',
            'user_type': 'BUSINESS',
            'shop_name': 'Amit Gear Rentals',
            'password1': 'Password@123',
            'password2': 'Password@123',
            'email_verification_token': token,
        })
        self.assertEqual(response.status_code, 302)
        new_user = User.objects.get(username='new_user_pune')
        self.assertTrue(new_user.is_business_seller)
        self.assertEqual(new_user.profile.shop_name, 'Amit Gear Rentals')
        self.assertEqual(new_user.phone_number, '+919822000000')

    def test_user_login_and_logout(self):
        # Successful login
        response = self.client.post(reverse('accounts:login'), {
            'username': 'pune_tester',
            'password': 'Password@123',
        })
        self.assertEqual(response.status_code, 302)

        # Logout
        response = self.client.post(reverse('accounts:logout'))
        self.assertEqual(response.status_code, 302)

    def test_unauthorized_dashboard_redirect(self):
        # Guest accessing dashboard should be redirected to login
        response = self.client.get(reverse('accounts:dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response.url)

    def test_authorized_dashboard_access(self):
        self.client.login(username='pune_tester', password='Password@123')
        response = self.client.get(reverse('accounts:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Welcome, pune_tester')


class RegistrationValidationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.existing_user = User.objects.create_user(
            username='existing_user',
            email='existing@shareloop.in',
            password='SecurePassword@123',
            phone_number='+919876543210',
            user_type='INDIVIDUAL',
        )

    def test_01_empty_form_submission(self):
        """Submitting an empty registration form must fail and show field errors."""
        response = self.client.post(reverse('accounts:register'), {})
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertFalse(form.is_valid())
        self.assertIn('first_name', form.errors)
        self.assertIn('last_name', form.errors)
        self.assertIn('username', form.errors)
        self.assertIn('email', form.errors)
        self.assertIn('phone_number', form.errors)
        self.assertIn('password1', form.errors)

    def test_02_valid_and_invalid_email_addresses(self):
        """Valid emails are accepted & trimmed; invalid/malformed emails are rejected."""
        valid_emails = [
            'pune.user@shareloop.in',
            'test+tag@example.com',
            '  spaced@pune.gov.in  ',
        ]
        for email in valid_emails:
            cleaned = validate_email_format(email)
            self.assertEqual(cleaned, email.strip().lower())

        invalid_emails = [
            '',
            'plainaddress',
            'missingdomain@',
            '@missinguser.com',
            'user@.com',
            'user@domain',
            'user@domain.c',
            'user space@domain.com',
            'user@domain..com',
        ]
        for email in invalid_emails:
            with self.assertRaises(ValidationError):
                validate_email_format(email)

    def test_03_indian_phone_numbers_with_and_without_plus91(self):
        """Accepts various valid Indian mobile number formats and normalizes to +91XXXXXXXXXX."""
        valid_formats = [
            ('9876543211', '+919876543211'),
            ('+919876543211', '+919876543211'),
            ('+91 98765 43211', '+919876543211'),
            ('+91-98765-43211', '+919876543211'),
            ('09876543211', '+919876543211'),
            ('919876543211', '+919876543211'),
            ('  +91 98765 43211  ', '+919876543211'),
            ('6123456789', '+916123456789'),
            ('7123456789', '+917123456789'),
            ('8123456789', '+918123456789'),
        ]
        for raw, expected in valid_formats:
            normalized = validate_and_normalize_indian_phone(raw)
            self.assertEqual(normalized, expected, f"Failed for format: {raw}")

    def test_04_phone_numbers_with_invalid_lengths_or_starting_digits(self):
        """Rejects numbers with invalid length, invalid starting digits (1-5), non-Indian country codes, or letters."""
        invalid_phones = [
            ('', 'Phone number is required.'),
            ('98765', 'exactly 10 mobile digits'),
            ('987654321', 'exactly 10 mobile digits'),
            ('9876543210123', 'exactly 10 mobile digits'),
            ('1234567890', 'must begin with 6, 7, 8, or 9'),
            ('5876543210', 'must begin with 6, 7, 8, or 9'),
            ('2345678901', 'must begin with 6, 7, 8, or 9'),
            ('+12125551234', 'Only Indian phone numbers (+91) are supported'),
            ('98765abcde', 'only digits and valid separators'),
            ('98765@43210', 'only digits and valid separators'),
        ]
        for phone, expected_err in invalid_phones:
            with self.assertRaises(ValidationError) as ctx:
                validate_and_normalize_indian_phone(phone)
            self.assertTrue(any(expected_err in msg for msg in ctx.exception.messages))

    def test_05_individual_user_registration_without_business_name(self):
        """Individual user registration must succeed with verified email even without a shop name."""
        token = create_verified_registration_token('rohan.patil@pune.in')
        response = self.client.post(reverse('accounts:register'), {
            'username': 'individual_user_1',
            'first_name': 'Rohan',
            'last_name': 'Patil',
            'email': 'rohan.patil@pune.in',
            'phone_number': '9822112233',
            'user_type': 'INDIVIDUAL',
            'shop_name': '',
            'password1': 'StrongPass@2026',
            'password2': 'StrongPass@2026',
            'email_verification_token': token,
        })
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username='individual_user_1')
        self.assertEqual(user.user_type, 'INDIVIDUAL')
        self.assertFalse(user.is_business_seller)
        self.assertEqual(user.phone_number, '+919822112233')

    def test_06_business_seller_registration_without_business_name(self):
        """Business seller registration MUST fail if shop/business name is omitted."""
        token = create_verified_registration_token('pooja@pune.in')
        response = self.client.post(reverse('accounts:register'), {
            'username': 'business_user_missing_shop',
            'first_name': 'Pooja',
            'last_name': 'Kulkarni',
            'email': 'pooja@pune.in',
            'phone_number': '9822445566',
            'user_type': 'BUSINESS',
            'shop_name': '',
            'password1': 'StrongPass@2026',
            'password2': 'StrongPass@2026',
            'email_verification_token': token,
        })
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertFalse(form.is_valid())
        self.assertIn('shop_name', form.errors)
        self.assertIn('required for Business Sellers', form.errors['shop_name'][0])

    def test_07_business_name_containing_only_spaces_or_exceeding_max_length(self):
        """Business names with only whitespace must fail, and names > 100 characters must be rejected."""
        token1 = create_verified_registration_token('rahul@pune.in')
        response = self.client.post(reverse('accounts:register'), {
            'username': 'business_spaces',
            'first_name': 'Rahul',
            'last_name': 'Deshmukh',
            'email': 'rahul@pune.in',
            'phone_number': '9822778899',
            'user_type': 'BUSINESS',
            'shop_name': '     ',
            'password1': 'StrongPass@2026',
            'password2': 'StrongPass@2026',
            'email_verification_token': token1,
        })
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertFalse(form.is_valid())
        self.assertIn('shop_name', form.errors)

        token2 = create_verified_registration_token('rahul2@pune.in')
        response_too_long = self.client.post(reverse('accounts:register'), {
            'username': 'business_toolong',
            'first_name': 'Rahul',
            'last_name': 'Deshmukh',
            'email': 'rahul2@pune.in',
            'phone_number': '9822778800',
            'user_type': 'BUSINESS',
            'shop_name': 'A' * 101,
            'password1': 'StrongPass@2026',
            'password2': 'StrongPass@2026',
            'email_verification_token': token2,
        })
        self.assertEqual(response_too_long.status_code, 200)
        self.assertIn('shop_name', response_too_long.context['form'].errors)

    def test_08_password_validation_length_whitespace_and_integrity(self):
        """Passwords < 8 chars, > 128 chars, or whitespace-only must be rejected."""
        form_short = RegistrationForm(data={'password1': 'Short1', 'password2': 'Short1'})
        self.assertFalse(form_short.is_valid())
        self.assertIn('password1', form_short.errors)

        form_long = RegistrationForm(data={'password1': 'P' * 129, 'password2': 'P' * 129})
        self.assertFalse(form_long.is_valid())
        self.assertIn('password1', form_long.errors)

        form_whitespace = RegistrationForm(data={'password1': '        ', 'password2': '        '})
        self.assertFalse(form_whitespace.is_valid())
        self.assertIn('password1', form_whitespace.errors)

        form_mismatch = RegistrationForm(data={'password1': 'Password123', 'password2': 'DifferentPass123'})
        self.assertFalse(form_mismatch.is_valid())
        self.assertIn('password2', form_mismatch.errors)

    def test_09_duplicate_email_and_phone_registration(self):
        """Prevent duplicate account registration using email and phone uniqueness rules."""
        token1 = create_verified_registration_token('EXISTING@SHARELOOP.IN')
        response_dup_email = self.client.post(reverse('accounts:register'), {
            'username': 'unique_user_email_test',
            'first_name': 'Vikram',
            'last_name': 'Gaikwad',
            'email': 'EXISTING@SHARELOOP.IN',
            'phone_number': '9823999999',
            'user_type': 'INDIVIDUAL',
            'password1': 'StrongPass@2026',
            'password2': 'StrongPass@2026',
            'email_verification_token': token1,
        })
        self.assertEqual(response_dup_email.status_code, 200)
        self.assertIn('email', response_dup_email.context['form'].errors)

        token2 = create_verified_registration_token('vikram.unique@shareloop.in')
        response_dup_phone = self.client.post(reverse('accounts:register'), {
            'username': 'unique_user_phone_test',
            'first_name': 'Vikram',
            'last_name': 'Gaikwad',
            'email': 'vikram.unique@shareloop.in',
            'phone_number': '9876543210',
            'user_type': 'INDIVIDUAL',
            'password1': 'StrongPass@2026',
            'password2': 'StrongPass@2026',
            'email_verification_token': token2,
        })
        self.assertEqual(response_dup_phone.status_code, 200)
        self.assertIn('phone_number', response_dup_phone.context['form'].errors)

    def test_10_backend_validation_errors_structured_ajax_response(self):
        """AJAX requests receive HTTP 400 with structured JSON error responses on validation failure."""
        response = self.client.post(
            reverse('accounts:register'),
            data={'email': 'invalid-email', 'phone_number': '123'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 400)
        json_data = response.json()
        self.assertFalse(json_data['success'])
        self.assertIn('errors', json_data)

    def test_11_successful_registration_for_both_account_roles(self):
        """Both Individual and Business roles register successfully with verified emails."""
        token_ind = create_verified_registration_token('sunita.more@pune.in')
        res_ind = self.client.post(reverse('accounts:register'), {
            'username': 'ind_success',
            'first_name': 'Sunita',
            'last_name': 'More',
            'email': 'sunita.more@pune.in',
            'phone_number': '+91 98223 34455',
            'user_type': 'INDIVIDUAL',
            'shop_name': '',
            'password1': 'SunitaPass@2026',
            'password2': 'SunitaPass@2026',
            'email_verification_token': token_ind,
        })
        self.assertEqual(res_ind.status_code, 302)
        user_ind = User.objects.get(username='ind_success')
        self.assertEqual(user_ind.user_type, 'INDIVIDUAL')
        self.assertEqual(user_ind.phone_number, '+919822334455')
        self.assertTrue(user_ind.check_password('SunitaPass@2026'))

        self.client.logout()

        token_biz = create_verified_registration_token('ganesh.shinde@pune.in')
        res_biz = self.client.post(reverse('accounts:register'), {
            'username': 'biz_success',
            'first_name': 'Ganesh',
            'last_name': 'Shinde',
            'email': 'ganesh.shinde@pune.in',
            'phone_number': '98228 89900',
            'user_type': 'BUSINESS',
            'shop_name': 'Kothrud Tool Works',
            'password1': 'GaneshPass@2026',
            'password2': 'GaneshPass@2026',
            'email_verification_token': token_biz,
        })
        self.assertEqual(res_biz.status_code, 302)
        user_biz = User.objects.get(username='biz_success')
        self.assertEqual(user_biz.user_type, 'BUSINESS')
        self.assertTrue(user_biz.is_business_seller)
        self.assertEqual(user_biz.phone_number, '+919822889900')


class EmailVerificationAndOTPTests(TestCase):
    """
    Tests for Feature 1: Registration Email OTP Verification:
      - Valid and invalid email handling
      - Cryptographic OTP generation & delivery via configured email provider
      - Verification attempts tracking and 5-attempt lockout
      - 5-minute expiry enforcement
      - 60-second cooldown enforcement
      - Registration strictly blocked without prior email OTP verification
      - Single-use token invalidation
    """
    def setUp(self):
        self.client = Client()
        mail.outbox = []

    def test_01_registration_email_otp_send_and_verify_success(self):
        """User requests email OTP, receives email in outbox, verifies OTP, and successfully registers."""
        # 1. Send OTP
        res_send = self.client.post(
            reverse('accounts:register_send_email_otp'),
            data=json.dumps({'email': 'new.user@pune.in'}),
            content_type='application/json'
        )
        self.assertEqual(res_send.status_code, 200)
        data = res_send.json()
        self.assertTrue(data['success'])
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Your ShareLoop Verification Code', mail.outbox[0].subject)

        # Extract OTP from email body
        otp_body = mail.outbox[0].body
        import re
        otp_match = re.search(r'\b\d{6}\b', otp_body)
        self.assertIsNotNone(otp_match)
        otp = otp_match.group(0)

        # 2. Verify OTP with incorrect code -> fails
        res_wrong = self.client.post(
            reverse('accounts:register_verify_email_otp'),
            data=json.dumps({'email': 'new.user@pune.in', 'otp': '000000'}),
            content_type='application/json'
        )
        self.assertEqual(res_wrong.status_code, 400)
        self.assertFalse(res_wrong.json()['success'])

        # 3. Verify OTP with correct code -> succeeds and yields token
        res_correct = self.client.post(
            reverse('accounts:register_verify_email_otp'),
            data=json.dumps({'email': 'new.user@pune.in', 'otp': otp}),
            content_type='application/json'
        )
        self.assertEqual(res_correct.status_code, 200)
        ver_token = res_correct.json()['verification_token']
        self.assertTrue(ver_token)

        # 4. Registration with token succeeds
        res_reg = self.client.post(reverse('accounts:register'), {
            'username': 'registered_via_otp',
            'first_name': 'Nikhil',
            'last_name': 'Kamble',
            'email': 'new.user@pune.in',
            'phone_number': '9822331100',
            'user_type': 'INDIVIDUAL',
            'password1': 'SafePass@123',
            'password2': 'SafePass@123',
            'email_verification_token': ver_token,
        })
        self.assertEqual(res_reg.status_code, 302)
        user = User.objects.get(username='registered_via_otp')
        self.assertEqual(user.email, 'new.user@pune.in')

        # Log out user before testing token reuse
        self.client.logout()

        # 5. Attempting to register again with same token is rejected
        res_reuse = self.client.post(reverse('accounts:register'), {
            'username': 'registered_again',
            'first_name': 'Nikhil',
            'last_name': 'Kamble',
            'email': 'new.user@pune.in',
            'phone_number': '9822331101',
            'user_type': 'INDIVIDUAL',
            'password1': 'SafePass@123',
            'password2': 'SafePass@123',
            'email_verification_token': ver_token,
        })
        self.assertEqual(res_reuse.status_code, 200)

    def test_02_unverified_email_cannot_register(self):
        """Unverified email addresses are strictly blocked from registration by backend validation."""
        response = self.client.post(reverse('accounts:register'), {
            'username': 'unverified_user',
            'first_name': 'Ramesh',
            'last_name': 'Pawar',
            'email': 'unverified@pune.in',
            'phone_number': '9822119988',
            'user_type': 'INDIVIDUAL',
            'password1': 'SafePass@123',
            'password2': 'SafePass@123',
        })
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)
        self.assertIn('verify your email address', form.errors['email'][0])

    def test_03_registration_email_otp_max_attempts(self):
        """Entering incorrect OTP 5 times locks the verification code."""
        send_registration_email_otp('locked.out@pune.in')
        for i in range(5):
            res = self.client.post(
                reverse('accounts:register_verify_email_otp'),
                data=json.dumps({'email': 'locked.out@pune.in', 'otp': '999999'}),
                content_type='application/json'
            )
            self.assertEqual(res.status_code, 400)

        # 6th attempt fails with maximum attempts exceeded
        res_6th = self.client.post(
            reverse('accounts:register_verify_email_otp'),
            data=json.dumps({'email': 'locked.out@pune.in', 'otp': '999999'}),
            content_type='application/json'
        )
        self.assertEqual(res_6th.status_code, 400)
        self.assertIn('Maximum verification attempts exceeded', res_6th.json()['error'])

    def test_04_registration_email_otp_expiry(self):
        """Expired OTPs cannot be verified."""
        send_registration_email_otp('expired.user@pune.in')
        otp_rec = OTPVerification.objects.filter(identifier='expired.user@pune.in').first()
        otp_rec.expires_at = timezone.now() - timedelta(minutes=1)
        otp_rec.save()

        res = self.client.post(
            reverse('accounts:register_verify_email_otp'),
            data=json.dumps({'email': 'expired.user@pune.in', 'otp': '123456'}),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn('expired', res.json()['error'].lower())

    def test_05_registration_email_otp_cooldown(self):
        """Requesting OTPs too quickly enforces the 60-second cooldown."""
        res1 = self.client.post(
            reverse('accounts:register_send_email_otp'),
            data=json.dumps({'email': 'cooldown.user@pune.in'}),
            content_type='application/json'
        )
        self.assertEqual(res1.status_code, 200)

        # Immediate second request
        res2 = self.client.post(
            reverse('accounts:register_send_email_otp'),
            data=json.dumps({'email': 'cooldown.user@pune.in'}),
            content_type='application/json'
        )
        self.assertEqual(res2.status_code, 400)
        self.assertIn('wait', res2.json()['error'].lower())


class PasswordRecoveryTests(TestCase):
    """
    Tests for Feature 2, 3, 4, 5, 6:
      - Forgot password via Email
      - Forgot password via Phone
      - Account enumeration prevention (generic response for unknown accounts)
      - OTP verification and single-use reset authorization token
      - Password reset execution with secure PBKDF2 hashing
      - Login with new password and old password invalidation
      - Feature 6 endpoint routing aliases
    """
    def setUp(self):
        self.client = Client()
        mail.outbox = []
        self.user = User.objects.create_user(
            username='recovery_tester',
            email='recovery@shareloop.in',
            password='OriginalPassword@123',
            phone_number='+919822998877',
            user_type='INDIVIDUAL',
        )

    def test_01_email_password_recovery_success_flow(self):
        """End-to-end recovery using registered email: OTP sent, verified, password updated, login works."""
        # 1. Request OTP via email
        res_req = self.client.post(
            reverse('accounts:forgot_password_send_otp'),
            data=json.dumps({'contact_type': 'email', 'contact_value': 'recovery@shareloop.in'}),
            content_type='application/json'
        )
        self.assertEqual(res_req.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)

        import re
        otp_match = re.search(r'\b\d{6}\b', mail.outbox[0].body)
        self.assertIsNotNone(otp_match)
        otp = otp_match.group(0)

        # 2. Verify OTP
        res_ver = self.client.post(
            reverse('accounts:forgot_password_verify_otp'),
            data=json.dumps({'contact_type': 'email', 'contact_value': 'recovery@shareloop.in', 'otp': otp}),
            content_type='application/json'
        )
        self.assertEqual(res_ver.status_code, 200)
        reset_token = res_ver.json()['reset_token']
        self.assertTrue(reset_token)

        # 3. Reset password
        res_reset = self.client.post(
            reverse('accounts:reset_password'),
            data=json.dumps({
                'reset_token': reset_token,
                'password1': 'BrandNewPassword@2026',
                'password2': 'BrandNewPassword@2026',
            }),
            content_type='application/json'
        )
        self.assertEqual(res_reset.status_code, 200)

        # 4. Verify old password no longer works
        self.assertFalse(self.client.login(username='recovery_tester', password='OriginalPassword@123'))

        # 5. Verify new password works
        self.assertTrue(self.client.login(username='recovery_tester', password='BrandNewPassword@2026'))

    def test_02_account_enumeration_protection_on_email(self):
        """Unknown email returns generic success response without exposing account absence."""
        res = self.client.post(
            reverse('accounts:forgot_password_send_otp'),
            data=json.dumps({'contact_type': 'email', 'contact_value': 'unknown.account@shareloop.in'}),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()['success'])
        self.assertIn('If an account is associated', res.json()['message'])
        # No email sent
        self.assertEqual(len(mail.outbox), 0)

    def test_03_reset_token_cannot_be_reused(self):
        """Reset tokens are single-use and cannot be replayed."""
        # Send & verify
        send_password_reset_otp('email', 'recovery@shareloop.in')
        otp_rec = OTPVerification.objects.filter(identifier='recovery@shareloop.in').first()
        import secrets
        plain_otp = '123456'
        otp_rec.set_otp(plain_otp)
        otp_rec.save()

        res_ver = verify_password_reset_otp('email', 'recovery@shareloop.in', plain_otp)
        token = res_ver['reset_token']

        # Reset once
        execute_password_reset(token, 'NewPass1@ShareLoop', 'NewPass1@ShareLoop')

        # Try to reset again with same token -> must fail
        with self.assertRaises(ValidationError):
            execute_password_reset(token, 'NewPass2@ShareLoop', 'NewPass2@ShareLoop')

    def test_04_password_reset_validation_rules(self):
        """Password confirmation must match, min length 8, max length 128, reject whitespace-only."""
        rec = OTPVerification.objects.create(
            purpose=OTPVerification.PURPOSE_PASSWORD_RESET_EMAIL,
            identifier='recovery@shareloop.in',
            user=self.user,
            otp_hash='hash',
            expires_at=timezone.now() + timedelta(minutes=10),
            is_verified=True,
            is_used=False,
        )
        token = rec.issue_reset_token()

        # Mismatch
        with self.assertRaises(ValidationError) as ctx:
            execute_password_reset(token, 'ValidPass@123', 'MismatchPass@123')
        self.assertIn('do not match', ctx.exception.messages[0])

        # Short
        with self.assertRaises(ValidationError) as ctx:
            execute_password_reset(token, 'Short1', 'Short1')
        self.assertIn('at least 8 characters', ctx.exception.messages[0])

        # Whitespace-only
        with self.assertRaises(ValidationError) as ctx:
            execute_password_reset(token, '        ', '        ')
        self.assertIn('whitespace', ctx.exception.messages[0])

    def test_05_phone_password_recovery_unregistered_number(self):
        """Unregistered phone numbers cannot initiate password reset."""
        res = self.client.post(
            reverse('accounts:forgot_password_send_otp'),
            data=json.dumps({'contact_type': 'phone', 'contact_value': '9999900000'}),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn('No registered account found', res.json()['error'])

    def test_06_phone_password_recovery_unconfigured_sms_graceful_handling(self):
        """When SMS gateway is not configured, returns clear error identifying missing env vars."""
        with patch.dict('os.environ', {'TWILIO_ACCOUNT_SID': '', 'FAST2SMS_API_KEY': ''}):
            res = self.client.post(
                reverse('accounts:forgot_password_send_otp'),
                data=json.dumps({'contact_type': 'phone', 'contact_value': '9822998877'}),
                content_type='application/json'
            )
            self.assertEqual(res.status_code, 400)
            self.assertIn('SMS gateway is not configured', res.json()['error'])

    def test_07_phone_password_recovery_with_mocked_gateway(self):
        """With configured SMS gateway, recovery OTP is dispatched, verified, and password updated."""
        with patch('accounts.otp_service.send_sms_otp', return_value={'provider': 'Twilio', 'success': True, 'sid': 'SM123'}):
            res_req = self.client.post(
                reverse('accounts:forgot_password_send_otp'),
                data=json.dumps({'contact_type': 'phone', 'contact_value': '+91 98229 98877'}),
                content_type='application/json'
            )
            self.assertEqual(res_req.status_code, 200)

            # Retrieve active OTP
            otp_rec = OTPVerification.objects.filter(identifier='+919822998877').first()
            self.assertIsNotNone(otp_rec)
            otp_rec.set_otp('654321')
            otp_rec.save()

            # Verify OTP
            res_ver = self.client.post(
                reverse('accounts:forgot_password_verify_otp'),
                data=json.dumps({'contact_type': 'phone', 'contact_value': '9822998877', 'otp': '654321'}),
                content_type='application/json'
            )
            self.assertEqual(res_ver.status_code, 200)
            token = res_ver.json()['reset_token']

            # Reset password
            res_reset = self.client.post(
                reverse('accounts:reset_password'),
                data=json.dumps({'reset_token': token, 'password1': 'PhoneResetPass@2026', 'password2': 'PhoneResetPass@2026'}),
                content_type='application/json'
            )
            self.assertEqual(res_reset.status_code, 200)

            # Login with new password
            self.assertTrue(self.client.login(username='recovery_tester', password='PhoneResetPass@2026'))

    def test_08_auth_api_routes_compatibility(self):
        """Verify that Feature 6 route aliases (/auth/...) respond correctly."""
        # 1. /auth/register/send-email-otp
        res_email_otp = self.client.post(
            '/auth/register/send-email-otp',
            data=json.dumps({'email': 'api.route.tester@shareloop.in'}),
            content_type='application/json'
        )
        self.assertEqual(res_email_otp.status_code, 200)

        # 2. /auth/forgot-password/email
        res_fp_email = self.client.post(
            '/auth/forgot-password/email',
            data=json.dumps({'email': 'recovery@shareloop.in'}),
            content_type='application/json'
        )
        self.assertEqual(res_fp_email.status_code, 200)
