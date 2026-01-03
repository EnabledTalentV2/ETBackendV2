from rest_framework import serializers
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken

from users.models import User


class EmailTokenObtainPairSerializer(serializers.Serializer):
    """
    JWT login using email + password (matches your existing LoginSerializer).
    Enforces:
      - valid credentials
      - is_active
      - is_verified
    """
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")

        user = authenticate(
            request=self.context.get("request"),
            email=email,
            password=password,
        )

        if not user:
            raise serializers.ValidationError({"detail": "Invalid Credentials"})

        if not user.is_active:
            raise serializers.ValidationError({"detail": "Account disabled"})

        if not getattr(user, "is_verified", False):
            raise serializers.ValidationError({"detail": "Verification required."})

        refresh = RefreshToken.for_user(user)

        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }
