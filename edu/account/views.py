from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.hashers import make_password, check_password
from django.utils import timezone
from django.urls import reverse_lazy
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.db.models import Q

from .emailer import send_email_otp
from .models import EmailOTP, Profile, PendingRegistration
from .utils import generate_otp, otp_expire, otp_cooldown_remaining
from .forms import UserRegistrationForm, UserEditForm, ProfileEditForm



COOLDOWN_SECONDS = 60


def register(request):
    """
    Handle user registration with email verification.

    Flow:
    1. User submits registration form
    2. Validate form (unique username, unique email, passwords match)
    3. Check for existing pending registration
    4. Generate OTP code
    5. Hash OTP
    6. Save pending registration with expiry
    7. Send email via SMTP
    8. Redirect to verification page
    """

    if request.method == 'POST':
        user_form = UserRegistrationForm(request.POST)

        if user_form.is_valid():
            email = user_form.cleaned_data['email']
            username = user_form.cleaned_data['username']

            existing = PendingRegistration.objects.filter(
                Q(email__iexact=email) | Q(username__iexact=username)
            ).first()

            if existing:
                if existing.is_expired():
                    existing.delete()
                else:
                    request.session['pending_registration_id'] = existing.id
                    messages.info(request, "You already started registration. Check your email or resend.")
                    return redirect('verify_email')

            code = generate_otp()
            code_hash = make_password(code)

            try:
                pending = PendingRegistration.objects.create(
                    username=username,
                    email=email,
                    first_name=user_form.cleaned_data.get('first_name', ''),
                    last_name=user_form.cleaned_data.get('last_name', ''),
                    password_hash=make_password(user_form.cleaned_data['password']),
                    code_hash=code_hash,
                    expires_at=otp_expire(10),
                    last_sent_at=timezone.now(),
                )
            except IntegrityError:
                messages.error(request, "A pending registration already exists. Please verify or resend.")
                return render(request, 'account/register.html', {'user_form': user_form})

            try:
                send_email_otp(
                    email,
                    "Your verification code - E-Learning Platform",
                    code
                )
            except Exception as e:
                messages.error(request, "Email sending failed. Please try again.")
                pending.delete()
                return render(request, 'account/register.html', {'user_form': user_form})

            request.session['pending_registration_id'] = pending.id
            messages.success(request, f"Verification code sent to {pending.email}")
            return redirect('verify_email')

        for field, errors in user_form.errors.items():
            for error in errors:
                messages.error(request, f"{field.replace('_', ' ').title()}: {error}")
        return render(request, 'account/register.html', {'user_form': user_form})

    user_form = UserRegistrationForm()
    return render(request, 'account/register.html', {'user_form': user_form})


def verify_email(request):
    """
    Verify OTP code entered by user.
    
    Flow:
    1. Check if user has pending verification
    2. Get their EmailOTP record
    3. Validate code:
       - Check if expired (> 10 minutes)
       - Check if too many attempts (>= 5)
       - Hash user input and compare with stored hash
    4. If valid: activate account, delete OTP, login, redirect
    5. If invalid: increment attempts, show error
    """
    
    # Get user ID from session (set during registration)
    pending_id = request.session.get('pending_registration_id')
    
    if not pending_id:
        # User not registering, send to login
        messages.warning(request, "No pending verification. Please register first.")
        return redirect('student_registration')
    
    pending = PendingRegistration.objects.get(id=pending_id)
    
    if request.method == 'POST':
        # User entered code
        code = request.POST.get('code', '').strip()
        
        # Check 1: Is OTP expired?
        if pending.is_expired():
            pending.delete()
            return render(
                request,
                'account/verify.html',
                {'error': 'Code has expired. Please request a new one.', 'user_email': pending.email}
            )
        
        # Check 2: Have they tried too many times?
        if pending.attempts >= 5:
            return render(
                request,
                'account/verify.html',
                {'error': 'Too many incorrect attempts. Please request a new code.', 'user_email': pending.email}
            )
        
        # Check 3: Does the code match?
        if check_password(code, pending.code_hash):
            # ✓ Code is correct!
            user_model = get_user_model()
            new_user = user_model(
                username=pending.username,
                email=pending.email,
                first_name=pending.first_name,
                last_name=pending.last_name,
                is_active=True
            )
            new_user.password = pending.password_hash  # already hashed
            new_user.save()
            
            #delete temporary record
            pending.delete()
            
            # Auto-login user
            login(request, new_user, backend="django.contrib.auth.backends.ModelBackend")
            
            messages.success(request, f"Email verified! Welcome to E-Learning Platform, {new_user.first_name or new_user.username}!")
            
            # Redirect to course list
            return redirect('course_list')
        
        else:
            # ✗ Code is incorrect
            
            # Increment attempts
            pending.attempts += 1
            pending.save()
            
            attempts_left = 5 - pending.attempts
            error_msg = f'Incorrect code. You have {attempts_left} attempts remaining.'
            
            return render(
                request,
                'account/verify.html',
                {'error': error_msg, 'user_email': pending.email}
            )
    
    else:
        # GET request - show verification form
        return render(request, 'account/verify.html', {'user_email': pending.email})


def resend_otp(request):
    """
    Resend OTP code to user's email.
    
    Includes 60-second cooldown to prevent spam.
    """
    
    if request.method != 'POST':
        return redirect('verify_email')
    
    # Get pending user from session
    pending_id = request.session.get('pending_registration_id')
    
    if not pending_id:
        messages.warning(request, "No pending verification.")
        return redirect('student_registration')
    try:
        pending = PendingRegistration.objects.get(id=pending_id)
    except PendingRegistration.DoesNotExist:
        messages.warning(request, "Registration record not found. Please register again.")
        return redirect('student_registration')
    
    # Check cooldown
    remaining = otp_cooldown_remaining(pending.last_sent_at, seconds=COOLDOWN_SECONDS)
    if remaining > 0:
        return render(
            request,
            'account/verify.html',
            {
                'error': f'Please wait {remaining} seconds before requesting a new code.',
                'user_email': pending.email
            }
        )
    
    # Generate new OTP
    code = generate_otp()
    pending.code_hash = make_password(code)
    pending.expires_at = otp_expire(10)
    pending.attempts = 0
    pending.last_sent_at = timezone.now()
    pending.save()
    
    # Send email
    try:
        send_email_otp(
            pending.email,
            "Your new verification code - E-Learning Platform",
            code
        )
    except Exception as e:
        messages.error(request, f"Failed to send email. Please try again later.")
        return render(
            request,
            'account/verify.html',
            {'user_email': pending.email}
        )
    messages.success(request, f"New verification code sent to {pending.email}")
    return render(
        request,
        'account/verify.html',
        {
            'info': 'New code sent! Check your email.',
            'user_email': pending.email
        }
    )

@login_required
def edit(request):
    profile, created = Profile.objects.get_or_create(user=request.user)  # ✅ safe

    if request.method == 'POST':
        user_form = UserEditForm(instance=request.user, data=request.POST)
        profile_form = ProfileEditForm(instance=profile, data=request.POST, files=request.FILES)

        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, "Profile updated successfully 🎉")
        else:
            messages.error(request, "Error updating your profile.")
    else:
        user_form = UserEditForm(instance=request.user)
        profile_form = ProfileEditForm(instance=profile)   # ✅ empty fields if new profile

    return render(request, 'account/edit.html', {
    'user_form': user_form,
    'profile_form': profile_form,
    'show_help': True, 
    })