from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("game", "0003_codecombat_like_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="mission",
            name="pos_x",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="mission",
            name="pos_y",
            field=models.IntegerField(default=0),
        ),
    ]
