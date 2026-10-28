"""«Развернуть демо-пример»: one click gives a new teacher a small finished course to look at and copy from.

A closed class, like every Studio course, with one section, one mission and all three step types: a story, a quiz
and a code task with personal variants, two hints, a skeleton, a hidden check and «ещё не проходили». Everything
goes through the Studio serializers, so the demo obeys the same rules as hand-made content. Course and mission
are published at once: a closed class is seen only by its teacher and by the learners who join it with its code,
and the teacher can open the demo «глазами студента» right away.
"""

from django.db import transaction

from .classes import with_fresh_code
from .models import Track

DEMO_TITLE_RU = "Демо-курс: первые шаги в Python"

COURSE = {
    "title_ru": DEMO_TITLE_RU,
    "title_en": "Demo course: first steps in Python",
    "description_ru": (
        "Показательный курс на 15 минут. Для кого: ученики, которые ещё не писали код. "
        "Что внутри: история с теорией, квиз на понимание и задача с кодом, у каждого ученика свой вариант. "
        "Как пользоваться: откройте курс «глазами студента», потом поменяйте тексты под свою группу или "
        "соберите по его образцу свой курс."
    ),
    "description_en": (
        "A 15-minute sample course: a story with theory, a quiz and a code task where every learner gets their "
        "own variant. Open it as a learner, then adapt the texts or build your own course after it."
    ),
}

SECTION = {"title_ru": "Глава 1. Знакомство с Python", "title_en": "Chapter 1. Meet Python"}

MISSION = {
    "title_ru": "Миссия 1. Переменные и вывод",
    "title_en": "Mission 1. Variables and output",
    "description_ru": "Узнаем, что такое переменная, и напишем первую программу, которая здоровается с героем.",
    "description_en": "What a variable is, and a first program that greets a hero.",
    "xp_reward": 50,
}

STEPS = [
    {
        "task_type": "story",
        "title_ru": "Теория: что такое переменная",
        "title_en": "Theory: what a variable is",
        "body_ru": (
            "<p>Переменная — это <strong>подписанная коробка</strong> для значения. "
            "Мы кладём в неё значение знаком <code>=</code> и потом обращаемся к нему по имени.</p>"
            "<pre><code>hero = \"Ари\"\nprint(hero)</code></pre>"
            "<p>Программа выведет <code>Ари</code>. Если положить в коробку другое значение, "
            "старое исчезнет: переменная помнит только последнее.</p>"
        ),
        "body_en": (
            "<p>A variable is a <strong>labelled box</strong> for a value. We put a value in with <code>=</code> "
            "and use it by its name.</p><pre><code>hero = \"Ari\"\nprint(hero)</code></pre>"
            "<p>The program prints <code>Ari</code>. A new value replaces the old one.</p>"
        ),
        "estimated_minutes": 3,
        "xp_reward": 5,
        "data": {},
    },
    {
        "task_type": "quiz",
        "title_ru": "Квиз: что выведет программа?",
        "title_en": "Quiz: what does the program print?",
        "body_ru": "<pre><code>x = 2\nx = x + 3\nprint(x)</code></pre><p>Что появится на экране?</p>",
        "body_en": "<pre><code>x = 2\nx = x + 3\nprint(x)</code></pre><p>What appears on the screen?</p>",
        "estimated_minutes": 2,
        "xp_reward": 10,
        "data": {
            "options": [
                {"value": "5", "label": "5"},
                {"value": "2", "label": "2"},
                {"value": "x + 3", "label": "x + 3"},
                {"value": "Ошибка", "label": "Ошибка"},
            ],
            "correct_answer": "5",
        },
    },
    {
        "task_type": "code",
        "title_ru": "Задача: поприветствуйте героя",
        "title_en": "Task: greet the hero",
        "body_ru": (
            "<p>В Академию пришёл герой <strong>{{name}}</strong>. Его имя уже лежит в переменной "
            "<code>name</code>.</p><p>Напишите программу, которая выводит ровно одну строку:</p>"
            "<pre><code>Привет, {{name}}!</code></pre>"
            "<p>Используйте переменную, а не имя целиком: у соседа по парте герой другой.</p>"
        ),
        "body_en": (
            "<p>The hero <strong>{{name}}</strong> has come to the Academy; the name is in the variable "
            "<code>name</code>.</p><p>Print exactly one line:</p><pre><code>Привет, {{name}}!</code></pre>"
            "<p>Use the variable, not the name itself: your neighbour has another hero.</p>"
        ),
        "estimated_minutes": 5,
        "xp_reward": 20,
        "data": {
            "starter": 'name = "{{name}}"\n# Выведите приветствие с помощью print\n',
            "expected_output": "Привет, {{name}}!",
            "hidden_check": 'assert name == "{{name}}", "Не меняйте значение переменной name"',
            "hints": [
                {
                    "ru": "Строки склеиваются знаком +: \"Привет, \" + name.",
                    "en": "Strings are joined with +: \"Привет, \" + name.",
                },
                {
                    "ru": "Не забудьте восклицательный знак в конце: + \"!\".",
                    "en": "Do not forget the exclamation mark at the end: + \"!\".",
                },
            ],
            "skeleton": {
                "ru": 'name = "{{name}}"\nprint("Привет, " + ... + "!")\n',
                "en": 'name = "{{name}}"\nprint("Привет, " + ... + "!")\n',
            },
            "not_yet": ["def", "lambda", "comprehension", "import", "class"],
            "variants": [
                {"vars": {"name": "Ари"}},
                {"vars": {"name": "Мила"}},
                {"vars": {"name": "Тимур"}},
                {"vars": {"name": "Зарина"}},
            ],
        },
    },
]


def existing_demo(user):
    """The teacher's demo course if one exists already (a second click opens it instead of making a copy)."""
    return Track.objects.filter(owner=user, title_ru=DEMO_TITLE_RU).order_by("id").first()


def _save(serializer_class, payload, **extra):
    serializer = serializer_class(data=payload)
    serializer.is_valid(raise_exception=True)
    return serializer.save(**extra)


def create_demo_course(user):
    """Build the demo course for *user* in one transaction and return its Track (the quota is checked by the view)."""
    from .studio import (  # the Studio module imports this one
        StudioLocationSerializer,
        StudioMissionSerializer,
        StudioTaskSerializer,
        StudioTrackSerializer,
    )

    with transaction.atomic():
        track = with_fresh_code(
            lambda code: _save(StudioTrackSerializer, COURSE, owner=user, is_public=False, join_code=code)
        )
        section = _save(StudioLocationSerializer, {**SECTION, "track": track.pk, "order": 0})
        mission = _save(StudioMissionSerializer, {**MISSION, "location": section.pk, "order": 0})
        for order, step in enumerate(STEPS, start=1):
            _save(StudioTaskSerializer, {**step, "mission": mission.pk, "order": order})
        # a mission is published only once it has steps (StudioMissionSerializer), so both go live last
        mission.is_active = True
        mission.save(update_fields=["is_active"])
        track.is_active = True
        track.save(update_fields=["is_active"])
    return track
