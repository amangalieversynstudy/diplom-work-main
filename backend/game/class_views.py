"""Joining a teacher's class by its code.

A class is a closed course (``Track.is_public`` off) with a join code. The learner opens the invitation, sees who
will be able to see their nickname and progress, agrees, and only then is enrolled. Leaving is one request.
"""

from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .classes import normalize_code
from .models import Enrollment, Track
from .throttles import ClassJoinThrottle


def _class_or_404(code):
    """The open or closed class with this code. A wrong code and a class that does not exist look the same."""
    code = normalize_code(code)
    if not code:
        raise serializers.ValidationError({"code": "Введите код класса."})
    track = Track.objects.filter(join_code=code, is_active=True).select_related("owner").first()
    if track is None:
        return None
    return track


def _teacher_name(track):
    owner = track.owner
    if owner is None:
        return ""
    return owner.display_name or owner.username


def _title(track):
    return track.title_ru or track.title or track.title_en


class ClassLookupView(APIView):
    """Who invites me and to what: shown before the learner agrees."""

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ClassJoinThrottle]

    def get(self, request):
        track = _class_or_404(request.query_params.get("code"))
        if track is None:
            return Response({"detail": "Такого класса нет. Проверьте код."}, status=status.HTTP_404_NOT_FOUND)
        return Response(
            {
                "track_id": track.pk,
                "title": _title(track),
                "teacher": _teacher_name(track),
                "open": track.join_open,
                "joined": Enrollment.objects.filter(user=request.user, track=track).exists(),
                "own": track.owner_id == request.user.pk,
            }
        )


class ClassJoinView(APIView):
    """Join a class. Needs the code and an explicit ``consent`` flag."""

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ClassJoinThrottle]

    def post(self, request):
        track = _class_or_404(request.data.get("code"))
        if track is None:
            return Response({"detail": "Такого класса нет. Проверьте код."}, status=status.HTTP_404_NOT_FOUND)
        if track.owner_id == request.user.pk:
            return Response({"detail": "Это ваш собственный класс."}, status=status.HTTP_400_BAD_REQUEST)
        if request.user.can_teach:
            # a teacher is not a learner: their own trial run must not appear in anyone's cabinet
            return Response(
                {"detail": "Преподаватели не вступают в классы. Зайдите ученическим аккаунтом."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if request.data.get("consent") is not True:
            return Response(
                {"detail": "Нужно согласие: преподаватель увидит ваш ник и прогресс в этом курсе."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        already = Enrollment.objects.filter(user=request.user, track=track).exists()
        if not already:
            if not track.join_open:
                return Response({"detail": "Набор в этот класс закрыт."}, status=status.HTTP_403_FORBIDDEN)
            try:
                Enrollment.objects.create(user=request.user, track=track, consented_at=timezone.now())
            except IntegrityError:  # a double click: the first request already did it
                pass
        return Response(
            {"track_id": track.pk, "title": _title(track), "teacher": _teacher_name(track)},
            status=status.HTTP_200_OK if already else status.HTTP_201_CREATED,
        )


class MyClassesView(APIView):
    """The classes I am in."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        rows = Enrollment.objects.filter(user=request.user).select_related("track", "track__owner")
        return Response(
            [
                {
                    "track_id": row.track_id,
                    "title": _title(row.track),
                    "teacher": _teacher_name(row.track),
                    "joined_at": row.joined_at.isoformat(),
                }
                for row in rows
            ]
        )


class LeaveClassView(APIView):
    """Leave a class: the teacher stops seeing me there. My own progress stays with me."""

    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, track_id):
        row = get_object_or_404(Enrollment, user=request.user, track_id=track_id)
        row.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
