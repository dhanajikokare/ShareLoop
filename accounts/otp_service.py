import secrets
import logging
from datetime import timedelta
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone

from .models import OTPVerification
from .validators import validate_email_format, validate_and_normalize_indian_phone
from .sms_service import send_sms_otp, SMSDeliveryError, SMSNotConfiguredError

logger = logging.getLogger(__name__)
User = get_user_model()


def generate_secure_otp():
    """Generates a cryptographically secure 6-digit numeric OTP."""
    return f"{secrets.randbelow(900000) + 100000:06d}"


def send_registration_email_otp(raw_email, ip_address=None):
    """
    Validates email format, checks for duplicates, enforces 60s cooldown,
    generates secure 6-digit OTP, stores hash, and dispatches via configured email backend.
    """
    email = validate_email_format(raw_email)

    # Duplicate check
    if User.objects.filter(email__iexact=email).exists():
        raise ValidationError("An account with this email address already exists. Please log in or use forgot password.")

    # Check 60s cooldown on existing active OTP
    recent_active = OTPVerification.objects.filter(
        identifier=email,
        purpose=OTPVerification.PURPOSE_REGISTRATION_EMAIL,
        is_used=False
    ).first()

    if recent_active:
        cooldown = recent_active.cooldown_remaining()
        if cooldown > 0:
            raise ValidationError(f"Please wait {cooldown} seconds before requesting a new code.")

    # Invalidate previous unused OTPs for this email & purpose
    OTPVerification.objects.filter(
        identifier=email,
        purpose=OTPVerification.PURPOSE_REGISTRATION_EMAIL,
        is_used=False
    ).update(is_used=True)

    otp = generate_secure_otp()
    expires_at = timezone.now() + timedelta(minutes=5)

    otp_record = OTPVerification(
        purpose=OTPVerification.PURPOSE_REGISTRATION_EMAIL,
        identifier=email,
        expires_at=expires_at,
        ip_address=ip_address,
        last_sent_at=timezone.now(),
    )
    otp_record.set_otp(otp)
    otp_record.save()

    # Send real email via Django configured backend
    subject = f"Your ShareLoop Verification Code: {otp}"
    message = (
        f"Hello,\n\n"
        f"Welcome to ShareLoop Pune! Your verification code is:\n\n"
        f"      {otp}\n\n"
        f"This code will expire in 5 minutes.\n"
        f"If you did not request this verification, please ignore this email.\n\n"
        f"Happy sharing,\n"
        f"The ShareLoop Pune Team"
    )
    html_message = f"""
    <div style="font-family: Arial, sans-serif; max-width: 520px; margin: 0 auto; padding: 24px; border: 1px solid #e2e8f0; border-radius: 12px; background-color: #ffffff;">
      <div style="text-align: center; margin-bottom: 20px;">
        <h2 style="color: #1E3A8A; margin: 0; font-size: 24px;">ShareLoop Pune</h2>
        <p style="color: #64748b; font-size: 14px; margin-top: 4px;">Rent, borrow, or sell with neighbors</p>
      </div>
      <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px; text-align: center; margin: 20px 0;">
        <p style="color: #475569; font-size: 14px; margin-top: 0;">Your verification code is:</p>
        <div style="font-size: 32px; font-weight: bold; letter-spacing: 6px; color: #0D9488; margin: 10px 0;">{otp}</div>
        <p style="color: #94a3b8; font-size: 12px; margin-bottom: 0;">Valid for 5 minutes • Do not share with anyone</p>
      </div>
      <p style="color: #64748b; font-size: 13px; line-height: 1.5;">If you did not request this registration code, you can safely ignore this email.</p>
      <hr style="border: none; border-top: 1px solid #f1f5f9; margin: 20px 0;" />
      <p style="color: #94a3b8; font-size: 12px; text-align: center; margin: 0;">&copy; ShareLoop Pune. Pune, Maharashtra.</p>
    </div>
    """

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info(f"Registration OTP email successfully sent to {email}")
    except Exception as e:
        logger.error(f"Failed to send registration OTP email to {email}: {str(e)}")
        raise ValidationError("Unable to send verification email. Please check server mail settings or try again.")

    return {
        'success': True,
        'message': f"Verification code sent to {email}. Valid for 5 minutes.",
        'cooldown': 60,
    }


