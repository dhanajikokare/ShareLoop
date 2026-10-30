import re
from django.core.exceptions import ValidationError
from django.core.validators import validate_email as django_validate_email, EmailValidator


def validate_and_normalize_indian_phone(value):
    """
    Validates and normalizes an Indian mobile phone number.
    
    Accepts formats such as:
      - 9876543210
      - +919876543210
      - +91 98765 43210
      - +91-98765-43210
      - 09876543210
      - (0)9876543210
    
    Rules:
      - Permitted separators: spaces, hyphens, parentheses, plus sign.
      - Letters or invalid symbols are rejected.
      - Exactly 10 mobile digits after removing country code / trunk prefix.
      - First mobile digit must be between 6 and 9.
    
    Returns:
      Normalized phone number in '+91XXXXXXXXXX' format.
    """
    if not value or not str(value).strip():
        raise ValidationError("Phone number is required.")

    raw = str(value).strip()

    # Reject if any letter or unsupported punctuation is present
    if not re.match(r'^[0-9+\s\-()]+$', raw):
        raise ValidationError("Phone number must contain only digits and valid separators.")

    # Check for country code prefix if plus is present
    if raw.startswith('+'):
        # Must start with +91
        if not raw.startswith('+91'):
            raise ValidationError("Only Indian phone numbers (+91) are supported.")
        # Strip the +91 prefix
        after_cc = raw[3:]
    else:
        after_cc = raw

    # Extract all digits
    digits = re.sub(r'\D', '', after_cc)

    # Handle 12-digit format starting with 91 (when user enters 919876543210 without +)
    if len(digits) == 12 and digits.startswith('91'):
        digits = digits[2:]
    # Handle 11-digit format starting with 0 trunk prefix (e.g. 09876543210)
    elif len(digits) == 11 and digits.startswith('0'):
        digits = digits[1:]

    # Must be exactly 10 digits
    if len(digits) != 10:
        raise ValidationError("Phone number must contain exactly 10 mobile digits.")

    # First digit must be between 6 and 9
    if digits[0] not in '6789':
        raise ValidationError("Indian mobile numbers must begin with 6, 7, 8, or 9.")

    return f"+91{digits}"


def validate_email_format(value):
    """
    Validates email format:
      - Required, non-empty.
      - Trimmed leading/trailing spaces.
      - Valid local and domain parts.
      - Domain must have at least one dot and a valid TLD of at least 2 chars.
      - Rejects missing domains, malformed formats, and spaces.
    
    Returns:
      Normalized lowercase email string.
    """
    if not value or not str(value).strip():
        raise ValidationError("Email address is required.")

    email = str(value).strip()

    if email.count('@') != 1:
        raise ValidationError("Enter a valid email address (e.g., user@example.com).")

    local_part, domain_part = email.split('@')

    if not local_part:
        raise ValidationError("Enter a valid email address with a username before '@'.")

    if not domain_part:
        raise ValidationError("Enter a valid email address with a domain after '@'.")

    if '.' not in domain_part or domain_part.startswith('.') or domain_part.endswith('.'):
        raise ValidationError("Enter a valid email address with a complete domain (e.g., user@example.com).")

    domain_parts = domain_part.split('.')
    if any(not part or part.startswith('-') or part.endswith('-') for part in domain_parts):
        raise ValidationError("Enter a valid email address with a valid domain.")

    if len(domain_parts[-1]) < 2:
        raise ValidationError("Enter a valid email address with a valid domain extension (e.g., .com, .in).")

    validator = EmailValidator(message="Enter a valid email address (e.g., user@example.com).")
    validator(email)

    return email.lower()
