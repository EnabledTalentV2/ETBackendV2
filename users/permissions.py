from rest_framework.permissions import IsAuthenticated, SAFE_METHODS


class UserViewSetPermissions(IsAuthenticated):
    """
    Permissions:
    - User must be authenticated.
    - Only the owner or staff can modify/update/delete the user.
    - GET/HEAD/OPTIONS allowed for authenticated users.
    """

    def has_object_permission(self, request, view, instance):
        # First check if authenticated
        if not super().has_object_permission(request, view, instance):
            return False

        # Read-only requests always allowed
        if request.method in SAFE_METHODS:
            return True

        # Only owner or admin can modify
        return instance.id == request.user.id or request.user.is_staff
