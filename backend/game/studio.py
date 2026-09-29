"""Teacher Studio API — owner-scoped CRUD for course content.

Teachers (``is_staff``) author their own courses here. Every queryset is
filtered to content the requesting teacher owns; superusers see and edit
everything. The public content API (``game.views``) is read-only for everyone
except superusers, so the Studio is the only write path for teachers and
ownership cannot be bypassed.

Hierarchy: Track (course) → Location (section) → Mission → Task
(story / quiz / code). A mission with no tasks cannot be published: learners
could open it but never finish it.
"""

from django.utils.text import slugify
from rest_framework import permissions, serializers, viewsets
from rest_framework.exceptions import PermissionDenied

from .models import Location, Mission, MissionTask, Track

# Rewards are authored by teachers, so they are capped: an absurd value would
# distort the leaderboard for the whole platform.
MAX_MISSION_XP = 500
MAX_TASK_XP = 100

STUDIO_TASK_TYPES = ("story", "quiz", "code")
MAX_QUIZ_OPTIONS = 8
MAX_TEXT = 20_000
MAX_CODE = 10_000


def _unique_slug(base: str) -> str:
    """Slugify *base* and append -2/-3/... until the slug is unique."""
    base = slugify(base, allow_unicode=False) or "course"
    slug = base
    n = 2
    while Track.objects.filter(slug=slug).exists():
        slug = f"{base}-{n}"
        n += 1
    return slug


def _mirror(localized_ru, localized_en, fallback):
    """Pick a non-empty value (ru → en → fallback) for the legacy field."""
    return (localized_ru or localized_en or fallback)


# ── Serializers ──────────────────────────────────────────────────────────────
# Write-friendly and flat: the teacher edits ``*_ru`` / ``*_en`` directly. The
# legacy non-localized ``title`` / ``description`` columns are kept in sync so
# the play-side localization fallback always has a value.


class StudioTrackSerializer(serializers.ModelSerializer):
    locations_count = serializers.SerializerMethodField()
    missions_count = serializers.SerializerMethodField()

    class Meta:
        model = Track
        fields = [
            "id",
            "slug",
            "title_ru",
            "title_en",
            "description_ru",
            "description_en",
            "tagline_ru",
            "tagline_en",
            "color_theme",
            "icon_url",
            "banner_url",
            "order",
            "is_active",
            "locations_count",
            "missions_count",
        ]
        read_only_fields = ["slug"]

    def get_locations_count(self, obj):
        return obj.worlds.count()

    def get_missions_count(self, obj):
        return Mission.objects.filter(location__track=obj).count()

    def validate(self, attrs):
        if self.instance is None and not (
            attrs.get("title_ru") or attrs.get("title_en")
        ):
            raise serializers.ValidationError(
                {"title_ru": "Укажите название курса."}
            )
        return attrs

    def create(self, validated):
        title = _mirror(validated.get("title_ru"), validated.get("title_en"), "Курс")
        validated["title"] = title
        validated["description"] = _mirror(
            validated.get("description_ru"), validated.get("description_en"), ""
        )
        validated["slug"] = _unique_slug(title)
        # Новый курс — черновик: не виден ученикам, пока преподаватель не
        # включит публикацию в редакторе (поле is_active).
        validated.setdefault("is_active", False)
        return super().create(validated)

    def update(self, instance, validated):
        title = _mirror(
            validated.get("title_ru", instance.title_ru),
            validated.get("title_en", instance.title_en),
            instance.title or "Курс",
        )
        validated["title"] = title
        validated["description"] = _mirror(
            validated.get("description_ru", instance.description_ru),
            validated.get("description_en", instance.description_en),
            "",
        )
        return super().update(instance, validated)


