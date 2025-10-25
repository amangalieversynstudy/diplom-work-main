from django.contrib import admin
from django.contrib.auth import get_user_model
from .models import Profile
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

User = get_user_model()

# If the default auth.User was automatically registered, unregister first
try:
    admin.site.unregister(User)
except Exception:
    pass


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ("id", "username", "email")


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "xp", "level")
