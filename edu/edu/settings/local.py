from .base import *

DEBUG = True

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        # Local defaults target Docker postgres; override via .env when needed.
        'NAME': config('DB_NAME', default='e_learning_db'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST', default='127.0.0.1'),
        'PORT': config('POSTGRES_PORT', default=5432, cast=int),
    }
}
CSRF_TRUSTED_ORIGINS = [
    'http://127.0.0.1:8000',
]
