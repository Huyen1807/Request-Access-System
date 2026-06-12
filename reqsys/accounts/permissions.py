from rest_framework import permissions

class IsSubAdmin(permissions.BasePermission):
    """
    Allows access only to users who belong to the 'sub-admin' group.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            request.user.groups.filter(name='sub-admin').exists()
        )


class IsOwner(permissions.BasePermission):
    """
    Allows access only to users who belong to the 'owner' group.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.groups.filter(name='owner').exists()
        )
