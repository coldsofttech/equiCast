import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "insecure-dev-key-change-me")
DEBUG = os.environ.get("DJANGO_DEBUG", "true").lower() == "true"
ALLOWED_HOSTS = [h for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",") if h]

# Every urls.py pattern already ends in a trailing slash, and every
# documented endpoint (docs/local-setup.md, backend/README.md) is written
# with one — this is a JSON API with no browser navigation to accommodate,
# so Django's default redirect-on-GET-without-slash isn't useful here, and
# for non-safe methods it's actively harmful: CommonMiddleware refuses to
# redirect a POST/PUT/PATCH/DELETE missing its trailing slash (redirecting
# would risk dropping the body) and raises RuntimeError instead, which
# surfaces to the caller as an unhandled 500. False makes every method
# behave the same way for a missing slash: a plain 404.
APPEND_SLASH = False

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
    "pies",
    "watchlists",
    "holdings",
    "transactions",
    "goals",
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

# Per-user request budget DEFAULT_THROTTLE_RATES below applies globally —
# overridable per environment via the API_RATE_LIMIT_PER_MINUTE GitHub
# Environment variable (see infra/variables.tf's api_rate_limit_per_minute
# and .github/workflows/terraform.yml), same convention as the MAX_* caps
# further down.
API_RATE_LIMIT_PER_MINUTE = int(os.environ.get("API_RATE_LIMIT_PER_MINUTE", 120))

# Django's cache framework backs DRF throttling below (every count/window
# it tracks lives here). Explicit rather than relying on Django's own
# implicit LocMemCache default, so the choice — and its one real
# limitation — is documented rather than accidental: LocMemCache is a
# plain in-process dict, scoped to *one* Lambda execution environment, not
# shared across the several that can run concurrently under real traffic.
# Each warm container therefore counts a given user's requests
# independently, so the effective per-user rate can multiply by however
# many containers happen to be warm at once — an accepted, explicit
# tradeoff for now (see identity.throttling's module docstring) rather
# than standing up a new always-on/shared store this app's actual traffic
# doesn't yet justify.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    # Only *identifies* a caller when a valid Bearer token is present — it
    # doesn't itself require one. Views that need to be locked down still
    # declare their own `permission_classes = [IsAuthenticated]` (see
    # identity/views.py, market_data/views.py).
    "DEFAULT_AUTHENTICATION_CLASSES": ["identity.authentication.Auth0JWTAuthentication"],
    # Applies to every DRF view by default (no per-view opt-out needed,
    # since every real endpoint requires IsAuthenticated already) — see
    # identity.throttling.Auth0UserRateThrottle for why this isn't DRF's
    # own UserRateThrottle (Auth0User has no `.pk`).
    "DEFAULT_THROTTLE_CLASSES": ["identity.throttling.Auth0UserRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {"user": f"{API_RATE_LIMIT_PER_MINUTE}/min"},
}

CORS_ALLOWED_ORIGINS = [
    o for o in os.environ.get("DJANGO_CORS_ORIGINS", "http://localhost:5173").split(",") if o
]

# Retry-After isn't one of the handful of response headers a browser
# exposes to a cross-origin fetch() by default (the CORS-safelisted set —
# Cache-Control/Content-Language/Content-Length/Content-Type/Expires/
# Last-Modified/Pragma) — without this, DRF's own Retry-After header on a
# 429 (see rest_framework's exception_handler, set from
# identity.throttling.Auth0UserRateThrottle) would be present on the wire
# but silently unreadable via response.headers.get("Retry-After") in the
# frontend's apiFetch (client.js), which only ever hits this cross-origin
# in a real deployment — same-origin locally, via Vite's dev proxy, is why
# this could otherwise go unnoticed in local testing.
CORS_EXPOSE_HEADERS = ["Retry-After"]

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

# Bucket for user-owned JSON data (accounts, pies, watchlists, holdings,
# transactions) — see infra/main.tf's user_data_bucket module. No default,
# same "fail loudly" reasoning as MARKET_DATA_BUCKET.
USER_DATA_BUCKET = os.environ.get("USER_DATA_BUCKET")

# Product-defined per-user/per-account/per-pie/per-watchlist/per-holding
# caps, overridable per environment via GitHub Environment variables (see
# infra/variables.tf's max_accounts/max_pies/max_watchlists/
# max_holdings_for_account/max_holdings_for_pie/max_holdings_for_watchlist/
# max_transactions_for_holding and .github/workflows/terraform.yml) rather
# than a code change — defaults here match equicast_core's own
# MAX_ACCOUNTS/MAX_PIES/MAX_WATCHLISTS/MAX_HOLDINGS_FOR_ACCOUNT/
# MAX_HOLDINGS_FOR_PIE/MAX_HOLDINGS_FOR_WATCHLIST/
# MAX_TRANSACTIONS_FOR_HOLDING defaults, in case the env var is unset (e.g.
# running locally).
MAX_ACCOUNTS = int(os.environ.get("MAX_ACCOUNTS", 5))
MAX_PIES = int(os.environ.get("MAX_PIES", 20))
MAX_WATCHLISTS = int(os.environ.get("MAX_WATCHLISTS", 5))
MAX_GOALS = int(os.environ.get("MAX_GOALS", 10))
MAX_HOLDINGS_FOR_ACCOUNT = int(os.environ.get("MAX_HOLDINGS_FOR_ACCOUNT", 100))
MAX_HOLDINGS_FOR_PIE = int(os.environ.get("MAX_HOLDINGS_FOR_PIE", 50))
MAX_HOLDINGS_FOR_WATCHLIST = int(os.environ.get("MAX_HOLDINGS_FOR_WATCHLIST", 20))
MAX_TRANSACTIONS_FOR_HOLDING = int(os.environ.get("MAX_TRANSACTIONS_FOR_HOLDING", 500))

# TTL (seconds) for MarketDataClient's in-process S3 parquet cache — same
# overridable-per-environment convention as the MAX_* caps above (see
# infra/variables.tf's market_data_cache_ttl_seconds and
# .github/workflows/terraform.yml), default matching equicast_core's own
# DEFAULT_CACHE_TTL_SECONDS for local/unset use.
MARKET_DATA_CACHE_TTL_SECONDS = int(os.environ.get("MARKET_DATA_CACHE_TTL_SECONDS", 6 * 60 * 60))
