"""Close public courses owned by teachers the platform has not vetted.

Migration 0020 made every existing course public. A self-service teacher (is_teacher) who owned one would see every
learner who opens it, without their consent to that teacher. Such courses become closed classes with a fresh code;
their learners keep their progress and can join with the code.
"""

import secrets

from django.db import migrations
from django.db.models import Q

ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def _code(Track):
    while True:
        code = "".join(secrets.choice(ALPHABET) for _ in range(8))
        if not Track.objects.filter(join_code=code).exists():
            return code


def close_unvetted_public_tracks(apps, schema_editor):
    Track = apps.get_model("game", "Track")
    unvetted = Track.objects.filter(is_public=True, owner__isnull=False, owner__is_superuser=False).filter(
        Q(owner__is_staff=False) | Q(owner__is_teacher=True)
    )
    for track in unvetted:
        track.is_public = False
        track.join_code = track.join_code or _code(Track)
        track.save(update_fields=["is_public", "join_code"])


class Migration(migrations.Migration):
    dependencies = [
        ("game", "0020_classes"),
        ("users", "0011_user_is_teacher"),
    ]

    operations = [migrations.RunPython(close_unvetted_public_tracks, migrations.RunPython.noop)]
