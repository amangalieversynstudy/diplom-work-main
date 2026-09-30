from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0015_coderun_provenance'),
    ]

    operations = [
        migrations.AddField(
            model_name='coderun',
            name='fingerprint',
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="Hash of the code's structure with the author's own names, comments and docstrings left out (game/codeanalysis.py). The code itself is not stored.",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name='coderun',
            name='ast_nodes',
            field=models.PositiveIntegerField(default=0, help_text='Size of the parsed code, 0 if it did not parse.'),
        ),
        migrations.AddField(
            model_name='coderun',
            name='constructs',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='Language constructs used: def, lambda, comprehension, try, ...',
            ),
        ),
    ]