class StudioLocationSerializer(serializers.ModelSerializer):
    missions_count = serializers.SerializerMethodField()

    class Meta:
        model = Location
        fields = [
            "id",
            "track",
            "title_ru",
            "title_en",
            "description_ru",
            "description_en",
            "order",
            "missions_count",
        ]

    def get_missions_count(self, obj):
        return obj.missions.count()

    def validate(self, attrs):
        if self.instance is None and not (
            attrs.get("title_ru") or attrs.get("title_en")
        ):
            raise serializers.ValidationError(
                {"title_ru": "Укажите название раздела."}
            )
        return attrs

    def create(self, validated):
        validated["title"] = _mirror(
            validated.get("title_ru"), validated.get("title_en"), "Раздел"
        )
        validated["description"] = _mirror(
            validated.get("description_ru"), validated.get("description_en"), ""
        )
        return super().create(validated)

    def update(self, instance, validated):
        validated["title"] = _mirror(
            validated.get("title_ru", instance.title_ru),
            validated.get("title_en", instance.title_en),
            instance.title or "Раздел",
        )
        validated["description"] = _mirror(
            validated.get("description_ru", instance.description_ru),
            validated.get("description_en", instance.description_en),
            "",
        )
        return super().update(instance, validated)


class StudioMissionSerializer(serializers.ModelSerializer):
    tasks_count = serializers.SerializerMethodField()

    class Meta:
        model = Mission
        fields = [
            "id",
            "location",
            "title_ru",
            "title_en",
            "description_ru",
            "description_en",
            "xp_reward",
            "order",
            "is_active",
            "min_level",
            "tasks_count",
        ]

    def get_tasks_count(self, obj):
        return obj.tasks.count()

    def validate_xp_reward(self, value):
        if not 0 <= value <= MAX_MISSION_XP:
            raise serializers.ValidationError(
                f"Награда за миссию: от 0 до {MAX_MISSION_XP} XP."
            )
        return value

    def validate(self, attrs):
        if self.instance is None and not (
            attrs.get("title_ru") or attrs.get("title_en")
        ):
            raise serializers.ValidationError(
                {"title_ru": "Укажите название миссии."}
            )
        # A published mission must be finishable, i.e. have at least one task.
        if attrs.get("is_active") and (
            self.instance is None or not self.instance.tasks.exists()
        ):
            raise serializers.ValidationError(
                {"is_active": "Добавьте хотя бы одну задачу, прежде чем публиковать миссию."}
            )
        return attrs

    def create(self, validated):
        # A new mission is a draft until its tasks exist.
        validated.setdefault("is_active", False)
        validated["title"] = _mirror(
            validated.get("title_ru"), validated.get("title_en"), "Миссия"
        )
        validated["description"] = _mirror(
            validated.get("description_ru"), validated.get("description_en"), ""
        )
        return super().create(validated)

    def update(self, instance, validated):
        validated["title"] = _mirror(
            validated.get("title_ru", instance.title_ru),
            validated.get("title_en", instance.title_en),
            instance.title or "Миссия",
        )
        validated["description"] = _mirror(
            validated.get("description_ru", instance.description_ru),
            validated.get("description_en", instance.description_en),
            "",
        )
        return super().update(instance, validated)


# ── ViewSets ─────────────────────────────────────────────────────────────────


class StudioTrackViewSet(viewsets.ModelViewSet):
    """A teacher's own courses. Superusers see all."""

    serializer_class = StudioTrackSerializer
    permission_classes = [permissions.IsAdminUser]
    queryset = Track.objects.all()

    def get_queryset(self):
        qs = Track.objects.all().order_by("order", "id")
        if self.request.user.is_superuser:
            return qs
        return qs.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class StudioLocationViewSet(viewsets.ModelViewSet):
    """Sections inside a teacher's courses. Filter with ``?track=<id>``."""

    serializer_class = StudioLocationSerializer
    permission_classes = [permissions.IsAdminUser]
    queryset = Location.objects.all()

    def get_queryset(self):
        qs = Location.objects.select_related("track").order_by("order", "id")
        if not self.request.user.is_superuser:
            qs = qs.filter(track__owner=self.request.user)
        track_id = self.request.query_params.get("track")
        if track_id:
            qs = qs.filter(track_id=track_id)
        return qs

    def _check_track(self, track):
        if track is None:
            raise serializers.ValidationError({"track": "Курс обязателен."})
        if not self.request.user.is_superuser and track.owner_id != self.request.user.id:
            raise PermissionDenied("Можно добавлять разделы только в свои курсы.")

    def perform_create(self, serializer):
        self._check_track(serializer.validated_data.get("track"))
        serializer.save()

    def perform_update(self, serializer):
        self._check_track(
            serializer.validated_data.get("track", serializer.instance.track)
        )
        serializer.save()


