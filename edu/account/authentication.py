from django.contrib.auth.models import User


class EmailAuthBackend:
    """
    Authenticate using an email address instead of username.
    Allows users to login with either username OR email.
    """
    
    def authenticate(self, request, username=None, password=None):
        """
        Try to authenticate using email address.
        
        Args:
            request: HTTP request object
            username: Email address (named username for Django compatibility)
            password: User's password
            
        Returns:
            User object if valid, None if invalid
        """
        try:
            # Look up user by EMAIL (not username)
            user = User.objects.get(email=username)
            
            # Check if password matches
            if user.check_password(password):
                return user
            
            return None
            
        except (User.DoesNotExist, User.MultipleObjectsReturned):
            return None
    
    def get_user(self, user_id):
        """Retrieve user by ID (used for session restoration)."""
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
