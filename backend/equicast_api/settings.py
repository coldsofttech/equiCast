import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "insecure-dev-key-change-me")
DEBUG = os.environ.get("DJANGO_DEBUG", "true").lower() == "true"
ALLOWED_HOSTS = [h for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",") if h]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "market_data",
    "identity",
    "accounts",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "equicast_api.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "equicast_api.wsgi.application"
ASGI_APPLICATION = "equicast_api.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    # Only *identifies* a caller when a valid Bearer token is present — it
    # doesn't itself require one. Views that need to be locked down still
    # declare their own `permission_classes = [IsAuthenticated]` (see
    # identity/views.py, market_data/views.py).
    "DEFAULT_AUTHENTICATION_CLASSES": ["identity.authentication.Auth0JWTAuthentication"],
}

CORS_ALLOWED_ORIGINS = [
    o for o in os.environ.get("DJANGO_CORS_ORIGINS", "http://localhost:5173").split(",") if o
]

# No default: there's no sane bucket to fall back to, so an unset value
# should fail loudly rather than silently pointing at nothing.
MARKET_DATA_BUCKET = os.environ.get("MARKET_DATA_BUCKET")
AWS_REGION = os.environ.get("AWS_REGION", "eu-west-1")

# Auth0 tenant/API identifying which access tokens Auth0JWTAuthentication
# accepts — see docs/auth0-setup.md. No defaults, same "fail loudly" reasoning
# as MARKET_DATA_BUCKET: an unset value should error, not silently accept (or
# reject) every token.
AUTH0_DOMAIN = os.environ.get("AUTH0_DOMAIN")
AUTH0_AUDIENCE = os.environ.get("AUTH0_AUDIENCE")
USER_PROFILES_TABLE = os.environ.get("USER_PROFILES_TABLE")

# Bucket for user-owned JSON data (accounts, and future domains like
# portfolios/watchlists) — see infra/main.tf's user_data_bucket module. No
# default, same "fail loudly" reasoning as MARKET_DATA_BUCKET.
USER_DATA_BUCKET = os.environ.get("USER_DATA_BUCKET")
