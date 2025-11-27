"""Django AppConfig for the game application."""

from django.apps import AppConfig


class GameConfig(AppConfig):
    """Configuration for the game app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "game"
