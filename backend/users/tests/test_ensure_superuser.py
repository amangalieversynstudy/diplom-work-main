"""ensure_superuser runs on every deploy start: skip quietly, create once, never stop the start."""

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

User = get_user_model()


@pytest.mark.django_db
def test_nothing_happens_without_the_variable(monkeypatch):
    monkeypatch.delenv("DJANGO_SUPERUSER_USERNAME", raising=False)
    call_command("ensure_superuser")
    assert not User.objects.filter(is_superuser=True).exists()


@pytest.mark.django_db
def test_the_superuser_is_created_once(monkeypatch):
    monkeypatch.setenv("DJANGO_SUPERUSER_USERNAME", "boss")
    monkeypatch.setenv("DJANGO_SUPERUSER_PASSWORD", "Boss-pass-123")
    call_command("ensure_superuser")
    call_command("ensure_superuser")  # the next deploy
    boss = User.objects.get(username="boss")
    assert boss.is_superuser and boss.check_password("Boss-pass-123")
    assert User.objects.filter(is_superuser=True).count() == 1


@pytest.mark.django_db
def test_an_existing_account_is_left_alone(monkeypatch):
    User.objects.create_user(username="Boss", password="old-pass-123")
    monkeypatch.setenv("DJANGO_SUPERUSER_USERNAME", "boss")
    monkeypatch.setenv("DJANGO_SUPERUSER_PASSWORD", "new-pass-123")
    call_command("ensure_superuser")
    user = User.objects.get(username="Boss")
    assert not user.is_superuser and user.check_password("old-pass-123")


@pytest.mark.django_db
def test_a_missing_password_is_reported_and_the_start_goes_on(monkeypatch, capsys):
    monkeypatch.setenv("DJANGO_SUPERUSER_USERNAME", "boss")
    monkeypatch.delenv("DJANGO_SUPERUSER_PASSWORD", raising=False)
    call_command("ensure_superuser")
    assert "DJANGO_SUPERUSER_PASSWORD" in capsys.readouterr().err
    assert not User.objects.filter(username="boss").exists()
