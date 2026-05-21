"""Admin registrations for game models.

Optimised for content editors (methodologists) who need a clean CMS-like
interface to manage tracks, missions, and tasks without touching JSON files.
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import (
    ClassRole,
    LeaderboardEntry,
    Location,
    Mission,
    MissionTask,
    Progress,
    Rank,
    TaskProgress,
    Track,
)


# ─── Shared helpers ───────────────────────────────────────────────────────────

class _LocalisedMixin:
    """Show both RU/EN titles in list views."""

    @admin.display(description="RU")
    def ru_title(self, obj):
        return obj.title_ru or "—"

    @admin.display(description="EN")
    def en_title(self, obj):
        return obj.title_en or "—"


# ─── ClassRole ────────────────────────────────────────────────────────────────

@admin.register(ClassRole)
class ClassRoleAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "description")
    search_fields = ("name",)


# ─── Track ────────────────────────────────────────────────────────────────────

@admin.register(Track)
class TrackAdmin(_LocalisedMixin, admin.ModelAdmin):
    list_display = (
        "id", "slug", "ru_title", "en_title",
        "order", "is_active", "is_premium", "is_intro_badge",
    )
    list_filter = ("is_active", "is_premium", "is_intro")
    search_fields = ("slug", "title", "title_ru", "title_en")
    list_editable = ("order", "is_active")
    list_per_page = 25

    fieldsets = (
        ("Идентификация", {
            "fields": ("slug", "order", "default_language"),
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
            "fields": ("is_active", "is_premium", "is_intro", "color_theme"),
        }),
        ("Медиа", {
            "fields": ("icon_url", "banner_url"),
            "classes": ("collapse",),
        }),
    )

    @admin.display(description="Вводный", boolean=True)
    def is_intro_badge(self, obj):
        return obj.is_intro


# ─── Location ─────────────────────────────────────────────────────────────────

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


# ─── MissionTask inline ───────────────────────────────────────────────────────

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


# ─── Mission ──────────────────────────────────────────────────────────────────

@admin.register(Mission)
class MissionAdmin(_LocalisedMixin, admin.ModelAdmin):
    list_display = (
        "id", "ru_title", "en_title", "location",
        "xp_reward", "order", "is_active", "min_level",
    )
    list_filter = ("is_active", "location__track", "min_level")
    list_select_related = ("location", "location__track")
    search_fields = ("title", "title_ru", "title_en")
    list_editable = ("order", "is_active", "xp_reward")
    inlines = [MissionTaskInline]
    filter_horizontal = ("prerequisites",)

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


# ─── MissionTask (standalone) ─────────────────────────────────────────────────

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


# ─── Progress ─────────────────────────────────────────────────────────────────

@admin.register(Progress)
class ProgressAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "mission", "status", "completed", "xp_earned", "stars", "attempts")
    list_filter = ("completed", "status")
    list_select_related = ("user", "mission")
    search_fields = ("user__username", "mission__title_ru")
    readonly_fields = ("user", "mission", "attempts", "started_at", "completed_at")


@admin.register(TaskProgress)
class TaskProgressAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "task", "status", "attempts", "best_score")
    list_filter = ("status", "task__task_type")
    list_select_related = ("user", "task")
    search_fields = ("user__username", "task__title_ru", "task__title_en")
    readonly_fields = ("user", "task", "attempts", "best_score")


# ─── Rank ─────────────────────────────────────────────────────────────────────

@admin.register(Rank)
class RankAdmin(admin.ModelAdmin):
    list_display = ("slug", "title_ru", "title_en", "min_level", "min_xp", "order")
    ordering = ("order", "min_level")
    search_fields = ("slug", "title_ru", "title_en")


# ─── Leaderboard ──────────────────────────────────────────────────────────────

@admin.register(LeaderboardEntry)
class LeaderboardEntryAdmin(admin.ModelAdmin):
    list_display = (
        "id", "user", "track", "scope",
        "period_label", "position", "xp_total",
    )
    list_filter = ("scope", "period_label")
    list_select_related = ("user", "track")
    search_fields = ("user__username", "track__slug")
    ordering = ("period_label", "position")
