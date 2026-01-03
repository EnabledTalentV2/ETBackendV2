# users/views.py

from django.shortcuts import render
from rest_framework.views import APIView, Http404
from rest_framework import permissions, status, viewsets
from rest_framework.response import Response
from django.contrib.auth import logout, login, authenticate, update_session_auth_hash
from django.conf import settings
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from users.models import User, EmailVerificationToken
from organization.models import OrganizationInvite
from . import serializers, permissions as pp
from rest_framework_simplejwt.tokens import RefreshToken


import smtplib


# ===========================================================================================
# SIGNUP VIEW
# ===========================================================================================
def set_jwt_cookies(response, user):
    refresh = RefreshToken.for_user(user)

    response.set_cookie(
        key="access_token",
        value=str(refresh.access_token),
        httponly=True,
        secure=not settings.DEBUG,
        samesite="None" if not settings.DEBUG else "Lax",
        max_age=60 * 15,
    )

    response.set_cookie(
        key="refresh_token",
        value=str(refresh),
        httponly=True,
        secure=not settings.DEBUG,
        samesite="None" if not settings.DEBUG else "Lax",
        max_age=60 * 60 * 24 * 7,
    )

class RefreshTokenView(APIView):
    permission_classes = (permissions.AllowAny,)

    def post(self, request):
        refresh_token = request.COOKIES.get("refresh_token")
        if not refresh_token:
            return Response({"detail": "No refresh token"}, status=401)

        try:
            refresh = RefreshToken(refresh_token)
            access = refresh.access_token

            response = Response({"detail": "Token refreshed"}, status=200)
            response.set_cookie(
                key="access_token",
                value=str(access),
                httponly=True,
                secure=not settings.DEBUG,
                samesite="None" if not settings.DEBUG else "Lax",
                max_age=60 * 15,
            )
            return response

        except Exception:
            return Response({"detail": "Invalid refresh token"}, status=401)


class SignupView(APIView):
    permission_classes = (permissions.AllowAny,)

    def post(self, request):
        invite_code = request.data.get("invite_code")
        if invite_code:
            if not OrganizationInvite.objects.filter(invite_code=invite_code).exists():
                return Response({"detail": "Invalid invite code."},
                                status=status.HTTP_404_NOT_FOUND)

        serializer = serializers.UserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Create verification token
        verification_token = EmailVerificationToken.objects.create(user=user)

        # Send verification email
        try:
            subject = "Verify your email address"
            message = f"""
Hello,

Thank you for signing up! Please verify your email address.

Your verification code is: {verification_token.code}

Best regards,
The HireMod Team
"""
            msg = f"Subject: {subject}\n\n{message}"

            smtp = smtplib.SMTP("smtp.gmail.com", port=587)
            smtp.starttls()
            smtp.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
            smtp.sendmail(settings.EMAIL_FROM, user.email, msg)
            smtp.quit()

        except Exception as e:
            print("Email send error:", e)

        return Response(
            {"detail": "Registration successful! Please verify your email."},
            status=status.HTTP_201_CREATED
        )


# ===========================================================================================
# VERIFY EMAIL
# ===========================================================================================

