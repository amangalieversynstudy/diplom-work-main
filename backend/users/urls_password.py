"""Password reset URL patterns."""

from django.urls import path

from .views_password import PasswordResetConfirmView, PasswordResetRequestView

urlpatterns = [
    path(
        "auth/password-reset/",
        PasswordResetRequestView.as_view(),
        name="password_reset",
    ),
    path(
        "auth/password-reset-confirm/",
        PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
]
