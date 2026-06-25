from rest_framework import permissions


class IsSubAdmin(permissions.BasePermission):
    """
    Allows access only to users whose profile has is_subadmin=True.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            hasattr(request.user, 'profile') and
            request.user.profile.is_subadmin
        )


class IsOwner(permissions.BasePermission):
    """
    Allows access only to users whose profile has is_owner=True.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            hasattr(request.user, 'profile') and
            request.user.profile.is_owner
        )


class IsRequester(permissions.BasePermission):
    """
    Every authenticated user is a requester.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)


class IsSuperUser(permissions.BasePermission):
    """
    Allows access only to superusers.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.is_superuser
        )


class IsDomainManager(permissions.BasePermission):
    """
    Object-level permission: the requesting user must be a manager of the
    Domain (or, for objects with a `domain` attribute such as Application,
    of that related Domain).
    """
    def has_object_permission(self, request, view, obj):
        if request.user and request.user.is_superuser:
            return True
        domain = getattr(obj, 'domain', obj)
        if not domain.managers.exists():
            return True
        return domain.managers.filter(pk=request.user.pk).exists()