class StudioMissionViewSet(viewsets.ModelViewSet):
    """Missions inside a teacher's courses. Filter with ``?location=<id>``."""

    serializer_class = StudioMissionSerializer
    permission_classes = [permissions.IsAdminUser]
    queryset = Mission.objects.all()

    def get_queryset(self):
        qs = Mission.objects.select_related(
            "location", "location__track"
        ).order_by("order", "id")
        if not self.request.user.is_superuser:
            qs = qs.filter(location__track__owner=self.request.user)
        location_id = self.request.query_params.get("location")
        if location_id:
            qs = qs.filter(location_id=location_id)
        return qs

    def _check_location(self, location):
        if location is None:
            raise serializers.ValidationError({"location": "Раздел обязателен."})
        track = location.track
        if not self.request.user.is_superuser and (
            track is None or track.owner_id != self.request.user.id
        ):
            raise PermissionDenied("Можно добавлять миссии только в свои курсы.")

    def perform_create(self, serializer):
        self._check_location(serializer.validated_data.get("location"))
        serializer.save()

    def perform_update(self, serializer):
        self._check_location(
            serializer.validated_data.get("location", serializer.instance.location)
        )
        serializer.save()


class StudioTaskSerializer(serializers.ModelSerializer):
    """One step of a mission, with the answer key: the author sees it, learners never do."""

    class Meta:
        model = MissionTask
        fields = [
            "id",
            "mission",
            "order",
            "task_type",
            "title_ru",
            "title_en",
            "body_ru",
            "body_en",
            "data",
            "is_required",
            "estimated_minutes",
            "xp_reward",
        ]

    def validate_task_type(self, value):
        if value not in STUDIO_TASK_TYPES:
            raise serializers.ValidationError("Доступны типы: история, квиз, код.")
        return value

    def validate_xp_reward(self, value):
        if not 0 <= value <= MAX_TASK_XP:
            raise serializers.ValidationError(f"Награда за шаг: от 0 до {MAX_TASK_XP} XP.")
        return value

    def validate_estimated_minutes(self, value):
        if not 1 <= value <= 240:
            raise serializers.ValidationError("Оценка времени: от 1 до 240 минут.")
        return value

    def validate_body_ru(self, value):
        return self._short(value)

    def validate_body_en(self, value):
        return self._short(value)

    @staticmethod
    def _short(value):
        if len(value or "") > MAX_TEXT:
            raise serializers.ValidationError(f"Текст длиннее {MAX_TEXT} символов.")
        return value

    def validate(self, attrs):
        instance = self.instance
        task_type = attrs.get("task_type", instance.task_type if instance else "story")
        data = attrs.get("data", instance.data if instance else {})
        if self.instance is None and not (
            attrs.get("title_ru") or attrs.get("title_en")
        ):
            raise serializers.ValidationError({"title_ru": "Укажите название шага."})
        if not isinstance(data, dict):
            raise serializers.ValidationError({"data": "Ожидается объект."})
        attrs["data"] = self._clean_data(task_type, data)
        return attrs

    def _clean_data(self, task_type, data):
        if task_type == "story":
            return {}
        if task_type == "quiz":
            return self._clean_quiz(data)
        return self._clean_code(data)

    @staticmethod
    def _clean_quiz(data):
        options = data.get("options")
        if not isinstance(options, list) or not 2 <= len(options) <= MAX_QUIZ_OPTIONS:
            raise serializers.ValidationError(
                {"data": f"У квиза от 2 до {MAX_QUIZ_OPTIONS} вариантов ответа."}
            )
        cleaned, seen = [], set()
        for option in options:
            if not isinstance(option, dict):
                raise serializers.ValidationError({"data": "Вариант ответа: объект value/label."})
            value = str(option.get("value", "")).strip()
            label = str(option.get("label", value)).strip() or value
            if not value or len(value) > 200 or len(label) > 200:
                raise serializers.ValidationError({"data": "Вариант ответа: от 1 до 200 символов."})
            if value.casefold() in seen:
                raise serializers.ValidationError({"data": "Варианты ответа не должны повторяться."})
            seen.add(value.casefold())
            cleaned.append({"value": value, "label": label})
        answer = str(data.get("correct_answer", "")).strip()
        if answer.casefold() not in seen:
            raise serializers.ValidationError(
                {"data": "Правильный ответ должен совпадать с одним из вариантов."}
            )
        # keep the author's spelling of the option the answer refers to
        answer = next(o["value"] for o in cleaned if o["value"].casefold() == answer.casefold())
        return {"options": cleaned, "correct_answer": answer}

    @staticmethod
    def _clean_code(data):
        starter = str(data.get("starter", ""))
        expected = str(data.get("expected_output", ""))
        if len(starter) > MAX_CODE or len(expected) > MAX_CODE:
            raise serializers.ValidationError({"data": f"Код или вывод длиннее {MAX_CODE} символов."})
        return {"language": "python", "starter": starter, "expected_output": expected}

    def _mirror_texts(self, validated, instance=None):
        get = (lambda k: validated.get(k, getattr(instance, k, ""))) if instance else validated.get
        validated["title"] = _mirror(get("title_ru"), get("title_en"), getattr(instance, "title", "") or "Шаг")
        validated["body"] = _mirror(get("body_ru"), get("body_en"), "")

    def create(self, validated):
        self._mirror_texts(validated)
        return super().create(validated)

    def update(self, instance, validated):
        self._mirror_texts(validated, instance)
        return super().update(instance, validated)


