# candidates/permissions.py

"""
Production-grade, minimal RBAC helpers.

Design goal:
- Employers can *read* candidates globally.
- Candidates (employees) can only access their own profile.

We infer "employer" from Organization membership (root_user or users M2M)
to avoid schema changes / migrations and to keep the existing system stable.
"""

from __future__ import annotations

from rest_framework.permissions import BasePermission, SAFE_METHODS
from organization.models import Organization


def is_employer(user) -> bool:
    """Return True if the authenticated user belongs to (or owns) an Organization."""
    if not user or not getattr(user, "is_authenticated", False):
        return False

    # Root user OR a member user of any organization → employer
    return (
        Organization.objects.filter(root_user=user).exists()
        or Organization.objects.filter(users=user).exists()
    )


def can_access_candidate_profile(user, profile) -> bool:
    """Authorization rule used by AI endpoints (Prompt/CareerCoach).

    - Candidate can access their own profile only.
    - Employer can access any candidate profile (global read access).
    """
    if not user or not getattr(user, "is_authenticated", False):
        return False
    return profile.user_id == user.id or is_employer(user)


class IsOwnerOrEmployerReadOnly(BasePermission):
    """Object-level permissions for CandidateProfile.

    - Candidate (owner): full access to their own CandidateProfile.
    - Employer: read-only access to all CandidateProfiles.

    NOTE: For list views, filtering is handled in `CandidateViewSet.get_queryset()`.
    """

    def has_object_permission(self, request, view, obj) -> bool:
        # Owner can do anything on their own profile
        if getattr(obj, "user_id", None) == getattr(request.user, "id", None):
            return True

        # Employers can only READ
        if is_employer(request.user) and request.method in SAFE_METHODS:
            return True

        return False
