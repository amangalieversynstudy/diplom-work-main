from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("game", "0002_initial"),
    ]

    operations = [
        # Mission fields
        migrations.AddField(
            model_name="mission",
            name="min_level",
            field=models.IntegerField(default=1),
        ),
        migrations.AddField(
            model_name="mission",
            name="repeatable",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="mission",
            name="repeat_xp_rate",
            field=models.IntegerField(
                default=0, help_text="Repeat completion XP in %, 0 = no XP on repeat"
            ),
        ),
        migrations.AddField(
            model_name="mission",
            name="prerequisites",
            field=models.ManyToManyField(
                blank=True, related_name="unlocks", to="game.mission"
            ),
        ),
        # Progress fields
        migrations.AddField(
            model_name="progress",
            name="status",
            field=models.CharField(
                choices=[
                    ("not_started", "Not started"),
                    ("in_progress", "In progress"),
                    ("completed", "Completed"),
                ],
                default="not_started",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="progress",
            name="attempts",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="progress",
            name="started_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="progress",
            name="last_started_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="progress",
            name="xp_earned",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="progress",
            name="stars",
            field=models.SmallIntegerField(default=0),
        ),
        migrations.AlterUniqueTogether(
            name="progress",
            unique_together={("user", "mission")},
        ),
    ]
