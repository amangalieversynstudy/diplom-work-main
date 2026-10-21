"""Admin registrations for users and profile models."""

from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import Profile

User = get_user_model()

# If the default auth.User was automatically registered, unregister first
try:
    admin.site.unregister(User)
except Exception:
    pass

admin.site.index_template = "admin/rpg_index.html"


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    extra = 0
    max_num = 1
    fields = ("xp", "level", "current_streak", "longest_streak", "research_consent")
    readonly_fields = ("xp", "level", "current_streak", "longest_streak", "research_consent")
    verbose_name_plural = "Профиль ученика"

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """Admin for the custom User model."""

    list_display = (
        "username", "email", "role", "is_active", "level_col", "xp_col", "date_joined", "last_login",
    )
    list_filter = ("is_teacher", "is_staff", "is_superuser", "is_active", "date_joined")
    search_fields = ("username", "email")
    ordering = ("-date_joined",)
    list_select_related = ("profile",)
    inlines = [ProfileInline]
    actions = ["make_teacher", "remove_teacher", "block_users", "unblock_users"]

    # the role right after the login: it is what the owner opens this page for
    fieldsets = (
        DjangoUserAdmin.fieldsets[:1]
        + (("Роль на платформе", {"fields": ("is_teacher",)}),)
        + DjangoUserAdmin.fieldsets[1:]
    )

    @admin.display(description="Роль")
    def role(self, obj):
        if obj.is_superuser:
            return "Суперпользователь"
        if obj.is_staff:
            return "Персонал"
        if obj.is_teacher:
            return "Преподаватель"
        return "Ученик"

    @admin.display(description="Уровень", ordering="profile__level")
    def level_col(self, obj):
        p = getattr(obj, "profile", None)
        return p.level if p else "—"

    @admin.display(description="Опыт (XP)", ordering="profile__xp")
    def xp_col(self, obj):
        p = getattr(obj, "profile", None)
        return p.xp if p else "—"

    @admin.action(description="Сделать преподавателем")
    def make_teacher(self, request, queryset):
        n = queryset.update(is_teacher=True)
        self.message_user(request, f"Роль преподавателя выдана: {n}.", messages.SUCCESS)

    @admin.action(description="Снять роль преподавателя")
    def remove_teacher(self, request, queryset):
        n = queryset.update(is_teacher=False)
        self.message_user(request, f"Роль преподавателя снята: {n}.", messages.SUCCESS)

    def _safe_qs(self, request, queryset):
        return queryset.exclude(is_superuser=True).exclude(pk=request.user.pk)

    @admin.action(description="Заблокировать")
    def block_users(self, request, queryset):
        n = self._safe_qs(request, queryset).update(is_active=False)
        skipped = queryset.count() - n
        self.message_user(request, f"Заблокировано: {n}.", messages.SUCCESS)
        if skipped:
            self.message_user(
                request,
                f"Пропущено {skipped}: суперпользователей и себя блокировать нельзя.",
                messages.WARNING,
            )

    @admin.action(description="Разблокировать")
    def unblock_users(self, request, queryset):
        n = self._safe_qs(request, queryset).update(is_active=True)
        self.message_user(request, f"Разблокировано: {n}.", messages.SUCCESS)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    """Admin for Profile model."""

    list_display = ("user", "xp", "level")
