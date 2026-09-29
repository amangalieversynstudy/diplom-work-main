"""URL routes for user profile endpoints."""

from django.urls import path

from .views import ProfileMeView, UseItemView

urlpatterns = [
    path("profile", ProfileMeView.as_view(), name="profile"),
    path("profile/me/", ProfileMeView.as_view(), name="profile-me"),
    path('profile/use-item/', UseItemView.as_view(), name='use-item'),
]
