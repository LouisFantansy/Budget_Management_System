from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('budget_templates', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='templatefield',
            name='frozen',
            field=models.BooleanField(default=False),
        ),
    ]
