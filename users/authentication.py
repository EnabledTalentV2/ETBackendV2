from rest_framework_simplejwt.authentication import JWTAuthentication


class CookieOrHeaderJWTAuthentication(JWTAuthentication):
    """
    Production-safe migration auth:
    - Prefer access token from HttpOnly cookie (new standard)
    - Fallback to Authorization: Bearer <token> (legacy support)
    """

    def authenticate(self, request):
        cookie_token = request.COOKIES.get("access_token")
        if cookie_token:
            validated_token = self.get_validated_token(cookie_token)
            user = self.get_user(validated_token)
            return (user, validated_token)

        # fallback to default header-based behavior
        return super().authenticate(request)
