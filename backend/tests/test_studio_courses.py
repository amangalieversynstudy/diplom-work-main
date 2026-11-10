"""Whole-course operations of the Studio (game/studio_courses.py).

«Создать курс по шаблону» builds a course with its sections, missions and steps in one request: all of it or none,
through the same checks as hand-made content, inside the Studio limits. «Копировать курс» clones a teacher's own
course as a closed draft class with a new code and never takes anything of learners.
"""

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from game.models import CodeRun, Enrollment, Location, Mission, MissionTask, Progress, TaskProgress, Track

User = get_user_model()
pytestmark = pytest.mark.django_db

TRACKS = "/api/teacher/studio/tracks/"
OUTLINE = "/api/teacher/studio/tracks/outline/"


@pytest.fixture(autouse=True)
def _fresh_throttles():
    cache.clear()
    yield
    cache.clear()


def _user(name, **extra):
    return User.objects.create_user(username=name, password="StudioPass123!", **extra)


def _client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def teacher():
    return _user("author", is_teacher=True)


STORY = {"task_type": "story", "title_ru": "Теория", "body_ru": "## Заголовок\nТекст.", "xp_reward": 5}
QUIZ = {
    "task_type": "quiz",
    "title_ru": "Квиз",
    "body_ru": "Сколько строк?",
    "xp_reward": 10,
    "data": {"options": [{"value": "3", "label": "3"}, {"value": "2", "label": "2"}], "correct_answer": "3"},
}
CODE = {
    "task_type": "code",
    "title_ru": "Задача",
    "body_ru": "Посчитайте сумму.",
    "xp_reward": 20,
    "estimated_minutes": 7,
    "data": {
        "starter": "total = 0\n",
        "expected_output": "Итого: 350",
        "hidden_check": 'assert total == 350, "Сумма в total"',
        "hints": [{"ru": "Цикл for", "en": "A for loop"}],
        "skeleton": {"ru": "total = ...\n", "en": ""},
        "not_yet": ["def"],
        "variants": [],
    },
}


def _outline(sections=2, missions=2, steps=(STORY, QUIZ, CODE), **course):
    return {
        "title_ru": "Python с нуля",
        "title_en": "Python from scratch",
        "description_ru": "Вводный курс.",
        **course,
        "sections": [
            {
                "title_ru": f"Глава {s + 1}",
                "title_en": f"Chapter {s + 1}",
                "missions": [
                    {"title_ru": f"Миссия {s + 1}.{m + 1}", "xp_reward": 30, "steps": [dict(step) for step in steps]}
                    for m in range(missions)
                ],
            }
            for s in range(sections)
        ],
    }


def _content_counts():
    return (
        Track.objects.count(),
        Location.objects.count(),
        Mission.objects.count(),
        MissionTask.objects.count(),
    )


# ── «Создать курс по шаблону» ───────────────────────────────────────────────


def test_an_outline_becomes_a_draft_course_with_sections_missions_and_steps(teacher):
    resp = _client(teacher).post(OUTLINE, _outline(sections=4, missions=2), format="json")
    assert resp.status_code == 201, resp.json()
    body = resp.json()
    assert (body["locations_count"], body["missions_count"]) == (4, 8)
    track = Track.objects.get(pk=body["id"])
    assert track.owner == teacher and not track.is_public and track.join_code and not track.is_active
    assert track.title == "Python с нуля"

    sections = list(track.worlds.order_by("order"))
    assert [s.title_ru for s in sections] == ["Глава 1", "Глава 2", "Глава 3", "Глава 4"]
    assert [s.order for s in sections] == [0, 1, 2, 3]
    for section in sections:
        missions = list(section.missions.order_by("order"))
        assert [m.order for m in missions] == [0, 1]
        for mission in missions:
            assert not mission.is_active and mission.xp_reward == 30  # placeholders wait for the teacher
            steps = list(mission.tasks.order_by("order"))
            assert [(s.order, s.task_type) for s in steps] == [(1, "story"), (2, "quiz"), (3, "code")]
            code = steps[2]
            # the Studio's cleaning ran: language added, the check kept, empty parts dropped
            assert code.data["hidden_check"] == CODE["data"]["hidden_check"]
            assert code.data["language"] == "python" and "variants" not in code.data
            assert steps[1].data["correct_answer"] == "3"
            assert code.title == "Задача" and code.body == "Посчитайте сумму."  # legacy columns mirrored


def test_the_outline_is_all_or_nothing_and_says_where_it_failed(teacher):
    broken = _outline()
    # a code step without an expected output or a hidden check would accept any code at all
    broken["sections"][1]["missions"][0]["steps"][2]["data"] = {"starter": "x = 1\n"}
    before = _content_counts()
    resp = _client(teacher).post(OUTLINE, broken, format="json")
    assert resp.status_code == 400
    assert resp.json()["detail"].startswith("Раздел 2, миссия 1, шаг 3: Укажите эталонный вывод")
    assert _content_counts() == before