def verify_registration_email_otp(raw_email, plain_otp):
    """
    Verifies the email OTP, checks expiry, tracks attempts (max 5),
    invalidates OTP, and returns a short-lived single-use verification token.
    """
    email = validate_email_format(raw_email)
    plain_otp = str(plain_otp).strip()

    if not plain_otp:
        raise ValidationError("Please enter the 6-digit verification code.")

    otp_record = OTPVerification.objects.filter(
        identifier=email,
        purpose=OTPVerification.PURPOSE_REGISTRATION_EMAIL,
        is_used=False
    ).first()

    if not otp_record:
        raise ValidationError("No active verification code found for this email. Please request a new code.")

    if otp_record.is_expired:
        raise ValidationError("Verification code has expired. Please request a new code.")

    if otp_record.attempts >= otp_record.max_attempts:
        raise ValidationError("Maximum verification attempts exceeded. Please request a new code.")

    otp_record.attempts += 1

    if not otp_record.check_otp(plain_otp):
        otp_record.save(update_fields=['attempts'])
        remaining = otp_record.max_attempts - otp_record.attempts
        if remaining > 0:
            raise ValidationError(f"Invalid verification code. {remaining} attempt(s) remaining.")
        else:
            raise ValidationError("Invalid code. Maximum attempts exceeded. Please request a new code.")

    # Success: mark verified and issue single-use verification token
    otp_record.is_verified = True
    token = otp_record.issue_reset_token()
    otp_record.save(update_fields=['is_verified', 'attempts'])

    return {
        'success': True,
        'message': "Email address verified successfully!",
        'verification_token': token,
    }


def check_email_is_verified_for_registration(email, verification_token=None):
    """
    Enforces on the backend that an email has been verified via OTP within the last 15 minutes.
    """
    normalized_email = email.strip().lower()
    cutoff = timezone.now() - timedelta(minutes=15)

    qs = OTPVerification.objects.filter(
        identifier=normalized_email,
        purpose=OTPVerification.PURPOSE_REGISTRATION_EMAIL,
        is_verified=True,
        is_used=False,
        created_at__gte=cutoff,
    )
    if verification_token:
        qs = qs.filter(reset_token=verification_token)

    record = qs.first()
    return record is not None


def mark_registration_verification_used(email):
    """Marks the registration verification record as used upon successful user creation."""
    normalized_email = email.strip().lower()
    OTPVerification.objects.filter(
        identifier=normalized_email,
        purpose=OTPVerification.PURPOSE_REGISTRATION_EMAIL,
        is_verified=True,
        is_used=False,
    ).update(is_used=True, reset_token=None)


