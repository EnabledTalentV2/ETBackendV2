from django.urls import path
from rest_framework import routers
from . import views

from users.jwt_cookie_views import (
    CookieTokenObtainView,
    CookieTokenRefreshView,
    CookieLogoutView,
    CsrfView,
)

router = routers.DefaultRouter()
router.register("users", views.UserViewSet, basename="users")

urlpatterns = [
    # =========================
    # Public / onboarding
    # =========================
    path("signup/", views.SignupView.as_view(), name="signup"),
    path("verify-email/", views.VerifyEmailView.as_view(), name="verify-email"),
    path("resend-verification/", views.ResendVerificationEmailView.as_view(), name="resend-verification"),
    path("change-password/", views.ChangePasswordView.as_view(), name="change-password"),
    path("add-feedback/", views.AddFeedback.as_view(), name="add-feedback"),

    # =========================
    # Legacy session auth (TEMP)
    # =========================
    path("session/login/", views.LoginView.as_view(), name="session-login"),
    path("session/logout/", views.LogoutView.as_view(), name="session-logout"),

    # =========================
    # HttpOnly JWT auth (CANONICAL)
    # =========================
    path("csrf/", CsrfView.as_view(), name="csrf"),
    path("token/", CookieTokenObtainView.as_view(), name="token"),
    path("token/refresh/", CookieTokenRefreshView.as_view(), name="token-refresh"),
    path("logout/", CookieLogoutView.as_view(), name="logout"),
]

urlpatterns += router.urls