def test_the_outline_cannot_publish_or_move_content(teacher):
    other = _user("other", is_teacher=True)
    foreign = Track.objects.create(slug="foreign", title="Чужой", owner=other, is_public=False)
    foreign_section = Location.objects.create(track=foreign, title="Чужой раздел")
    outline = _outline(sections=1, missions=1, is_active=True, is_public=True, join_code="STOLEN12")
    outline["sections"][0]["track"] = foreign.pk
    mission = outline["sections"][0]["missions"][0]
    mission.update(is_active=True, location=foreign_section.pk)
    mission["steps"][0]["mission"] = 999_999

    resp = _client(teacher).post(OUTLINE, outline, format="json")
    assert resp.status_code == 201, resp.json()
    track = Track.objects.get(pk=resp.json()["id"])
    assert not track.is_active and not track.is_public and track.join_code != "STOLEN12"
    assert track.worlds.count() == 1 and not foreign.worlds.exclude(pk=foreign_section.pk).exists()
    assert not Mission.objects.filter(location__track=track, is_active=True).exists()
    assert MissionTask.objects.filter(mission__location__track=track).count() == 3


def test_an_outline_without_sections_is_a_plain_course(teacher):
    resp = _client(teacher).post(OUTLINE, {"title_ru": "Пустой курс"}, format="json")
    assert resp.status_code == 201
    assert (resp.json()["locations_count"], resp.json()["missions_count"]) == (0, 0)


@pytest.mark.parametrize(
    "payload",
    [
        {"title_ru": "К", "sections": "много"},
        {"title_ru": "К", "sections": [{"title_ru": "Р", "missions": ["миссия"]}]},
        {"title_ru": "К", "sections": [{"title_ru": "Р", "missions": [{"title_ru": "М", "steps": {"a": 1}}]}]},
        ["не объект"],
    ],
)
def test_a_malformed_outline_is_refused(teacher, payload):
    before = _content_counts()
    resp = _client(teacher).post(OUTLINE, payload, format="json")
    assert resp.status_code == 400
    assert _content_counts() == before


def test_the_outline_needs_a_course_title(teacher):
    before = _content_counts()
    resp = _client(teacher).post(OUTLINE, {**_outline(), "title_ru": "", "title_en": ""}, format="json")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Укажите название курса."
    assert _content_counts() == before


@pytest.mark.parametrize(
    ("limits", "outline", "message"),
    [
        ({"sections_per_track": 1}, _outline(sections=2, missions=1), "Не больше 1 разделов в курсе."),
        ({"missions_per_track": 3}, _outline(sections=2, missions=2), "Не больше 3 миссий в курсе."),
        ({"tasks_per_mission": 2}, _outline(sections=1, missions=1), "Не больше 2 шагов в миссии."),
    ],
)
def test_the_outline_stays_inside_the_studio_limits(teacher, settings, limits, outline, message):
    settings.STUDIO_LIMITS = {**settings.STUDIO_LIMITS, **limits}
    before = _content_counts()
    resp = _client(teacher).post(OUTLINE, outline, format="json")
    assert resp.status_code == 400 and resp.json()["detail"] == message
    assert _content_counts() == before
    # the platform owner is exempt, as in the one-by-one Studio path
    root = _user("root", is_staff=True, is_superuser=True)
    assert _client(root).post(OUTLINE, outline, format="json").status_code == 201


def test_the_outline_counts_against_the_course_quota(teacher, settings):
    settings.STUDIO_LIMITS = {**settings.STUDIO_LIMITS, "tracks_per_teacher": 1}
    api = _client(teacher)
    assert api.post(OUTLINE, _outline(sections=1, missions=1), format="json").status_code == 201
    resp = api.post(OUTLINE, _outline(sections=1, missions=1), format="json")
    assert resp.status_code == 400 and "Не больше 1 курсов" in resp.json()["detail"]
    assert Track.objects.filter(owner=teacher).count() == 1


def test_learners_and_guests_cannot_build_or_copy_courses(teacher):
    track = Track.objects.create(slug="t", title="T", owner=teacher)
    learner = _user("learner")
    before = _content_counts()
    for client in (_client(learner), APIClient()):
        assert client.post(OUTLINE, _outline(), format="json").status_code in (401, 403)
        assert client.post(f"{TRACKS}{track.pk}/copy/").status_code in (401, 403)
    assert _content_counts() == before


# ── «Копировать курс» ────────────────────────────────────────────────────────


