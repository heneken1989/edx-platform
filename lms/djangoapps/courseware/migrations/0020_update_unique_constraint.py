# Generated manually

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('courseware', '0019_add_test_session_id'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='quizresult',
            unique_together={('user', 'section_id', 'unit_id', 'template_id', 'test_session_id')},
        ),
    ]
