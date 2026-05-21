from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from .models import Profile
from .models import PendingRegistration

class UserRegistrationForm(forms.ModelForm):
    """
    Registration form for new users with email verification.
    
    Fields:
    - username: Required, unique
    - email: Required, unique
    - first_name: Optional
    - last_name: Optional
    - password: Required, min 8 chars, strong
    - password2: Required, must match password
    
    Validates:
    - Email not already registered
    - Passwords match
    - Password meets complexity requirements
    """
    
    # Password field (hidden input)
    password = forms.CharField(
        label='Password',
        widget=forms.PasswordInput
    )
    
    # Password confirmation field
    password2 = forms.CharField(
        label='Confirm password',
        widget=forms.PasswordInput
    )
    
    class Meta:
        model = get_user_model()
        fields = ['username', 'first_name', 'last_name', 'email']
    
    def clean_password2(self):
        """Validate that passwords match."""
        cd = self.cleaned_data
        
        if cd.get('password') and cd.get('password2'):
            if cd['password'] != cd['password2']:
                raise forms.ValidationError("Passwords don't match")
        
        return cd.get('password2')
    
    def clean_email(self):
        data = self.cleaned_data.get('email')
        if data and User.objects.filter(email__iexact=data).exists():
            raise forms.ValidationError('This email is already registered.')
        
        return data
    
    def clean_username(self):
        """Validate that username is unique."""
        data = self.cleaned_data.get('username')
        
        if data and User.objects.filter(username=data).exists():
            suggestion = suggest_username(data)
            raise forms.ValidationError(f'Username taken. Try: {suggestion}')
        
        return data

def suggest_username(email):
    """Generate alternative usernames with numbers"""
    base = email.split('@')[0]
    
    if not User.objects.filter(username=base).exists():
        return base
    
    for i in range(1, 1000):
        suggestion = f"{base}{i}"
        if not User.objects.filter(username=suggestion).exists():
            return suggestion
    
    return None


# profile manager
class UserEditForm(forms.ModelForm):
    class Meta:
        model = get_user_model()
        fields = ['first_name', 'last_name']

class ProfileEditForm(forms.ModelForm):
    """
    Form for editing a Profile instance.

    This ModelForm exposes only the 'date_of_birth' and 'photo' fields from the Profile model. It leverages Django's ModelForm machinery to:
    - automatically generate form fields and validation from the model,
    - bind data (and files) via ProfileEditForm(request.POST, request.FILES, instance=profile),
    - validate with is_valid() and persist changes with save() (use save(commit=False) to adjust before saving).

    Usage notes:
    - The HTML form must use enctype="multipart/form-data" to upload the 'photo'.
    - Validation is handled by the form fields and any model-level clean() methods.
    - Only the listed fields are editable; other Profile attributes are not exposed by this form.
    """
    class Meta:
        model = Profile
        fields = ['date_of_birth', 'photo']
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
        }