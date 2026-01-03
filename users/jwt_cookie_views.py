from django.contrib.auth import authenticate
from django.middleware.csrf import get_token
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from .jwt_cookies import set_auth_cookies, clear_auth_cookies


class CookieTokenObtainView(APIView):
    """
    Login endpoint.
    - Authenticates user
    - Issues access + refresh tokens
    - Stores both in HttpOnly cookies
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")

        user = authenticate(request, email=email, password=password)
        if not user:
            return Response(
                {"detail": "Invalid credentials"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if hasattr(user, "is_verified") and not user.is_verified:
            return Response(
                {"detail": "Email not verified"},
                status=status.HTTP_403_FORBIDDEN,
            )

        refresh = RefreshToken.for_user(user)
        access = refresh.access_token

        response = Response({"detail": "Login success"}, status=status.HTTP_200_OK)
        set_auth_cookies(response, str(access), str(refresh))

        # Ensure CSRF cookie exists for subsequent POST/PUT/DELETE
        get_token(request)

        return response


class CookieTokenRefreshView(APIView):
    """
    Refresh endpoint.
    - Reads refresh token from HttpOnly cookie
    - Rotates refresh token correctly
    - Blacklists old refresh token (if enabled)
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        refresh_token = request.COOKIES.get("refresh_token")
        if not refresh_token:
            return Response(
                {"detail": "Refresh token missing"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            old_refresh = RefreshToken(refresh_token)

            # Generate new access token
            new_access = old_refresh.access_token

            # Rotate refresh token (SimpleJWT standard)
            old_refresh.blacklist()  # requires token_blacklist app

            new_refresh = RefreshToken.for_user(old_refresh.user)  # safe after blacklist

        except TokenError:
            return Response(
                {"detail": "Invalid or expired refresh token"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        response = Response({"detail": "Token refreshed"}, status=status.HTTP_200_OK)
        set_auth_cookies(response, str(new_access), str(new_refresh))
        return response


class CookieLogoutView(APIView):
    """
    Logout endpoint.
    - Clears auth cookies
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        response = Response({"detail": "Logged out"}, status=status.HTTP_200_OK)
        clear_auth_cookies(response)
        return response


class CsrfView(APIView):
    """
    CSRF bootstrap endpoint.
    Call once on frontend app load.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        token = get_token(request)
        return Response({"csrftoken": token})