class VerifyEmailView(APIView):
    permission_classes = (permissions.AllowAny,)

    def post(self, request):
        email = request.data.get("email")
        code = request.data.get("code")

        if not email or not code:
            return Response({"detail": "Email and code required."},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
            token = EmailVerificationToken.objects.get(user=user, code=code)

            if token.is_expired:
                token.delete()
                return Response({"detail": "Code expired."},
                                status=status.HTTP_400_BAD_REQUEST)

            user.is_verified = True
            user.save()
            token.delete()

            response = Response({"detail": "Email verified"}, status=200)
            set_jwt_cookies(response, user)
            return response

            res = Response({"detail": "Email verified."}, status=status.HTTP_200_OK)
            res.set_cookie("loggedIn", "true", httponly=True)
            return res

        except User.DoesNotExist:
            return Response({"detail": "Invalid email."}, status=status.HTTP_400_BAD_REQUEST)
        except EmailVerificationToken.DoesNotExist:
            return Response({"detail": "Invalid verification code."}, status=status.HTTP_400_BAD_REQUEST)


# ===========================================================================================
# LOGIN
# ===========================================================================================
class LoginView(APIView):
    permission_classes = (permissions.AllowAny,)

    def post(self, request):
        serializer = serializers.LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = authenticate(
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        )

        if not user:
            return Response({"detail": "Invalid credentials"}, status=401)

        if not user.is_verified:
            return Response({"detail": "Email not verified"}, status=403)

        response = Response(
            {"detail": "Login successful"},
            status=status.HTTP_200_OK,
        )

        set_jwt_cookies(response, user)
        return response


# ===========================================================================================
# LOGOUT
# ===========================================================================================

class LogoutView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        response = Response({"detail": "Logged out"}, status=200)

        response.delete_cookie("access_token")
        response.delete_cookie("refresh_token")

        return response

# ===========================================================================================
# USER VIEWSET
# ===========================================================================================

class UserViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.UserSerializer
    permission_classes = (pp.UserViewSetPermissions,)
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    queryset = User.objects.all().select_related("profile")

    def list(self, request, *args, **kwargs):
        raise Http404

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()

        serializer = serializers.UserUpdateSerializer(
            instance=instance, data=request.data, partial=partial
        )
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()

        return Response(serializers.UserSerializer(instance).data,
                        status=status.HTTP_200_OK)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_200_OK)

    @action(methods=("GET",), detail=False, url_path="me")
    def get_current_user_data(self, request):
        return Response(self.get_serializer(request.user).data)


# ===========================================================================================
# CHANGE PASSWORD
# ===========================================================================================

class ChangePasswordView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        serializer = serializers.ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user

        if not user.check_password(serializer.validated_data["current_password"]):
            return Response({"error": "Incorrect old password."},
                            status=status.HTTP_400_BAD_REQUEST)

        if serializer.validated_data["new_password"] != serializer.validated_data["confirm_new_password"]:
            return Response({"message": "Password mismatch"},
                            status=status.HTTP_400_BAD_REQUEST)

        user.set_password(serializer.validated_data["new_password"])
        user.save()
        update_session_auth_hash(request, user)

        return Response({"message": "Password changed successfully."},
                        status=status.HTTP_200_OK)


# ===========================================================================================
# FEEDBACK
# ===========================================================================================

class AddFeedback(APIView):
    permission_classes = (permissions.IsAuthenticated,)
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        serializer = serializers.FeedbackCreateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# ===========================================================================================
# RESEND VERIFICATION EMAIL
# ===========================================================================================

class ResendVerificationEmailView(APIView):
    permission_classes = (permissions.AllowAny,)

    def post(self, request):
        email = request.data.get("email")
        if not email:
            return Response({"detail": "Email required"},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)

            if user.is_verified:
                return Response({"detail": "Email already verified"},
                                status=status.HTTP_400_BAD_REQUEST)

            try:
                token = EmailVerificationToken.objects.get(user=user)
                if token.is_expired:
                    token.delete()
                    token = EmailVerificationToken.objects.create(user=user)

            except EmailVerificationToken.DoesNotExist:
                token = EmailVerificationToken.objects.create(user=user)

            subject = "Verify your email address"
            message = f"Your verification code is: {token.code}"
            msg = f"Subject: Verify your email\n\n{message}"

            smtp = smtplib.SMTP("smtp.gmail.com", port=587)
            smtp.starttls()
            smtp.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
            smtp.sendmail(settings.EMAIL_FROM, user.email, msg)
            smtp.quit()

            return Response({"detail": "Verification email sent"},
                            status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({"detail": "If this email exists, verification was sent"},
                            status=status.HTTP_200_OK)
