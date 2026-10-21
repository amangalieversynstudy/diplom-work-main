"""Регистрация моделей в админке — CMS-интерфейс для методологов."""

from django.contrib import admin, messages
from django.db.models import Count, Q
from django.utils.html import format_html

from .models import (
    ClassRole,
    Enrollment,
    LeaderboardEntry,
    Location,
    Mission,
    MissionTask,
    Progress,
    Rank,
    TaskProgress,
    Track,
)



class _LocalisedMixin:
    """Show both RU/EN titles in list views."""

    @admin.display(description="RU")
    def ru_title(self, obj):
        return obj.title_ru or "—"

    @admin.display(description="EN")
    def en_title(self, obj):
        return obj.title_en or "—"



@admin.register(ClassRole)
class ClassRoleAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "description")
    search_fields = ("name",)



@admin.register(Track)
class TrackAdmin(_LocalisedMixin, admin.ModelAdmin):
    list_display = (
        "id", "slug", "ru_title", "en_title", "owner",
        "order", "is_active", "join_code", "learners_col", "missions_col", "published_col",
        "is_intro_badge",
    )
    list_filter = ("is_active", "is_intro", "owner__is_teacher")
    search_fields = ("slug", "title", "title_ru", "title_en", "owner__username", "join_code")
    list_editable = ("order", "is_active")
    list_per_page = 25
    list_select_related = ("owner",)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _learners=Count("enrollments", distinct=True),
            _missions=Count("worlds__missions", distinct=True),
            _published=Count(
                "worlds__missions", filter=Q(worlds__missions__is_active=True), distinct=True
            ),
        )

    @admin.display(description="Учеников", ordering="_learners")
    def learners_col(self, obj):
        return obj._learners

    @admin.display(description="Миссий", ordering="_missions")
    def missions_col(self, obj):
        return obj._missions

    @admin.display(description="Опубликовано", ordering="_published")
    def published_col(self, obj):
        return obj._published

    fieldsets = (
        ("Идентификация", {
            "fields": ("slug", "order"),
        }),
        ("Контент (RU)", {
            "fields": ("title_ru", "description_ru", "tagline_ru"),
        }),
        ("Контент (EN)", {
            "fields": ("title_en", "description_en", "tagline_en"),
            "classes": ("collapse",),
        }),
        ("Устаревшие поля (legacy)", {
            "fields": ("title", "description"),
            "classes": ("collapse",),
        }),
        ("Настройки", {
            "fields": ("is_active", "is_intro", "color_theme"),
        }),
        ("Медиа", {
            "fields": ("icon_url", "banner_url"),
            "classes": ("collapse",),
        }),
    )

    @admin.display(description="Вводный", boolean=True)
    def is_intro_badge(self, obj):
        return obj.is_intro



@admin.register(Location)
class LocationAdmin(_LocalisedMixin, admin.ModelAdmin):
    list_display = ("id", "ru_title", "en_title", "track", "order")
    list_filter = ("track",)
    list_select_related = ("track",)
    search_fields = ("title", "title_ru", "title_en")
    list_editable = ("order",)

    fieldsets = (
        ("Идентификация", {
            "fields": ("track", "order"),
        }),
        ("Контент (RU)", {
            "fields": ("title_ru", "description_ru"),
        }),
        ("Контент (EN)", {
            "fields": ("title_en", "description_en"),
            "classes": ("collapse",),
        }),
        ("Legacy", {
            "fields": ("title", "description"),
            "classes": ("collapse",),
        }),
    )



class MissionTaskInline(admin.StackedInline):
    """Stacked inline so methodologists can see/edit full task bodies."""

    model = MissionTask
    extra = 0
    fields = (
        "order",
        "task_type",
        "title_ru",
        "title_en",
        "body_ru",
        "body_en",
        "data",
        "xp_reward",
        "is_required",
        "estimated_minutes",
    )
    show_change_link = True



@admin.register(Mission)
class MissionAdmin(_LocalisedMixin, admin.ModelAdmin):
    list_display = (
        "id", "ru_title", "en_title", "location",
        "xp_reward", "order", "is_active", "min_level",
    )
    list_filter = ("location__track", "is_active", "min_level")
    list_select_related = ("location", "location__track")
    search_fields = ("title", "title_ru", "title_en")
    list_editable = ("order", "is_active", "xp_reward")
    inlines = [MissionTaskInline]
    filter_horizontal = ("prerequisites",)
    actions = ["publish_missions", "unpublish_missions"]

    @admin.action(description="Опубликовать")
    def publish_missions(self, request, queryset):
        ok = 0
        for m in queryset.prefetch_related("tasks"):
            if not m.tasks.exists():
                self.message_user(
                    request,
                    f"Миссия «{m}» не опубликована: добавьте хотя бы одну задачу.",
                    messages.ERROR,
                )
                continue
            if not m.is_active:
                m.is_active = True
                m.save(update_fields=["is_active"])
            ok += 1
        if ok:
            self.message_user(request, f"Опубликовано миссий: {ok}.", messages.SUCCESS)

    @admin.action(description="Снять с публикации")
    def unpublish_missions(self, request, queryset):
        n = queryset.update(is_active=False)
        self.message_user(request, f"Снято с публикации: {n}.", messages.SUCCESS)

    fieldsets = (
        ("Идентификация", {
            "fields": ("location", "order", "min_level"),
        }),
        ("Контент (RU)", {
            "fields": ("title_ru", "description_ru"),
        }),
        ("Контент (EN)", {
            "fields": ("title_en", "description_en"),
            "classes": ("collapse",),
        }),
        ("Legacy", {
            "fields": ("title", "description"),
            "classes": ("collapse",),
        }),
        ("Геймплей", {
            "fields": (
                "xp_reward", "is_active", "repeatable",
                "repeat_xp_rate", "prerequisites",
            ),
        }),
        ("Позиция на карте", {
            "fields": ("pos_x", "pos_y"),
            "classes": ("collapse",),
        }),
    )



