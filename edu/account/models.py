from django.db import models
from django.conf import settings
from django.utils import timezone
from django.dispatch import receiver
from django.db.models.signals import post_save


class EmailOTP(models.Model):
    """
    Model for email verification OTP.
    
    Stores hashed OTP codes (never plain text) for user registration
    email verification. One OTP per user during registration.
    """
    # Link to Django User
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )
    
    # OTP code is HASHED (not plain text) using PBKDF2
    code_hash = models.CharField(max_length=128)
    
    # When the OTP expires (10 minutes from creation)
    expires_at = models.DateTimeField()
    
    # Number of wrong attempts (max 5)
    attempts = models.PositiveIntegerField(default=0)
    
    # When OTP was last sent (for 60-second cooldown)
    last_sent_at = models.DateTimeField(null=True, blank=True)
    
    def is_expired(self):
        """Check if OTP has expired."""
        return timezone.now() > self.expires_at
    
    def __str__(self):
        return f"OTP for {self.user.email}"



class PendingRegistration(models.Model):
    """Temporary storage for unverified registrations"""
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    password_hash = models.CharField(max_length=128)
    first_name = models.CharField(max_length=30, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    
    code_hash = models.CharField(max_length=128)  # OTP hash
    expires_at = models.DateTimeField()
    attempts = models.PositiveIntegerField(default=0)
    last_sent_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def is_expired(self):
        return timezone.now() > self.expires_at
    
    def __str__(self):
        return f"Pending: {self.email}"


class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )
    date_of_birth = models.DateField(
        blank=True,
        null=True
    )
    photo = models.ImageField(
        upload_to = 'user/%Y/%m/%d/',
        blank = True
    )
    def __str__(self) -> str:
        return f'Profile of {self.user.username}'
@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
        