def send_password_reset_otp(contact_type, contact_value, ip_address=None):
    """
    Dispatches password reset OTP via Email or SMS.
    Enforces 60-second cooldown, 5-minute expiry, and protects against account enumeration.
    """
    if contact_type == 'email':
        email = validate_email_format(contact_value)
        user = User.objects.filter(email__iexact=email).first()

        # If user not found, return generic success to prevent account enumeration
        if not user:
            return {
                'success': True,
                'message': "If an account is associated with this email, a verification code has been sent.",
                'cooldown': 60,
                'contact_type': 'email',
                'target': email,
            }

        # Check cooldown
        recent = OTPVerification.objects.filter(
            identifier=email,
            purpose=OTPVerification.PURPOSE_PASSWORD_RESET_EMAIL,
            is_used=False
        ).first()
        if recent:
            cd = recent.cooldown_remaining()
            if cd > 0:
                raise ValidationError(f"Please wait {cd} seconds before requesting a new code.")

        # Invalidate previous unused
        OTPVerification.objects.filter(
            identifier=email,
            purpose=OTPVerification.PURPOSE_PASSWORD_RESET_EMAIL,
            is_used=False
        ).update(is_used=True)

        otp = generate_secure_otp()
        otp_record = OTPVerification(
            purpose=OTPVerification.PURPOSE_PASSWORD_RESET_EMAIL,
            identifier=email,
            user=user,
            expires_at=timezone.now() + timedelta(minutes=5),
            last_sent_at=timezone.now(),
            ip_address=ip_address,
        )
        otp_record.set_otp(otp)
        otp_record.save()

        subject = f"Your ShareLoop Password Reset Code: {otp}"
        message = (
            f"Hello {user.first_name or user.username},\n\n"
            f"We received a request to reset your ShareLoop password. Your verification code is:\n\n"
            f"      {otp}\n\n"
            f"This code will expire in 5 minutes.\n"
            f"If you did not request a password reset, please ignore this email or contact support.\n\n"
            f"The ShareLoop Team"
        )
        html_message = f"""
        <div style="font-family: Arial, sans-serif; max-width: 520px; margin: 0 auto; padding: 24px; border: 1px solid #e2e8f0; border-radius: 12px; background-color: #ffffff;">
          <div style="text-align: center; margin-bottom: 20px;">
            <h2 style="color: #1E3A8A; margin: 0; font-size: 24px;">ShareLoop Password Reset</h2>
            <p style="color: #64748b; font-size: 14px; margin-top: 4px;">Account Security</p>
          </div>
          <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px; text-align: center; margin: 20px 0;">
            <p style="color: #475569; font-size: 14px; margin-top: 0;">Your password recovery code is:</p>
            <div style="font-size: 32px; font-weight: bold; letter-spacing: 6px; color: #0D9488; margin: 10px 0;">{otp}</div>
            <p style="color: #94a3b8; font-size: 12px; margin-bottom: 0;">Valid for 5 minutes • Never share this code</p>
          </div>
          <p style="color: #64748b; font-size: 13px; line-height: 1.5;">If you did not request this password reset, please secure your account immediately.</p>
        </div>
        """

        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                html_message=html_message,
                fail_silently=False
            )
            logger.info(f"Password reset OTP email sent to {email}")
        except Exception as e:
            logger.error(f"Failed to send password reset email to {email}: {str(e)}")
            raise ValidationError("Unable to send recovery email. Please check server mail settings or try again.")

        return {
            'success': True,
            'message': f"If an account is associated with this email, a verification code has been sent.",
            'cooldown': 60,
            'contact_type': 'email',
            'target': email,
        }

    elif contact_type == 'phone':
        phone = validate_and_normalize_indian_phone(contact_value)
        raw_10 = phone.replace('+91', '')

        # Lookup user by phone
        phone_variations = [phone, raw_10, f"0{raw_10}", f"+91 {raw_10[:5]} {raw_10[5:]}", f"+91 {raw_10}"]
        user = User.objects.filter(phone_number__in=phone_variations).first()

        if not user:
            # For phone, explicitly reject or generic response
            raise ValidationError("No registered account found with this phone number. Please check the number or use email recovery.")

        # Check cooldown
        recent = OTPVerification.objects.filter(
            identifier=phone,
            purpose=OTPVerification.PURPOSE_PASSWORD_RESET_PHONE,
            is_used=False
        ).first()
        if recent:
            cd = recent.cooldown_remaining()
            if cd > 0:
                raise ValidationError(f"Please wait {cd} seconds before requesting a new code.")

        # Invalidate previous unused
        OTPVerification.objects.filter(
            identifier=phone,
            purpose=OTPVerification.PURPOSE_PASSWORD_RESET_PHONE,
            is_used=False
        ).update(is_used=True)

        otp = generate_secure_otp()

        # Send via real SMS gateway
        try:
            send_sms_otp(phone, otp)
        except SMSNotConfiguredError as e:
            logger.warning(f"SMS delivery unconfigured for phone reset: {str(e)}")
            raise ValidationError(str(e))
        except SMSDeliveryError as e:
            logger.error(f"SMS delivery error: {str(e)}")
            raise ValidationError(f"Failed to deliver SMS: {str(e)}")

        otp_record = OTPVerification(
            purpose=OTPVerification.PURPOSE_PASSWORD_RESET_PHONE,
            identifier=phone,
            user=user,
            expires_at=timezone.now() + timedelta(minutes=5),
            last_sent_at=timezone.now(),
            ip_address=ip_address,
        )
        otp_record.set_otp(otp)
        otp_record.save()

        return {
            'success': True,
            'message': f"Verification code sent to {phone[-4:].rjust(len(phone), '*')}. Valid for 5 minutes.",
            'cooldown': 60,
            'contact_type': 'phone',
            'target': phone,
        }

    else:
        raise ValidationError("Unsupported recovery option. Please choose Email or Phone.")