@pytest.fixture
def course(teacher):
    """A published class of two sections with every kind of step, prerequisites, and learners' work in it."""
    track = Track.objects.create(
        slug="source", title="Мой курс", title_ru="Мой курс", title_en="My course", description_ru="Описание",
        tagline_ru="Подзаголовок", color_theme="#8844ff", order=3, owner=teacher, is_public=False,
        join_code="SRCCODE2", join_open=False, is_active=True,
    )
    first = Location.objects.create(track=track, title="Глава 1", title_ru="Глава 1", order=0)
    second = Location.objects.create(track=track, title="Глава 2", title_ru="Глава 2", order=1)
    m1 = Mission.objects.create(location=first, title="М1", title_ru="М1", xp_reward=30, order=0, is_active=True)
    m2 = Mission.objects.create(location=first, title="М2", title_ru="М2", xp_reward=50, order=1, is_active=False)
    m3 = Mission.objects.create(location=second, title="М3", title_ru="М3", xp_reward=100, order=0, pos_x=40)
    m2.prerequisites.set([m1])
    m3.prerequisites.set([m1, m2])
    MissionTask.objects.create(mission=m1, order=1, task_type="story", title="Т", title_ru="Т", body_ru="Текст")
    MissionTask.objects.create(
        mission=m1, order=2, task_type="quiz", title="К", title_ru="К",
        data={"options": [{"value": "5", "label": "5"}, {"value": "2", "label": "2"}], "correct_answer": "5"},
    )
    code = MissionTask.objects.create(
        mission=m2, order=1, task_type="code", title="З", title_ru="З", xp_reward=25, estimated_minutes=9,
        data={
            "language": "python", "starter": 'name = "{{name}}"\n', "expected_output": "Привет, {{name}}!",
            "hidden_check": 'assert name == "{{name}}"', "variants": [{"vars": {"name": "Ари"}}, {"vars": {"name": "Мила"}}],
        },
    )
    # the question about a learner's own code: the Studio form cannot rebuild it, a copy must keep it as it is
    MissionTask.objects.create(
        mission=m3, order=1, task_type="quiz", title="О", title_ru="О",
        data={
            "kind": "explain", "about": code.pk,
            "options": [{"value": "{{a}}", "label": "{{a}}"}], "correct_answer": "{{a}}",
        },
    )
    learner = _user("pupil")
    Enrollment.objects.create(user=learner, track=track, consented_at=timezone.now())
    Progress.objects.create(user=learner, mission=m1, completed=True, status="completed")
    step = m1.tasks.get(order=1)
    TaskProgress.objects.create(user=learner, task=step, attempts=2, status="completed")
    CodeRun.objects.create(user=learner, task=m2.tasks.get(), outcome="success", passed=True)
    return track


def _tree(track):
    """The content of a course in reading order, without ids: what a copy must reproduce."""
    rows = []
    for section in track.worlds.order_by("order", "id"):
        rows.append(("section", section.title, section.title_ru, section.order))
        for mission in section.missions.order_by("order", "id"):
            rows.append(
                ("mission", mission.title_ru, mission.xp_reward, mission.order, mission.is_active, mission.pos_x,
                 sorted(pre.title_ru for pre in mission.prerequisites.all()))
            )
            for step in mission.tasks.order_by("order", "id"):
                data = dict(step.data)
                if isinstance(data.get("about"), int):  # a link to another step compares by what it points at
                    data["about"] = MissionTask.objects.get(pk=data["about"]).title_ru
                rows.append(
                    ("step", step.order, step.task_type, step.title_ru, step.body_ru, data, step.xp_reward,
                     step.estimated_minutes, step.is_required)
                )
    return rows


def test_a_copy_is_a_closed_draft_class_with_the_same_content(teacher, course):
    resp = _client(teacher).post(f"{TRACKS}{course.pk}/copy/")
    assert resp.status_code == 201, resp.json()
    body = resp.json()
    assert (body["locations_count"], body["missions_count"]) == (2, 3)
    copy = Track.objects.get(pk=body["id"])
    assert copy.pk != course.pk and copy.owner == teacher
    assert (copy.title_ru, copy.title_en, copy.title) == ("Мой курс (копия)", "My course (copy)", "Мой курс (копия)")
    assert (copy.description_ru, copy.tagline_ru, copy.color_theme, copy.order) == ("Описание", "Подзаголовок", "#8844ff", 3)
    # a new class: closed, a draft, its own code, open for joining; the source's publication does not carry over
    assert not copy.is_public and not copy.is_active and copy.join_open and not copy.is_intro
    assert copy.join_code and copy.join_code != course.join_code and copy.slug != course.slug
    assert _tree(copy) == _tree(course)


