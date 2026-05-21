"""Channels URL routing for the game app."""

from django.urls import path

from .consumers import RunnerConsumer

websocket_urlpatterns = [
    path("ws/runner/", RunnerConsumer.as_asgi()),
]
