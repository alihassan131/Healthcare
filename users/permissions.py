from rest_framework.permissions import BasePermission, SAFE_METHODS


def _is_admin(user):
    return bool(user and user.is_authenticated and (user.is_superuser or user.is_staff))


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return _is_admin(request.user)


class IsAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        return _is_admin(request.user)


class IsAdminOrDoctor(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return _is_admin(user) or (
            user.is_authenticated and user.role == 'doctor'
        )


class IsAdminOrSelfDoctor(BasePermission):
    def has_object_permission(self, request, view, obj):
        return _is_admin(request.user) or obj.user == request.user