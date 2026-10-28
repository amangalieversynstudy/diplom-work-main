"""JWT authentication with the teacher's «Глазами студента» switch.

The frontend sends ``X-View-As: student`` while a teacher looks at the platform as a learner. The request is then
marked ``user.view_as_student`` and the play side hides the drafts of the teacher's own courses, as a learner
sees them (``game.services.sees_drafts`` / ``only_live_missions``). Nothing else changes: the teacher keeps the
teacher's rights and still earns nothing (preview mode). For anyone who cannot teach the header means nothing.
"""

from rest_framework_simplejwt.authentication import JWTAuthentication

VIEW_AS_HEADER = "HTTP_X_VIEW_AS"


def wants_student_view(request):
    return request.META.get(VIEW_AS_HEADER, "").strip().lower() == "student"


class ViewAsJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        result = super().authenticate(request)
        if result is not None:
            user = result[0]
            user.view_as_student = bool(getattr(user, "can_teach", False) and wants_student_view(request))
        return result
