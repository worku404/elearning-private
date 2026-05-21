from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string


def send_email_otp(to_email, subject, otp_code):
    """
    Send OTP verification email via Google SMTP.
    
    Uses Django's built-in email backend configured for Google SMTP.
    
    Args:
        to_email (str): Recipient email address
        subject (str): Email subject line
        otp_code (str): 6-digit OTP code to include in email
        
    Returns:
        int: Number of emails sent (0 or 1)
        
    Raises:
        Exception: If email sending fails
        
    Configuration (in settings.py):
        EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
        EMAIL_HOST = "smtp.gmail.com"
        EMAIL_PORT = 587
        EMAIL_USE_TLS = True
        EMAIL_HOST_USER = "your-email@gmail.com"
        EMAIL_HOST_PASSWORD = "your-app-password"
    """
    
    # Build plain text message
    message_text = f"""
Your verification code is: {otp_code}

This code will expire in 10 minutes.

Do not share this code with anyone.

If you did not request this code, you can safely ignore this email.
"""
    
    # Build HTML message (optional, for better email clients)
    try:
        html_message = render_to_string('account/email/otp_email.html', {
            'otp_code': otp_code,
            'site_name': settings.SITE_NAME if hasattr(settings, 'SITE_NAME') else 'E-Learning Platform'
        })
    except:
        # Fallback if template doesn't exist
        html_message = f"""
        <h2>Email Verification</h2>
        <p>Your verification code is: <strong>{otp_code}</strong></p>
        <p>This code will expire in 10 minutes.</p>
        <p><small>Do not share this code with anyone.</small></p>
        """
    
    # Get sender email from settings
    from_email = settings.DEFAULT_FROM_EMAIL
    
    # Send email via Django's send_mail function
    try:
        send_mail(
            subject=subject,
            message=message_text,
            from_email=from_email,
            recipient_list=[to_email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Email sending failed: {str(e)}")
        raise