def test_a_copy_points_its_prerequisites_at_its_own_missions(teacher, course):
    copy = Track.objects.get(pk=_client(teacher).post(f"{TRACKS}{course.pk}/copy/").json()["id"])
    for mission in Mission.objects.filter(location__track=copy):
        assert all(pre.location.track_id == copy.pk for pre in mission.prerequisites.all()), mission.title_ru
    third = Mission.objects.get(location__track=copy, title_ru="М3")
    assert third.prerequisites.count() == 2


def test_a_copied_explain_question_asks_about_the_copied_code_step(teacher, course):
    source = MissionTask.objects.get(mission__location__track=course, data__kind="explain")
    copy = Track.objects.get(pk=_client(teacher).post(f"{TRACKS}{course.pk}/copy/").json()["id"])
    explain = MissionTask.objects.get(mission__location__track=copy, data__kind="explain")
    # not the source's step: that would borrow the variant the learner of the copy never solved
    assert explain.data["about"] != source.data["about"]
    target = MissionTask.objects.get(pk=explain.data["about"])
    assert target.mission.location.track_id == copy.pk and target.task_type == "code"
    source.refresh_from_db()
    assert MissionTask.objects.get(pk=source.data["about"]).mission.location.track_id == course.pk


def test_whole_course_operations_have_their_own_rate_limit(teacher, course):
    api = _client(teacher)
    codes = [api.post(f"{TRACKS}{course.pk}/copy/").status_code for _ in range(8)]
    assert 429 in codes  # six a minute, far below the generic 60 a minute of ordinary Studio writes


def test_the_outline_error_names_its_part_in_russian(teacher):
    resp = _client(teacher).post(f"{TRACKS}outline/", {"title_ru": "К", "sections": "не список"}, format="json")
    assert resp.status_code == 400
    assert "разделы" in resp.content.decode()


def test_a_copy_takes_nothing_of_learners_and_leaves_the_source_alone(teacher, course):
    source_tree = _tree(course)
    copy = Track.objects.get(pk=_client(teacher).post(f"{TRACKS}{course.pk}/copy/").json()["id"])
    assert not Enrollment.objects.filter(track=copy).exists()
    assert not Progress.objects.filter(mission__location__track=copy).exists()
    assert not TaskProgress.objects.filter(task__mission__location__track=copy).exists()
    assert not CodeRun.objects.filter(task__mission__location__track=copy).exists()
    course.refresh_from_db()
    assert _tree(course) == source_tree and course.is_active and course.join_code == "SRCCODE2"
    assert Enrollment.objects.filter(track=course).count() == 1


def test_a_copy_of_a_copy_and_a_long_title_still_fit(teacher):
    track = Track.objects.create(slug="long", title="Д" * 200, title_ru="Д" * 200, owner=teacher)
    api = _client(teacher)
    first = api.post(f"{TRACKS}{track.pk}/copy/").json()
    second = api.post(f"{TRACKS}{first['id']}/copy/").json()
    for body in (first, second):
        assert len(body["title_ru"]) <= 200 and body["title_ru"].endswith(" (копия)")


def test_another_teachers_course_cannot_be_copied(course):
    stranger = _user("stranger", is_teacher=True)
    before = _content_counts()
    assert _client(stranger).post(f"{TRACKS}{course.pk}/copy/").status_code == 404
    assert _content_counts() == before


def test_the_platform_owner_may_copy_a_built_in_course():
    built_in = Track.objects.create(slug="python", title="Python", is_public=True, is_active=True, is_intro=True)
    Location.objects.create(track=built_in, title="Раздел")
    root = _user("root", is_staff=True, is_superuser=True)
    resp = _client(root).post(f"{TRACKS}{built_in.pk}/copy/")
    assert resp.status_code == 201
    copy = Track.objects.get(pk=resp.json()["id"])
    assert copy.owner == root and not copy.is_public and not copy.is_intro and copy.worlds.count() == 1


def test_a_copy_counts_against_the_course_quota(teacher, course, settings):
    settings.STUDIO_LIMITS = {**settings.STUDIO_LIMITS, "tracks_per_teacher": 1}
    resp = _client(teacher).post(f"{TRACKS}{course.pk}/copy/")
    assert resp.status_code == 400 and "Не больше 1 курсов" in resp.json()["detail"]
    assert Track.objects.filter(owner=teacher).count() == 1


def test_a_copy_stays_inside_the_size_limits(teacher, course, settings):
    # the limits were lowered after the course was built: a copy would exceed what the teacher may make now
    settings.STUDIO_LIMITS = {**settings.STUDIO_LIMITS, "missions_per_track": 2}
    resp = _client(teacher).post(f"{TRACKS}{course.pk}/copy/")
    assert resp.status_code == 400 and resp.json()["detail"] == "Не больше 2 миссий в курсе."
    assert Track.objects.filter(owner=teacher).count() == 1
