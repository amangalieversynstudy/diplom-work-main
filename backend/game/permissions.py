"""Custom DRF permissions for the game app."""

from rest_framework import permissions


class IsSuperUser(permissions.BasePermission):
    """Allow only Django superusers.

    Used to lock writes on the *public* content API (tracks/locations/missions)
    to the platform owner. Teachers (is_staff) author content exclusively
    through the owner-scoped Studio API (``game.studio``), so a teacher can
    never edit another teacher's course by hitting the public endpoints.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_superuser)
