import secrets
from datetime import timedelta
from django.utils import timezone


def generate_otp():
    """
    Generate a random 6-digit OTP code.
    
    Uses Python's secrets module for cryptographic randomness.
    
    Returns:
        str: 6-digit code, e.g., "482956"
    """
    # Random number 0-999,999
    random_number = secrets.randbelow(1000000)
    
    # Format as 6 digits with leading zeros
    code = f'{random_number:06d}'
    
    return code


def otp_expire(minutes=10):
    """
    Calculate OTP expiration time.
    
    Args:
        minutes (int): Minutes until expiry (default 10)
    
    Returns:
        datetime: Current time + X minutes
    """
    return timezone.now() + timedelta(minutes=minutes)


def otp_cooldown_remaining(last_sent_at, seconds=60):
    """
    Calculate cooldown time remaining before can resend.
    
    Prevents spam by limiting resend frequency.
    
    Args:
        last_sent_at (datetime): When code was last sent
        seconds (int): Cooldown duration (default 60)
    
    Returns:
        int: Seconds remaining, or 0 if ready to resend
    """
    if not last_sent_at:
        return 0
    
    # Calculate when cooldown expires
    cooldown_expires = last_sent_at + timedelta(seconds=seconds)
    
    # Calculate remaining time
    remaining_seconds = (cooldown_expires - timezone.now()).total_seconds()
    
    # Return max(0, remaining) to never return negative
    return max(0, int(remaining_seconds))
