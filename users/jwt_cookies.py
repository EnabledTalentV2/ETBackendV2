from django.conf import settings

ACCESS_COOKIE_NAME = "access_token"
REFRESH_COOKIE_NAME = "refresh_token"

def _cookie_secure():
    # respects your ENV=prod flag
    return getattr(settings, "IS_PROD", False)

def _cookie_samesite():
    return "None" if getattr(settings, "IS_PROD", False) else "Lax"

def set_auth_cookies(response, access_token: str, refresh_token: str):
    secure = _cookie_secure()
    samesite = _cookie_samesite()

    # Access token (site-wide)
    response.set_cookie(
        ACCESS_COOKIE_NAME,
        access_token,
        httponly=True,
        secure=secure,
        samesite=samesite,
        path="/",
        max_age=60 * 15,
    )

    # Refresh token (scoped to refresh endpoint)
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        refresh_token,
        httponly=True,
        secure=secure,
        samesite=samesite,
        path="/api/token/refresh/",
        max_age=60 * 60 * 24 * 7,
    )

def clear_auth_cookies(response):
    response.delete_cookie(ACCESS_COOKIE_NAME, path="/")
    response.delete_cookie(REFRESH_COOKIE_NAME, path="/api/token/refresh/")
