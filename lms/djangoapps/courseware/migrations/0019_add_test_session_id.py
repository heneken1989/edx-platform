# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courseware', '0018_quizresult'),
    ]

    operations = [
        migrations.AddField(
            model_name='quizresult',
            name='test_session_id',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
