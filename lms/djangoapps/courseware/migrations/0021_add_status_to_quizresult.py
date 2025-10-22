# Generated manually on 2025-01-27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courseware', '0020_update_unique_constraint'),
    ]

    operations = [
        migrations.AddField(
            model_name='quizresult',
            name='status',
            field=models.CharField(
                choices=[('processing', 'Processing'), ('completed', 'Completed')],
                default='processing',
                max_length=20
            ),
        ),
    ]
