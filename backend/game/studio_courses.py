"""Whole-course operations of the Studio: a new course with its skeleton, and a copy of a course.

* ``create_from_outline`` («Создать курс по шаблону»): the course, its sections, missions and steps from one
  request, in one transaction. Every piece goes through the Studio serializers, as in ``demo_course``, so an outline
  cannot create what a teacher could not make by hand: titles are required, rewards are capped, a quiz key is one of
  its options and a code step has an expected output or a hidden check. The course and its missions stay drafts:
  the steps are placeholders the teacher replaces before publishing.
* ``copy_course`` («Копировать курс»): sections, missions and steps with their data are cloned row by row. The
  serializers would reshape data the Studio form cannot edit (the «explain» question about a learner's own code),
  so a copy does not pass through them. Learners, enrollments, progress, runs and events are never copied; the copy
  is a closed draft class with a new join code.

Both obey ``settings.STUDIO_LIMITS`` like the one-by-one Studio path; superusers are exempt.
"""

from collections import Counter
from copy import deepcopy

from django.conf import settings
from django.db import transaction
from rest_framework import serializers

from .classes import with_fresh_code
from .models import Location, Mission, MissionTask, Track

COPY_SUFFIX = {"title_ru": " (копия)", "title_en": " (copy)", "title": " (копия)"}

# what a copy of a course never takes from its source: the class (learners, code, intake), the publication and the
# «вводный курс» flag, which only one built-in course may have
TRACK_NOT_COPIED = {"id", "slug", "owner_id", "is_public", "join_code", "join_open", "is_active", "is_intro"}


def check_size(user, sections, missions, steps_per_mission=()):
    """Refuse a course bigger than a teacher may build by hand (``settings.STUDIO_LIMITS``)."""
    if user.is_superuser:
        return
    limits = settings.STUDIO_LIMITS
    for count, key, message in (
        (sections, "sections_per_track", "Не больше {n} разделов в курсе."),
        (missions, "missions_per_track", "Не больше {n} миссий в курсе."),
        (max(steps_per_mission, default=0), "tasks_per_mission", "Не больше {n} шагов в миссии."),
    ):
        if count > limits[key]:
            raise serializers.ValidationError({"detail": message.format(n=limits[key])})


# ── «Создать курс по шаблону» ────────────────────────────────────────────────


def _items(value, label):
    """A list of objects (an absent list is empty)."""
    if value in (None, ""):
        return []
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise serializers.ValidationError({"detail": f"Структура курса: «{label}» — список объектов."})
    return value


def _first_message(detail):
    """The first readable message of a serializer's errors (a dict of lists of messages, maybe nested)."""
    if isinstance(detail, dict):
        return next((_first_message(value) for value in detail.values()), "")
    if isinstance(detail, list):
        return _first_message(detail[0]) if detail else ""
    return str(detail)


def _save(serializer_class, payload, where, **extra):
    serializer = serializer_class(data=payload)
    if not serializer.is_valid():
        message = _first_message(serializer.errors)
        raise serializers.ValidationError({"detail": f"{where}: {message}" if where else message})
    return serializer.save(**extra)


def outline_size(outline):
    """(sections, missions, steps of each mission) of an outline, checking its shape on the way."""
    sections = _items(outline.get("sections"), "разделы")
    missions = [_items(section.get("missions"), "миссии") for section in sections]
    steps = [len(_items(mission.get("steps"), "шаги")) for group in missions for mission in group]
    return len(sections), len(steps), steps


