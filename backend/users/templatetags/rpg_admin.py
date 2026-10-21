from django import template
from django.conf import settings

from users.admin_dashboard import dashboard_stats

register = template.Library()


@register.simple_tag
def rpg_stats():
    return dashboard_stats()


@register.simple_tag
def rpg_frontend_url():
    return settings.FRONTEND_URL
