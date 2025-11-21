from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("game", "0004_mission_coordinates"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="LeaderboardEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("scope", models.CharField(choices=[("global", "Global"), ("track", "Track"), ("friends", "Friends")], default="global", max_length=16)),
                ("period_label", models.CharField(default="all_time", help_text="Например: all_time, weekly_2025W46, monthly_2025-11", max_length=32)),
                ("xp_total", models.IntegerField(default=0)),
                ("position", models.IntegerField(default=0)),
                ("snapshot_at", models.DateTimeField(auto_now_add=True)),
                ("track", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="leaderboard", to="game.track")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="leaderboard_entries", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["scope", "track_id", "period_label", "position"],
            },
        ),
        migrations.CreateModel(
            name="MissionTask",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("order", models.IntegerField(default=0)),
                ("task_type", models.CharField(choices=[("story", "Story/Theory"), ("quiz", "Quiz"), ("code", "Code"), ("project", "Project"), ("challenge", "Challenge")], default="story", max_length=20)),
                ("title", models.CharField(blank=True, max_length=255)),
                ("title_en", models.CharField(blank=True, max_length=255)),
                ("title_ru", models.CharField(blank=True, max_length=255)),
                ("body", models.TextField(blank=True)),
                ("body_en", models.TextField(blank=True)),
                ("body_ru", models.TextField(blank=True)),
                ("data", models.JSONField(blank=True, default=dict)),
                ("xp_reward", models.IntegerField(default=0)),
                ("is_required", models.BooleanField(default=True)),
                ("estimated_minutes", models.IntegerField(default=5)),
                ("is_side_quest", models.BooleanField(default=False, help_text="Если True — отображается как побочная миссия для доп. XP")),
                ("mission", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tasks", to="game.mission")),
            ],
            options={
                "ordering": ["mission", "order", "id"],
            },
        ),
        migrations.CreateModel(
            name="Rank",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("slug", models.SlugField(unique=True)),
                ("title_en", models.CharField(max_length=200)),
                ("title_ru", models.CharField(max_length=200)),
                ("description_en", models.TextField(blank=True)),
                ("description_ru", models.TextField(blank=True)),
                ("min_level", models.IntegerField(default=1)),
                ("min_xp", models.IntegerField(default=0)),
                ("order", models.IntegerField(default=0)),
                ("icon_url", models.URLField(blank=True)),
            ],
            options={
                "ordering": ["order", "min_level", "min_xp"],
            },
        ),
        migrations.CreateModel(
            name="TaskProgress",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("not_started", "Not started"), ("in_progress", "In progress"), ("completed", "Completed")], default="not_started", max_length=20)),
                ("attempts", models.IntegerField(default=0)),
                ("best_score", models.IntegerField(default=0)),
                ("last_submitted_at", models.DateTimeField(blank=True, null=True)),
                ("answer", models.JSONField(blank=True, default=dict)),
                ("task", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="progress_entries", to="game.missiontask")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="task_progress", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AlterUniqueTogether(
            name="leaderboardentry",
            unique_together={("track", "user", "scope", "period_label")},
        ),
        migrations.AlterUniqueTogether(
            name="taskprogress",
            unique_together={("user", "task")},
        ),
    ]
