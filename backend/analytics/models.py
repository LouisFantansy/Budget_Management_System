from django.db import models

from common.models import TimestampedModel


class DashboardConfig(TimestampedModel):
    class Scope(models.TextChoices):
        PERSONAL = 'personal', '个人'
        DEPARTMENT = 'department', '部门'
        GLOBAL = 'global', '全局'

    name = models.CharField(max_length=128)
    owner = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='dashboard_configs')
    scope = models.CharField(max_length=32, choices=Scope.choices, default=Scope.PERSONAL)
    department = models.ForeignKey('orgs.Department', on_delete=models.CASCADE, null=True, blank=True, related_name='dashboard_configs')
    version_context = models.CharField(max_length=64, default='latest_approved')
    config = models.JSONField(default=dict, blank=True)
    is_default = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Dashboard 配置'
        verbose_name_plural = 'Dashboard 配置'
        ordering = ['scope', 'name']

    def __str__(self):
        return self.name

# Create your models here.