def create_from_outline(user, outline):
    """Build a course with its sections, missions and steps for ``user`` in one transaction and return the Track.

    ``outline``: the course fields plus ``sections`` → ``missions`` → ``steps`` (the payloads of the Studio
    serializers). The parent of each piece and its order come from its place in the outline; the course quota is
    checked by the view, the size here."""
    from .studio import (  # the Studio module imports this one
        StudioLocationSerializer,
        StudioMissionSerializer,
        StudioTaskSerializer,
        StudioTrackSerializer,
    )

    if not isinstance(outline, dict):
        raise serializers.ValidationError({"detail": "Структура курса: ожидается объект."})
    sections_count, missions_count, steps_count = outline_size(outline)
    check_size(user, sections_count, missions_count, steps_count)
    # placeholders are not for learners: the course is a draft until the teacher publishes it
    course = {key: value for key, value in outline.items() if key not in ("sections", "is_active")}

    with transaction.atomic():
        track = with_fresh_code(
            lambda code: _save(StudioTrackSerializer, course, "", owner=user, is_public=False, join_code=code)
        )
        for s, section in enumerate(outline.get("sections") or []):
            where = f"Раздел {s + 1}"
            fields = {k: v for k, v in section.items() if k not in ("missions", "track", "order")}
            location = _save(StudioLocationSerializer, {**fields, "track": track.pk, "order": s}, where)
            for m, mission in enumerate(section.get("missions") or []):
                where = f"Раздел {s + 1}, миссия {m + 1}"
                fields = {k: v for k, v in mission.items() if k not in ("steps", "location", "order", "is_active")}
                saved = _save(StudioMissionSerializer, {**fields, "location": location.pk, "order": m}, where)
                for n, step in enumerate(mission.get("steps") or []):
                    fields = {k: v for k, v in step.items() if k not in ("mission", "order", "id")}
                    _save(StudioTaskSerializer, {**fields, "mission": saved.pk, "order": n + 1}, f"{where}, шаг {n + 1}")
    return track


# ── «Копировать курс» ────────────────────────────────────────────────────────


def _fields(obj, skip=()):
    """The concrete field values of ``obj`` (by attname) except its id and ``skip``: what a clone starts from."""
    return {
        field.attname: deepcopy(getattr(obj, field.attname))
        for field in obj._meta.concrete_fields
        if not field.primary_key and field.attname not in skip
    }


def _copy_title(value, field):
    if not value:
        return value
    suffix = COPY_SUFFIX[field]
    limit = Track._meta.get_field(field).max_length
    return value[: limit - len(suffix)].rstrip() + suffix


def copy_course(user, source):
    """Clone ``source`` for ``user`` as a closed draft class with a new join code; return the new Track.

    Copied: the course texts and look, its sections, missions (with their publication, rewards and the
    prerequisites between them) and steps with their data. Not copied: anything of learners. The course quota is
    checked by the view, the size here."""
    from .studio import _unique_slug

    sections = list(Location.objects.filter(track=source).order_by("order", "id"))
    missions = list(
        Mission.objects.filter(location__track=source).prefetch_related("prerequisites").order_by("order", "id")
    )
    steps = list(MissionTask.objects.filter(mission__location__track=source).order_by("order", "id"))
    check_size(user, len(sections), len(missions), Counter(step.mission_id for step in steps).values())

    fields = _fields(source, skip=TRACK_NOT_COPIED)
    for name in ("title", "title_ru", "title_en"):
        fields[name] = _copy_title(fields[name], name)

    with transaction.atomic():
        track = with_fresh_code(
            lambda code: Track.objects.create(
                **fields,
                slug=_unique_slug(fields["title"]),
                owner=user,
                is_public=False,
                join_code=code,
                join_open=True,
                is_active=False,
                is_intro=False,
            )
        )
        new_sections = {
            section.pk: Location.objects.create(**_fields(section, skip={"track_id"}), track=track)
            for section in sections
        }
        new_missions = {
            mission.pk: Mission.objects.create(
                **_fields(mission, skip={"location_id"}), location=new_sections[mission.location_id]
            )
            for mission in missions
        }
        for mission in missions:
            # a prerequisite inside the course points at its copy; one in another course stays as it was
            needed = [new_missions.get(pre.pk, pre) for pre in mission.prerequisites.all()]
            if needed:
                new_missions[mission.pk].prerequisites.set(needed)
        new_steps = {
            step.pk: MissionTask.objects.create(**_fields(step, skip={"mission_id"}), mission=new_missions[step.mission_id])
            for step in steps
        }
        # The question about a learner's own code names its code step in data.about. In the copy it must name the
        # COPIED step: otherwise it takes the variant of the source course and marks right answers as wrong.
        relinked = []
        for step in new_steps.values():
            about = step.data.get("about") if isinstance(step.data, dict) else None
            if isinstance(about, int) and not isinstance(about, bool) and about in new_steps:
                step.data = {**step.data, "about": new_steps[about].pk}
                relinked.append(step)
        if relinked:
            MissionTask.objects.bulk_update(relinked, ["data"])
    return track