class StudioTaskViewSet(viewsets.ModelViewSet):
    """Tasks inside a teacher's missions. Filter with ``?mission=<id>``."""

    serializer_class = StudioTaskSerializer
    permission_classes = [permissions.IsAdminUser]
    queryset = MissionTask.objects.all()

    def get_queryset(self):
        qs = MissionTask.objects.select_related(
            "mission", "mission__location", "mission__location__track"
        ).order_by("mission_id", "order", "id")
        if not self.request.user.is_superuser:
            qs = qs.filter(mission__location__track__owner=self.request.user)
        mission_id = self.request.query_params.get("mission")
        if mission_id and str(mission_id).isdigit():
            qs = qs.filter(mission_id=mission_id)
        return qs

    def _check_mission(self, mission):
        if mission is None:
            raise serializers.ValidationError({"mission": "Миссия обязательна."})
        track = mission.location.track if mission.location_id else None
        if not self.request.user.is_superuser and (
            track is None or track.owner_id != self.request.user.id
        ):
            raise PermissionDenied("Можно добавлять шаги только в миссии своих курсов.")

    def perform_create(self, serializer):
        self._check_mission(serializer.validated_data.get("mission"))
        serializer.save()

    def perform_update(self, serializer):
        self._check_mission(serializer.validated_data.get("mission", serializer.instance.mission))
        serializer.save()

    def perform_destroy(self, instance):
        mission = instance.mission
        instance.delete()
        # a mission that lost its last task can no longer be finished
        if mission.is_active and not mission.tasks.exists():
            mission.is_active = False
            mission.save(update_fields=["is_active"])
