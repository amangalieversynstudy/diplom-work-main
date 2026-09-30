from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0014_remove_unused_fields_and_token'),
    ]

    operations = [
        migrations.AddField(
            model_name='coderun',
            name='provenance',
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text='How the code got into the editor (counts only, never the keystrokes): pasted_chars, typed_chars, paste_count, edit_events, edits_after_paste, elapsed_ms. Sent by the editor, so a hint at authorship and not a proof.',
            ),
        ),
    ]
