# organization/views.py

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from .serializers import (
    OrganizationCreateSerializer,
    OrganizationInviteCreateSerializer,
    OrganizationSerializer,
)

from .models import Organization, OrganizationInvite, create_organization_invite
from django.core.mail import send_mail
import os


class OrganizationsViewSet(viewsets.ModelViewSet):
    """
    CRUD for Organizations (Supabase compatible).
    """
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):

        return self.request.user.organizations.all()

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return OrganizationCreateSerializer
        return OrganizationSerializer

    # ------------------------------------------------------------------
    # CREATE ORGANIZATION
    # ------------------------------------------------------------------
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        instance = serializer.save(root_user=request.user)

        return Response(
            OrganizationSerializer(instance).data,
            status=status.HTTP_201_CREATED
        )

    # ------------------------------------------------------------------
    # CREATE ORGANIZATION INVITE
    # ------------------------------------------------------------------
    @action(methods=["POST"], detail=True, url_path="create-invite")
    def create_invite(self, request, pk=None):
        organization = self.get_object()

        serializer = OrganizationInviteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        invite_code = create_organization_invite()

        invite = OrganizationInvite.objects.create(
            organization=organization,
            invite_code=invite_code,
            email=serializer.validated_data["email"],
        )

        send_mail(
            subject="Organization Invite",
            message=f"Your invite code is {invite_code}",
            from_email=os.environ.get("EMAIL_HOST_USER"),
            recipient_list=[invite.email],
            fail_silently=False,
        )

        return Response(
            {
                "email": invite.email,
                "invite_code": invite.invite_code,
                "organization": organization.id,
            },
            status=status.HTTP_201_CREATED,
        )

