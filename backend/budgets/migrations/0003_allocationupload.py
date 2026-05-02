from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('budget_cycles', '0001_initial'),
        ('budgets', '0002_importjob'),
    ]

    operations = [
        migrations.CreateModel(
            name='AllocationUpload',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('source_name', models.CharField(blank=True, max_length=255)),
                ('status', models.CharField(choices=[('success', '成功'), ('failed', '失败')], default='success', max_length=16)),
                ('total_rows', models.PositiveIntegerField(default=0)),
                ('imported_rows', models.PositiveIntegerField(default=0)),
                ('error_rows', models.PositiveIntegerField(default=0)),
                ('summary', models.JSONField(blank=True, default=dict)),
                ('errors', models.JSONField(blank=True, default=list)),
                ('cycle', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='allocation_uploads', to='budget_cycles.budgetcycle')),
                ('requester', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='allocation_uploads', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': '集团分摊上传任务',
                'verbose_name_plural': '集团分摊上传任务',
                'ordering': ['-created_at'],
            },
        ),
    ]
