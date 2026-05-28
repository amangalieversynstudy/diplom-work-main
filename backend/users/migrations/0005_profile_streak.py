from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0004_emailverificationtoken"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="current_streak",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Текущая серия дней с завершённой миссией",
            ),
        ),
        migrations.AddField(
            model_name="profile",
            name="longest_streak",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Лучшая серия за всё время",
            ),
        ),
    ]
