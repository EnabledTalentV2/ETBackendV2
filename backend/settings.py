import os
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client
from datetime import timedelta

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# ====================================================================================
# ENV
# ====================================================================================

ENV = os.environ.get("ENV", "dev")  # dev | prod
IS_PROD = ENV == "prod"

# ====================================================================================
# BASIC SETTINGS
# ====================================================================================

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-prod")
DEBUG = os.environ.get("DEBUG", "True") == "True"

ALLOWED_HOSTS = ["*"]

# ====================================================================================
# PROXY / HTTPS (RENDER, VERCEL, NGINX)
# ====================================================================================

# Render (and most PaaS) terminates SSL at the proxy level.
# These settings tell Django:
# "If X-Forwarded-Proto=https, treat the request as secure."
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Allows Django to trust the host header set by the proxy
USE_X_FORWARDED_HOST = True

# ====================================================================================
# INSTALLED APPS
# ====================================================================================

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third-party
    "rest_framework",
    "corsheaders",
    "django_rest_passwordreset",
    "rest_framework_simplejwt.token_blacklist",  # ✅ REQUIRED

    # Local Apps
    "users",
    "organization",
    "candidates",
    "main",
]

# ====================================================================================
# MIDDLEWARE
# ====================================================================================

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "backend.urls"

# ====================================================================================
# TEMPLATES
# ====================================================================================

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

WSGI_APPLICATION = "backend.wsgi.application"

# ====================================================================================
# DATABASE (Supabase PostgreSQL)
# ====================================================================================

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME"),
        "USER": os.environ.get("DB_USER"),
        "PASSWORD": os.environ.get("DB_PASSWORD"),
        "HOST": os.environ.get("DB_HOST"),
        "PORT": os.environ.get("DB_PORT", "5432"),
        "OPTIONS": {"sslmode": "require"},
    }
}

# ====================================================================================
# AUTH
# ====================================================================================

AUTH_USER_MODEL = "users.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ====================================================================================
# I18N
# ====================================================================================

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ====================================================================================
# STATIC / MEDIA
# ====================================================================================

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ====================================================================================
# CORS + CSRF (COOKIE SAFE)
# ====================================================================================

CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOW_CREDENTIALS = True

CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "https://hiremod.vercel.app",
    "https://app.enabledtalent.com",
]

CORS_ALLOW_HEADERS = [
    "X-CSRFToken",
    "Content-Type",
    "Accept",
    "Authorization",
]

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:3000",
    "https://hiremod.vercel.app",
    "https://app.enabledtalent.com",
]

# ✅ Do NOT break localhost
CSRF_COOKIE_SECURE = IS_PROD
SESSION_COOKIE_SECURE = IS_PROD

CSRF_COOKIE_SAMESITE = "None" if IS_PROD else "Lax"
SESSION_COOKIE_SAMESITE = "None" if IS_PROD else "Lax"

CSRF_COOKIE_HTTPONLY = False  # needed for frontend to send X-CSRFToken

# ====================================================================================
# REST FRAMEWORK (JWT COOKIE AUTH)
# ====================================================================================

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "users.authentication.CookieOrHeaderJWTAuthentication",  # ✅ cookie first, header fallback
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.FormParser",
        "rest_framework.parsers.MultiPartParser",
    ],
}


# ====================================================================================
# SIMPLE JWT (HTTPONLY MODE)
# ====================================================================================

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,

    # ✅ Keep Bearer enabled so old clients don't break
    "AUTH_HEADER_TYPES": ("Bearer",),
}


# ====================================================================================
# SUPABASE
# ====================================================================================

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
SUPABASE_BUCKET = os.environ.get("SUPABASE_BUCKET", "media")

SUPABASE = None
if SUPABASE_URL and SUPABASE_KEY:
    SUPABASE = create_client(SUPABASE_URL, SUPABASE_KEY)

# ====================================================================================
# CELERY
# ====================================================================================

CELERY_BROKER_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
CELERY_TIMEZONE = "UTC"
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60

# ====================================================================================
# DEFAULTS
# ====================================================================================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD")
EMAIL_FROM = os.environ.get("EMAIL_FROM", EMAIL_HOST_USER or "")
