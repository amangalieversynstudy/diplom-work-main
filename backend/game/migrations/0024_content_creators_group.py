"""The «Авторы контента» group: a content-manager role for the Django admin.

A member edits courses, sections, missions, steps, ranks and hero classes in the admin, but never deletes
them and never sees learners' records (progress, attempts, code runs, events stay superuser-only). To make
someone a content author: tick "staff status" and add them to this group. Teachers keep using the Studio,
which is the authoring screen of the site itself.
"""

from django.db import migrations

GROUP = "Авторы контента"
CONTENT_MODELS = ("track", "location", "mission", "missiontask", "rank", "classrole")
ACTIONS = ("add", "change", "view")


def create_group(apps, schema_editor):
    from django.contrib.auth.management import create_permissions

    # on a fresh database the permissions appear only after every migration; make them now
    for app_config in apps.get_app_configs():
        app_config.models_module = True
        create_permissions(app_config, apps=apps, verbosity=0)
        app_config.models_module = None

    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    group, _ = Group.objects.get_or_create(name=GROUP)
    codenames = [f"{action}_{model}" for model in CONTENT_MODELS for action in ACTIONS]
    group.permissions.add(*Permission.objects.filter(content_type__app_label="game", codename__in=codenames))


def remove_group(apps, schema_editor):
    apps.get_model("auth", "Group").objects.filter(name=GROUP).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("game", "0023_alter_classrole_options_alter_coderun_options_and_more"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [migrations.RunPython(create_group, remove_group)]
