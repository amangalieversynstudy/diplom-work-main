"""The tavern in the admin: superusers only, like the other records of what learners do.

The guild list is where offensive guild names are renamed or removed.
"""

from django.contrib import admin

from .models import Duel, DuelAttempt, Friendship, Guild, GuildMembership, ItemTrade


class _SuperuserOnly:
    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser


@admin.register(Friendship)
class FriendshipAdmin(_SuperuserOnly, admin.ModelAdmin):
    list_display = ("id", "user_low", "user_high", "requested_by", "status", "created_at", "accepted_at")
    list_filter = ("status",)
    search_fields = ("user_low__username", "user_high__username")
    raw_id_fields = ("user_low", "user_high", "requested_by")


@admin.register(ItemTrade)
class ItemTradeAdmin(_SuperuserOnly, admin.ModelAdmin):
    list_display = ("id", "sender", "receiver", "give_item", "give_qty", "ask_item", "ask_qty", "status", "created_at")
    list_filter = ("status", "give_item")
    search_fields = ("sender__username", "receiver__username")
    raw_id_fields = ("sender", "receiver")
    readonly_fields = ("sender", "receiver", "give_item", "give_qty", "ask_item", "ask_qty", "created_at", "resolved_at")


class GuildMembershipInline(admin.TabularInline):
    model = GuildMembership
    extra = 0
    raw_id_fields = ("user",)
    readonly_fields = ("joined_at",)


@admin.register(Guild)
class GuildAdmin(_SuperuserOnly, admin.ModelAdmin):
    list_display = ("id", "name", "leader", "emblem", "created_at")
    search_fields = ("name", "leader__username")
    raw_id_fields = ("leader",)
    inlines = [GuildMembershipInline]


class DuelAttemptInline(admin.TabularInline):
    model = DuelAttempt
    extra = 0
    readonly_fields = ("user", "started_at", "submitted_at", "correct", "results", "late")
    can_delete = False


@admin.register(Duel)
class DuelAdmin(_SuperuserOnly, admin.ModelAdmin):
    list_display = ("id", "challenger", "opponent", "status", "winner", "created_at", "finished_at")
    list_filter = ("status",)
    search_fields = ("challenger__username", "opponent__username")
    raw_id_fields = ("challenger", "opponent", "winner")
    readonly_fields = ("task_ids", "created_at", "finished_at")
    inlines = [DuelAttemptInline]
