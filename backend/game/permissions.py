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


class IsTeacher(permissions.BasePermission):
    """The teacher's cabinet, analytics and Studio: a signed-in user with the teacher role or staff rights.

    Every queryset behind these endpoints is still limited to the viewer's own courses (superusers see
    all), so the role alone never exposes another teacher's learners.
    """

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.can_teach)
