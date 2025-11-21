"""Admin registrations for game models."""

from django.contrib import admin

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


@admin.register(ClassRole)
class ClassRoleAdmin(admin.ModelAdmin):
    """Admin for ClassRole model."""

    list_display = ("id", "name")


@admin.register(Track)
class TrackAdmin(admin.ModelAdmin):
    """Admin configuration for Track model."""

    list_display = ("id", "slug", "title", "order", "is_active", "is_premium")
    list_filter = ("is_active", "is_premium")
    search_fields = ("slug", "title", "title_ru", "title_en")


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    """Admin for Location model."""

    list_display = ("id", "title", "track", "order")
    list_filter = ("track",)
    search_fields = ("title", "title_ru", "title_en")


class MissionTaskInline(admin.TabularInline):
    model = MissionTask
    extra = 0
    fields = (
        "order",
        "task_type",
        "title_ru",
        "title_en",
        "xp_reward",
        "is_required",
        "is_side_quest",
    )


@admin.register(Mission)
class MissionAdmin(admin.ModelAdmin):
    """Admin for Mission model."""

    list_display = ("id", "title", "location", "xp_reward", "is_active")
    inlines = [MissionTaskInline]


@admin.register(Progress)
class ProgressAdmin(admin.ModelAdmin):
    """Admin for Progress model."""

    list_display = ("id", "user", "mission", "completed")


@admin.register(TaskProgress)
class TaskProgressAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "task", "status", "attempts", "best_score")
    list_filter = ("status", "task__task_type")
    search_fields = ("user__username", "task__title", "task__title_ru", "task__title_en")


@admin.register(Rank)
class RankAdmin(admin.ModelAdmin):
    list_display = ("slug", "title_ru", "title_en", "min_level", "min_xp", "order")
    ordering = ("order", "min_level")


@admin.register(LeaderboardEntry)
class LeaderboardEntryAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "track", "scope", "period_label", "position", "xp_total")
    list_filter = ("scope", "period_label")
    search_fields = ("user__username", "track__slug")
