import os
import logging
import requests

logger = logging.getLogger(__name__)


class SMSDeliveryError(Exception):
    """Custom exception raised when SMS delivery fails."""
    pass


class SMSNotConfiguredError(SMSDeliveryError):
    """Raised when no SMS provider credentials are configured in the environment."""
    pass


def send_sms_otp(phone_number, otp):
    """
    Sends an SMS containing the OTP to the specified phone number using a real SMS gateway.
    
    Supported Providers (configured via environment variables):
    1. Twilio:
       - TWILIO_ACCOUNT_SID
       - TWILIO_AUTH_TOKEN
       - TWILIO_PHONE_NUMBER
    
    2. Fast2SMS (Indian SMS Gateway):
       - FAST2SMS_API_KEY
    
    If no provider is configured, raises SMSNotConfiguredError with the required environment variables.
    Does NOT mock or pretend to send an SMS if the provider is unconfigured.
    """
    message_text = f"Your ShareLoop verification code is {otp}. Valid for 5 minutes. Do not share this code with anyone."

    twilio_sid = os.getenv('TWILIO_ACCOUNT_SID', '').strip()
    twilio_token = os.getenv('TWILIO_AUTH_TOKEN', '').strip()
    twilio_from = os.getenv('TWILIO_PHONE_NUMBER', '').strip()

    fast2sms_key = os.getenv('FAST2SMS_API_KEY', '').strip()

    # 1. Try Twilio if credentials are provided
    if twilio_sid and twilio_token and twilio_from:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{twilio_sid}/Messages.json"
        data = {
            'To': phone_number,
            'From': twilio_from,
            'Body': message_text,
        }
        try:
            response = requests.post(
                url,
                data=data,
                auth=(twilio_sid, twilio_token),
                timeout=10
            )
            if response.status_code in (200, 201):
                logger.info(f"SMS successfully dispatched via Twilio to {phone_number[-4:]}")
                return {
                    'provider': 'Twilio',
                    'success': True,
                    'sid': response.json().get('sid')
                }
            else:
                err_msg = response.json().get('message', response.text)
                logger.error(f"Twilio SMS delivery failed: {err_msg}")
                raise SMSDeliveryError(f"Twilio delivery failed ({response.status_code}): {err_msg}")
        except requests.RequestException as e:
            logger.error(f"Network error during Twilio SMS dispatch: {str(e)}")
            raise SMSDeliveryError(f"Network error connecting to Twilio: {str(e)}")

    # 2. Try Fast2SMS (popular Indian transactional SMS gateway)
    elif fast2sms_key:
        url = "https://www.fast2sms.com/dev/bulkV2"
        # Fast2SMS requires 10-digit number without +91
        clean_10 = phone_number.replace('+91', '').strip()
        payload = {
            "route": "otp",
            "variables_values": otp,
            "numbers": clean_10,
        }
        headers = {
            "authorization": fast2sms_key,
            "Content-Type": "application/json"
        }
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            res_json = response.json()
            if response.status_code == 200 and res_json.get('return') is True:
                logger.info(f"SMS successfully dispatched via Fast2SMS to {phone_number[-4:]}")
                return {
                    'provider': 'Fast2SMS',
                    'success': True,
                    'request_id': res_json.get('request_id')
                }
            else:
                err_msg = res_json.get('message', ['Failed to send SMS'])
                if isinstance(err_msg, list):
                    err_msg = err_msg[0]
                logger.error(f"Fast2SMS error: {err_msg}")
                raise SMSDeliveryError(f"Fast2SMS delivery error: {err_msg}")
        except requests.RequestException as e:
            logger.error(f"Network error connecting to Fast2SMS: {str(e)}")
            raise SMSDeliveryError(f"Network error connecting to Fast2SMS: {str(e)}")

    # 3. Neither configured
    else:
        missing_vars = "TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER or FAST2SMS_API_KEY"
        logger.warning(f"SMS delivery attempted but no SMS provider credentials configured ({missing_vars})")
        raise SMSNotConfiguredError(
            "SMS gateway is not configured on this server. Please use Email Recovery, or configure environment variables: "
            "TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_PHONE_NUMBER."
        )