@admin.register(MissionTask)
class MissionTaskAdmin(admin.ModelAdmin):
    list_display = (
        "id", "task_type_badge", "title_ru", "mission",
        "order", "xp_reward", "is_required",
    )
    list_filter = ("task_type", "is_required", "mission__location__track")
    list_select_related = ("mission", "mission__location")
    search_fields = ("title_ru", "title_en", "body_ru")
    list_editable = ("order", "xp_reward")
    list_per_page = 40

    fieldsets = (
        ("Привязка", {
            "fields": ("mission", "order", "task_type"),
        }),
        ("Контент (RU)", {
            "fields": ("title_ru", "body_ru"),
        }),
        ("Контент (EN)", {
            "fields": ("title_en", "body_en"),
            "classes": ("collapse",),
        }),
        ("Данные задачи (JSON)", {
            "description": (
                "Для quiz: {correct_answer, options:[{value,label}]}<br>"
                "Для code: {language, starter, sampleOutput, hint}<br>"
                "Для story: {}"
            ),
            "fields": ("data",),
        }),
        ("Настройки", {
            "fields": ("xp_reward", "is_required", "estimated_minutes"),
        }),
    )

    TYPE_COLOURS = {
        "story": "#4ec9b0",
        "quiz": "#ce9178",
        "code": "#569cd6",
        "project": "#dcdcaa",
        "challenge": "#c678dd",
    }

    @admin.display(description="Тип")
    def task_type_badge(self, obj):
        colour = self.TYPE_COLOURS.get(obj.task_type, "#aaa")
        return format_html(
            '<span style="color:{};font-weight:600">{}</span>',
            colour,
            obj.task_type.upper(),
        )





class _SuperuserOnlyMixin:
    """Learners' records (progress, attempts, runs, events, leaderboard rows): superusers only. A staff teacher
    with any admin permission must not read every learner's footprint around the class rules."""

    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

@admin.register(Progress)
class ProgressAdmin(_SuperuserOnlyMixin, admin.ModelAdmin):
    list_display = ("id", "user", "mission", "status", "completed", "xp_earned", "stars", "attempts")
    list_filter = ("completed", "status")
    list_select_related = ("user", "mission")
    search_fields = ("user__username", "mission__title_ru")
    readonly_fields = ("user", "mission", "attempts", "started_at", "completed_at")


@admin.register(TaskProgress)
class TaskProgressAdmin(_SuperuserOnlyMixin, admin.ModelAdmin):
    list_display = ("id", "user", "task", "status", "attempts", "best_score")
    list_filter = ("status", "task__task_type")
    list_select_related = ("user", "task")
    search_fields = ("user__username", "task__title_ru", "task__title_en")
    readonly_fields = ("user", "task", "attempts", "best_score")



@admin.register(Rank)
class RankAdmin(admin.ModelAdmin):
    list_display = ("slug", "title_ru", "title_en", "min_level", "min_xp", "order")
    ordering = ("order", "min_level")
    search_fields = ("slug", "title_ru", "title_en")



@admin.register(LeaderboardEntry)
class LeaderboardEntryAdmin(_SuperuserOnlyMixin, admin.ModelAdmin):
    list_display = (
        "id", "user", "track", "scope",
        "period_label", "position", "xp_total",
    )
    list_filter = ("scope", "period_label")
    list_select_related = ("user", "track")
    search_fields = ("user__username", "track__slug")
    ordering = ("period_label", "position")


from .models import CodeRun, LearningEvent  # noqa: E402


class _ReadOnlyAdmin(_SuperuserOnlyMixin, admin.ModelAdmin):
    """The footprint is written by the server only; the admin just looks."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(CodeRun)
class CodeRunAdmin(_ReadOnlyAdmin):
    list_display = ("created_at", "user", "task", "outcome", "error_type", "passed")
    list_filter = ("outcome", "error_type", "passed", "after_solved")
    date_hierarchy = "created_at"


@admin.register(LearningEvent)
class LearningEventAdmin(_ReadOnlyAdmin):
    list_display = ("created_at", "user", "event_type", "task", "mission")
    list_filter = ("event_type",)
    date_hierarchy = "created_at"


@admin.register(Enrollment)
class EnrollmentAdmin(_SuperuserOnlyMixin, admin.ModelAdmin):
    """Who joined which class: learners' records, superusers only, view only."""

    list_display = ("user", "track", "consented_at", "joined_at")
    list_select_related = ("user", "track")
    search_fields = ("user__username", "track__slug", "track__title_ru", "track__title")
    readonly_fields = ("user", "track", "consented_at", "joined_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