def verify_password_reset_otp(contact_type, contact_value, plain_otp):
    """
    Verifies the password reset OTP, records attempts, and generates a single-use reset authorization token.
    """
    plain_otp = str(plain_otp).strip()
    if not plain_otp:
        raise ValidationError("Please enter the 6-digit verification code.")

    if contact_type == 'email':
        identifier = validate_email_format(contact_value)
        purpose = OTPVerification.PURPOSE_PASSWORD_RESET_EMAIL
    elif contact_type == 'phone':
        identifier = validate_and_normalize_indian_phone(contact_value)
        purpose = OTPVerification.PURPOSE_PASSWORD_RESET_PHONE
    else:
        raise ValidationError("Invalid recovery method.")

    otp_record = OTPVerification.objects.filter(
        identifier=identifier,
        purpose=purpose,
        is_used=False
    ).first()

    if not otp_record:
        raise ValidationError("No active verification code found. Please request a new code.")

    if otp_record.is_expired:
        raise ValidationError("Verification code has expired. Please request a new code.")

    if otp_record.attempts >= otp_record.max_attempts:
        raise ValidationError("Maximum verification attempts exceeded. Please request a new code.")

    otp_record.attempts += 1

    if not otp_record.check_otp(plain_otp):
        otp_record.save(update_fields=['attempts'])
        remaining = otp_record.max_attempts - otp_record.attempts
        if remaining > 0:
            raise ValidationError(f"Invalid verification code. {remaining} attempt(s) remaining.")
        else:
            raise ValidationError("Invalid code. Maximum attempts exceeded. Please request a new code.")

    # Success: issue single-use reset token bound to this record and user
    otp_record.is_verified = True
    reset_token = otp_record.issue_reset_token()
    otp_record.save(update_fields=['is_verified', 'attempts'])

    return {
        'success': True,
        'message': "Code verified! Please set your new password.",
        'reset_token': reset_token,
    }


def execute_password_reset(reset_token, password1_raw, password2_raw):
    """
    Validates reset authorization token and updates user password securely.
    Invalidates the reset token immediately to prevent replay.
    """
    if not reset_token or not str(reset_token).strip():
        raise ValidationError("Password reset authorization token is missing.")

    otp_record = OTPVerification.objects.filter(
        reset_token=reset_token.strip(),
        is_verified=True,
        is_used=False,
    ).first()

    if not otp_record or not otp_record.user:
        raise ValidationError("Password reset authorization has expired or is invalid. Please request a new code.")

    if otp_record.reset_token_expires_at and timezone.now() > otp_record.reset_token_expires_at:
        raise ValidationError("Password reset authorization has expired. Please request a new recovery code.")

    # Validate passwords
    if not password1_raw:
        raise ValidationError("Password is required.")
    if not str(password1_raw).strip():
        raise ValidationError("Password cannot consist entirely of whitespace.")
    if len(password1_raw) < 8:
        raise ValidationError("Password must contain at least 8 characters.")
    if len(password1_raw) > 128:
        raise ValidationError("Password cannot exceed 128 characters.")
    if password1_raw != password2_raw:
        raise ValidationError("Passwords do not match. Please re-enter your password.")

    user = otp_record.user
    user.set_password(password1_raw)
    user.save()

    # Invalidate all existing auth tokens and active sessions for this user
    try:
        from rest_framework.authtoken.models import Token
        Token.objects.filter(user=user).delete()
    except Exception as e:
        logger.warning(f'Could not delete auth tokens on password reset: {e}')

    # Invalidate reset token and mark record as used
    otp_record.is_used = True
    otp_record.reset_token = None
    otp_record.save(update_fields=['is_used', 'reset_token'])

    logger.info(f"Password successfully reset for user '{user.username}' via {otp_record.purpose}")

    return {
        'success': True,
        'message': "Your password has been reset successfully. Please log in with your new password.",
        'username': user.username,
    }
