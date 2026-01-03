from rest_framework import serializers
from .models import Organization, OrganizationInvite
from users.serializers import UserSerializer
from backend.storage import upload_to_supabase



# =====================================================================================
# ORGANIZATION CREATE + UPDATE SERIALIZER
# =====================================================================================

class OrganizationCreateSerializer(serializers.ModelSerializer):
    avatar = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = Organization
        fields = [
            'name',
            'industry',
            'linkedin_url',
            'headquarter_location',
            'about',
            'employee_size',
            'url',
            'avatar'        # incoming file from frontend
        ]

    def create(self, validated_data):
        avatar_file = validated_data.pop("avatar", None)
        org = Organization.objects.create(**validated_data)

        # Upload to Supabase if avatar provided
        if avatar_file:
            url = upload_to_supabase(avatar_file, folder="organization-avatars")
            org.avatar_url = url
            org.save()

        return org

    def update(self, instance, validated_data):
        avatar_file = validated_data.pop("avatar", None)

        # Update basic fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Upload new avatar
        if avatar_file:
            url = upload_to_supabase(avatar_file, folder="organization-avatars")
            instance.avatar_url = url
            instance.save()


        return instance


# =====================================================================================
# ORGANIZATION READ SERIALIZER
# =====================================================================================

class OrganizationSerializer(serializers.ModelSerializer):
    root_user = UserSerializer()
    users = UserSerializer(many=True)

    class Meta:
        model = Organization
        fields = [
            'id',
            'root_user',
            'headquarter_location',
            'about',
            'employee_size',
            'users',
            'name',
            'url',
            'industry',
            'linkedin_url',
            'created_at',
            'avatar_url',      # return Supabase URL
        ]


# =====================================================================================
# INVITE SERIALIZERS
# =====================================================================================

class OrganizationInviteCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationInvite
        fields = ["email"]


class OrganizationInviteSerializer(serializers.ModelSerializer):
    organization = OrganizationSerializer(read_only=True)

    class Meta:
        model = OrganizationInvite
        fields = [
            "organization",
            "invite_code",
            "email",
            "accepted",
            "created_at"
        ]
