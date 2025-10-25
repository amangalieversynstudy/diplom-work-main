"""Admin registrations for game models."""

from django.contrib import admin

from .models import ClassRole, Location, Mission, Progress


@admin.register(ClassRole)
class ClassRoleAdmin(admin.ModelAdmin):
    """Admin for ClassRole model."""

    list_display = ("id", "name")


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    """Admin for Location model."""

    list_display = ("id", "title", "order")


@admin.register(Mission)
class MissionAdmin(admin.ModelAdmin):
    """Admin for Mission model."""

    list_display = ("id", "title", "location", "xp_reward", "is_active")


@admin.register(Progress)
class ProgressAdmin(admin.ModelAdmin):
    """Admin for Progress model."""

    list_display = ("id", "user", "mission", "completed")
