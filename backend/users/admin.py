"""Admin registrations for users and profile models."""

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import Profile

User = get_user_model()

# If the default auth.User was automatically registered, unregister first
try:
    admin.site.unregister(User)
except Exception:
    pass


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """Admin for the custom User model."""

    list_display = ("id", "username", "email")


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    """Admin for Profile model."""

    list_display = ("user", "xp", "level")
