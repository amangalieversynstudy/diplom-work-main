"""The content-author role in the admin: edits the course content, never deletes it, never sees learners."""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client

User = get_user_model()

pytestmark = pytest.mark.django_db


def test_the_group_edits_content_but_does_not_delete_it():
    group = Group.objects.get(name="Авторы контента")
    codenames = set(group.permissions.values_list("codename", flat=True))
    assert {"add_mission", "change_missiontask", "view_track", "change_rank"} <= codenames
    assert not {name for name in codenames if name.startswith("delete_")}


def test_a_content_author_opens_content_but_not_learners_records():
    author = User.objects.create_user("author", "a@example.com", "S3cure-pass-1", is_staff=True)
    author.groups.add(Group.objects.get(name="Авторы контента"))
    client = Client()
    client.force_login(author)
    assert client.get("/admin/game/mission/").status_code == 200
    assert client.get("/admin/game/missiontask/add/").status_code == 200
    assert client.get("/admin/game/progress/").status_code == 403
    assert client.get("/admin/game/learningevent/").status_code == 403
