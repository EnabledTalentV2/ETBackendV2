# users/serializers.py

from rest_framework import serializers
from .models import User, Profile, Feedback
from backend.supabase_storage import SupabaseStorageService


# ---------------------------------------------------------------------
# USER CREATE
# ---------------------------------------------------------------------

class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)
    invite_code = serializers.CharField(required=False)

    class Meta:
        model = User
        fields = ["email", "password", "confirm_password", "invite_code", "newsletter"]

    def create(self, validated_data):
        if validated_data["password"] != validated_data["confirm_password"]:
            raise serializers.ValidationError("Password and confirmation do not match.")

        return User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
        )


# ---------------------------------------------------------------------
# PROFILE SERIALIZER
# ---------------------------------------------------------------------

class ProfileSerializer(serializers.ModelSerializer):
    avatar = serializers.CharField(source="avatar_url", read_only=True)

    class Meta:
        model = Profile
        read_only_fields = ["referral_code", "user"]
        fields = ("id", "user", "avatar", "referral_code", "total_referrals")


# ---------------------------------------------------------------------
# USER UPDATE (PROFILE AVATAR → SUPABASE)
# ---------------------------------------------------------------------

class UserUpdateSerializer(serializers.ModelSerializer):
    avatar = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = (
            "id",
            "first_name",
            "last_name",
            "avatar",
        )
        # Removed "email" for safety

    def update(self, instance, validated_data):
        avatar = validated_data.pop("avatar", None)

        # Update user info
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Upload avatar to Supabase
        if avatar is not None:
            profile, _ = Profile.objects.get_or_create(user=instance)
            url, path = SupabaseStorageService.upload_file(avatar, folder="avatars")
            profile.avatar_url = url
            profile.save()

        return instance


# ---------------------------------------------------------------------
# LOGIN SERIALIZER
# ---------------------------------------------------------------------

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()


# ---------------------------------------------------------------------
# USER SERIALIZER
# ---------------------------------------------------------------------

class UserSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer()
    is_candidate = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "first_name",
            "email",
            "last_name",
            "is_active",
            "profile",
            "is_verified",
            "is_candidate",
        )

    def get_is_candidate(self, obj):
        from candidates.models import CandidateProfile
        return CandidateProfile.objects.filter(user=obj).exists()


# ---------------------------------------------------------------------
# CHANGE PASSWORD
# ---------------------------------------------------------------------

class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)
    confirm_new_password = serializers.CharField(write_only=True)


# ---------------------------------------------------------------------
# FEEDBACK CREATE (UPLOAD TO SUPABASE)
# ---------------------------------------------------------------------

class FeedbackCreateSerializer(serializers.ModelSerializer):
    attachment = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = Feedback
        fields = ("urgency", "subject", "message", "emoji", "attachment")

    def create(self, validated_data):
        attachment = validated_data.pop("attachment", None)
        user = self.context["request"].user

        feedback = Feedback.objects.create(user=user, **validated_data)

        # Upload to Supabase if file exists
        if attachment:
            url, path = SupabaseStorageService.upload_file(
                attachment,
                folder="feedbacks",
            )
            feedback.attachment_url = url
            feedback.save()

        return feedback
