from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('orgs', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('category', models.CharField(choices=[('approval_todo', '审批待办'), ('approval_result', '审批结果'), ('system', '系统通知')], max_length=32)),
                ('title', models.CharField(max_length=255)),
                ('message', models.TextField(blank=True)),
                ('status', models.CharField(choices=[('unread', '未读'), ('read', '已读')], default='unread', max_length=16)),
                ('target_type', models.CharField(blank=True, max_length=64)),
                ('target_id', models.UUIDField(blank=True, null=True)),
                ('extra', models.JSONField(blank=True, default=dict)),
                ('read_at', models.DateTimeField(blank=True, null=True)),
                ('department', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='notifications', to='orgs.department')),
                ('recipient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': '通知',
                'verbose_name_plural': '通知',
                'ordering': ['status', '-created_at'],
            },
        ),
    ]
