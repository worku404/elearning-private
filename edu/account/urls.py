from django.urls import path, include
from . import views

urlpatterns = [
    # Include Django's built-in auth URLs (login, logout, password_reset, etc.)
    path('', include('django.contrib.auth.urls')),
    
    # Custom authentication URLs
    path('register/', views.register, name='account_register'),
    path('verify_email/', views.verify_email, name='verify_email'),
    path('verify_email/resend/', views.resend_otp, name='resend_otp'),
    path(
        'edit/', views.edit, name='edit'
    ),
]
