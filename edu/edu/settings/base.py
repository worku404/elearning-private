"""
Settings for the edu project.
"""

import os
from pathlib import Path  # Standard library: build OS-safe filesystem paths

from decouple import config
from django.urls import (
    reverse_lazy,  # Django utility: resolve URL names lazily at runtime
)
from dotenv import load_dotenv

# Redis Configuration
# Using values derived from your container inspection
REDIS_HOST = config("REDIS_HOST", default="127.0.0.1")
REDIS_PORT = config("REDIS_PORT", default=6379, cast=int)
REDIS_DB = config("REDIS_DB", default=0, cast=int)
ASSISTANT_MAX_OUTPUT_TOKENS = config("ASSISTANT_MAX_OUTPUT_TOKENS", default=60000, cast=int)

# Core project paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load environment variables from either project root or settings directory.
for _env_path in (BASE_DIR.parent / ".env", BASE_DIR / ".env", BASE_DIR / "edu" / ".env"):
    if _env_path.exists():
        load_dotenv(_env_path, override=True)

# Authentication behavior
# Send authenticated users to the course home page after login.
LOGIN_REDIRECT_URL = reverse_lazy("course_list")


# Security and runtime mode
SECRET_KEY = "7IbkXJQpjATuvsYerStSa^t)_kd7cve$=bhjrqj_qt+4*3*sooh9t=mxp$&7*8apel@9a6"
ALLOWED_HOSTS = []


# Application registration
INSTALLED_APPS = [
    "daphne",
    # Project apps (keep this app first as requested for auth monitoring/dependency order)
    "courses.apps.CoursesConfig",
    # Django built-in apps
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Project apps
    "account.apps.AccountConfig",  # Email verification and authentication
    "students.apps.StudentsConfig",
    "assistant.apps.AssistantConfig",
    "chat.apps.ChatConfig",
    # Notes app: personal notes feature.
    "notes.apps.NotesConfig",
    "learning_insights.apps.LearningInsightsConfig",
    # Third-party apps
    "embed_video",  # Embed and render video content in templates/models
    "debug_toolbar",  # Development-time request/SQL/debug inspection
    "redisboard",  # Redis monitoring dashboard
    "rest_framework",  # To build an API
    "rest_framework.authtoken",  # DRF token authentication model
    "django.contrib.postgres",
]


# Middleware pipeline (request/response processing order matters)
MIDDLEWARE = [
    # "debug_toolbar.middleware.DebugToolbarMiddleware",          # Third-party middleware
    "django.middleware.security.SecurityMiddleware",  # Built-in: security headers and protections
    "django.contrib.sessions.middleware.SessionMiddleware",  # Built-in: session support
    # Enable these only if full-site cache middleware is needed:
    # "django.middleware.cache.UpdateCacheMiddleware",          # Built-in: stores cache for responses
    "django.middleware.common.CommonMiddleware",  # Built-in: URL rewriting, ETags, etc.
    # "django.middleware.cache.FetchFromCacheMiddleware",       # Built-in: serves cached responses
    "django.middleware.csrf.CsrfViewMiddleware",  # Built-in: CSRF protection
    "django.contrib.auth.middleware.AuthenticationMiddleware",  # Built-in: attaches authenticated user
    "django.contrib.messages.middleware.MessageMiddleware",  # Built-in: one-time message framework
    "django.middleware.clickjacking.XFrameOptionsMiddleware",  # Built-in: clickjacking protection
    # 'courses.middleware.subdomain_course_middleware',
]


# URL and template configuration
ROOT_URLCONF = "edu.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # Project-level templates (used for global overrides like form widgets).
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "assistant.context_processors.llm_widget",
                "students.context_processors.global_progress",
                "courses.context_processors.daily_motto",
            ],
        },
    },
]

WSGI_APPLICATION = "edu.wsgi.application"


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# Localization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True


# Static and media files
STATIC_URL = "/static/"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
STATIC_ROOT = BASE_DIR / "static"


# Security headers
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"


# Cache configuration (Redis)
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/1",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}

# CACHES = {
#     "default": {
#         "BACKEND": "django.core.cache.backends.memcached.PyMemcacheCache",
#         "LOCATION": "127.0.0.1:11211",
#     }
# }
# Development local IPs (used by debug-toolbar)
INTERNAL_IPS = ["127.0.0.1"]

# Cache middleware settings
CACHE_MIDDLEWARE_ALIAS = "default"
CACHE_MIDDLEWARE_SECONDS = 60 * 60 * 2  # 2 hours
CACHE_MIDDLEWARE_KEY_PREFIX = "educa"
SESSION_COOKIE_AGE = 60 * 60 * 2
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_SAVE_EVERY_REQUEST = True
# GEMINI API
API1_KEY = os.getenv("API1_KEY")
API2_KEY = os.getenv("API2_KEY")
API3_KEY = os.getenv("API3_KEY")
API4_KEY = os.getenv("API4_KEY")
DAILY_QUOTE_API_KEY = os.getenv("DAILY_QUOTE_API_KEY")

# API
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.BasicAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.DjangoModelPermissionsOrAnonReadOnly"
    ],
}

ASGI_APPLICATION = "edu.asgi.application"

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [("127.0.0.1", 6379)],
        },
    },
}

CHAT_MAX_MESSAGES_PER_COURSE = config(
    "CHAT_MAX_MESSAGES_PER_COURSE",
    default=1000,
    cast=int,
)

#telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME")

# ============================================================================
# Email Configuration - Google SMTP for Email Verification
# ============================================================================
# Email backend for sending verification codes
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

# Google SMTP Server
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True

# Gmail/Google credentials (from environment variables)
# For Gmail: Use your Gmail address and an App Password (not regular password)
# Generate App Password: https://myaccount.google.com/apppasswords
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default=EMAIL_HOST_USER)

# Optional: Site name for emails
SITE_NAME = "E-Learning Platform"

# ============================================================================
# Authentication Backends
# ============================================================================
AUTHENTICATION_BACKENDS = [
    # Standard Django: username + password
    "django.contrib.auth.backends.ModelBackend",
    
    # Custom: email + password (allows login with email)
    "account.authentication.EmailAuthBackend",
]

# Custom login URL and redirects
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "course_list"
LOGOUT_REDIRECT_URL = "home"