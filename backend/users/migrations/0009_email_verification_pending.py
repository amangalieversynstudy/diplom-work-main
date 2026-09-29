from django.db import migrations, models


def keep_waiting_accounts_activatable(apps, schema_editor):
    """Before this flag, "inactive" meant "waiting for the e-mail link".

    Existing inactive learners with an address keep that meaning, so nobody who
    signed up and never clicked the link is locked out by the change. Inactive
    staff are treated as blocked by an admin.
    """
    User = apps.get_model("users", "User")
    User.objects.filter(is_active=False, is_staff=False).exclude(email="").update(
        email_verification_pending=True
    )


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0008_learning_footprint"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="email_verification_pending",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(keep_waiting_accounts_activatable, migrations.RunPython.noop),
    ]
