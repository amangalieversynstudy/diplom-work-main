"""Teacher Studio API — owner-scoped CRUD for course content.

Teachers (``is_staff``) author their own courses here. Every queryset is
filtered to content the requesting teacher owns; superusers see and edit
everything. The public content API (``game.views``) is read-only for everyone
except superusers, so the Studio is the only write path for teachers and
ownership cannot be bypassed.

Hierarchy: Track (course) → Location (section) → Mission. Mission tasks
(story/quiz/code) are added in a later phase.
"""

from django.utils.text import slugify
from rest_framework import permissions, serializers, viewsets
from rest_framework.exceptions import PermissionDenied

from .models import Location, Mission, Track


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

    def validate(self, attrs):
        if self.instance is None and not (
            attrs.get("title_ru") or attrs.get("title_en")
        ):
            raise serializers.ValidationError(
                {"title_ru": "Укажите название миссии."}
            )
        return attrs

    def create(self, validated):
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
